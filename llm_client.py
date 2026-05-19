from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict

from openai import OpenAI

from config import LLMConfig

logger = logging.getLogger(__name__)


@dataclass
class LLMCallRecord:
    timestamp: float = 0.0
    caller: str = ""  # which agent made this call
    model: str = ""

    # Token usage
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0

    # Content
    response_text: str = ""
    reasoning_content: str = ""
    tool_calls_count: int = 0

    # Timing
    duration_seconds: float = 0.0


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = OpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
        )
        self.total_tokens = 0
        self.call_log: list[LLMCallRecord] = []

    def _extract_usage(self, response) -> tuple[int, int, int, int]:
        if not response.usage:
            return 0, 0, 0, 0

        prompt = response.usage.prompt_tokens or 0
        completion = response.usage.completion_tokens or 0
        total = response.usage.total_tokens or 0
        reasoning = 0
        if hasattr(response.usage, "reasoning_tokens"):
            reasoning = response.usage.reasoning_tokens or 0

        return prompt, completion, reasoning, total

    def _extract_reasoning_content(self, message) -> str:
        if hasattr(message, "reasoning_content") and message.reasoning_content:
            return message.reasoning_content
        return ""

    def _record_call(
        self,
        response,
        caller: str = "",
        duration: float = 0.0,
    ) -> LLMCallRecord:
        message = response.choices[0].message
        prompt, completion, reasoning, total = self._extract_usage(response)

        record = LLMCallRecord(
            timestamp=time.time(),
            caller=caller,
            model=self.config.model,
            prompt_tokens=prompt,
            completion_tokens=completion,
            reasoning_tokens=reasoning,
            total_tokens=total,
            response_text=(message.content or "")[:500],  # truncate for log
            reasoning_content=self._extract_reasoning_content(message),
            tool_calls_count=len(message.tool_calls) if message.tool_calls else 0,
            duration_seconds=round(duration, 3),
        )

        self.call_log.append(record)
        self.total_tokens += total

        logger.debug(
            f"LLM call [{caller}]: {prompt} in / {completion} out / "
            f"{reasoning} reasoning / {duration:.1f}s"
        )

        return record

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict | None = None,
        caller: str = "",
    ) -> tuple[str, int]:
        kwargs: dict = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "extra_body": {
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
            },
        }

        if response_format:
            kwargs["response_format"] = response_format

        try:
            start = time.time()
            response = self.client.chat.completions.create(**kwargs)
            duration = time.time() - start
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

        record = self._record_call(response, caller=caller, duration=duration)
        content = response.choices[0].message.content or ""

        return content, record.total_tokens

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
        caller: str = "",
    ):
        kwargs: dict = {
            "model": self.config.model,
            "messages": messages,
            "tools": tools,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "extra_body": {
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
            },
        }

        try:
            start = time.time()
            response = self.client.chat.completions.create(**kwargs)
            duration = time.time() - start
        except Exception as e:
            logger.error(f"LLM tool call failed: {e}")
            raise

        record = self._record_call(response, caller=caller, duration=duration)

        return response, record.total_tokens

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        caller: str = "",
    ) -> tuple[dict, int]:
        tokens_total = 0
        try:
            text, tokens = self.chat(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format={"type": "json_object"},
                caller=caller,
            )
            tokens_total += tokens
        except Exception:
            text, tokens = self.chat(
                system_prompt=system_prompt + "\n\nRespond ONLY with valid JSON.",
                user_prompt=user_prompt,
                caller=caller,
            )
            tokens_total += tokens

        # Clean up common LLM quirks
        parsed = _try_parse_json(text)
        if parsed is not None:
            return parsed, tokens_total

    def save_call_log(self, output_path: str):
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        log_data = {
            "model": self.config.model,
            "total_calls": len(self.call_log),
            "total_tokens": self.total_tokens,
            "total_reasoning_tokens": sum(r.reasoning_tokens for r in self.call_log),
            "total_completion_tokens": sum(r.completion_tokens for r in self.call_log),
            "total_prompt_tokens": sum(r.prompt_tokens for r in self.call_log),
            "calls": [asdict(r) for r in self.call_log],
        }

        with open(output_path, "w") as f:
            json.dump(log_data, f, indent=2, default=str)

        logger.info(f"Call log saved to {output_path} ({len(self.call_log)} calls)")


def _try_parse_json(text: str) -> dict | None:
    text = text.strip()

    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        else:
            text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None
