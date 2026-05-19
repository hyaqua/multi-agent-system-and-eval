from __future__ import annotations

import json
import logging

from state import AgentState, Phase
from tools.shared_tools import TOOLS, execute_tool_call

logger = logging.getLogger(__name__)

# --- System prompts ---

CODER_SYSTEM_PROMPT = """\
You are an expert Python programmer. Your job is to implement code based on
an implementation plan.

You have tools available: write_file, edit_file, bash, and read_file.

Rules:
- Write complete, working Python code. No placeholders or TODOs.
- Create ALL files needed for the project.
- After writing files, run the code to verify it at least starts without errors.
- If you need external packages, install them with pip first.
- For games using pygame, include a main entry point that runs the game.
- Handle errors gracefully.
- Use edit_file for small targeted changes to existing files.
- Use write_file when creating new files or rewriting entire files.
"""

CODER_REVISION_PROMPT = """\
You are fixing code based on review feedback.

Focus on fixing the specific issues identified. Don't rewrite working code
unless necessary. Prefer edit_file for targeted fixes over write_file for
full rewrites. After making changes, run the code to verify your fixes work.
"""


def coder_node(state: dict, llm_client, sandbox) -> dict:
    s = AgentState(**state)
    total_new_tokens = 0
    all_code_files = dict(s.code_files)
    has_written_files = False

    if s.iteration == 0:
        system = CODER_SYSTEM_PROMPT
        user_prompt = f"""## Task: {s.task_name}

## Implementation Plan:
{s.plan}

## Required Features:
{chr(10).join(f"- {f}" for f in s.required_features)}

Implement the complete project now. Write all files and verify the code runs.
"""
    else:
        system = CODER_REVISION_PROMPT
        review_text = ""
        if s.review:
            review_text = f"""## Review Feedback:
- Missing features: {', '.join(s.review.missing_features)}
- Bugs: {', '.join(s.review.bugs)}
- Suggestions: {s.review.suggestions}
"""
        test_text = ""
        if s.test_result:
            test_text = f"""## Last Test Result:
- Exit code: {s.test_result.exit_code}
- Stderr: {s.test_result.stderr[:2000]}
"""

        file_listing = sandbox.list_files(s.container_id)

        user_prompt = f"""## Task: {s.task_name}

## Updated Plan:
{s.plan}

{review_text}
{test_text}

## Current files in workspace:
{file_listing}

Fix the issues identified above. Read any files you need to understand
the current state, then make targeted fixes.
"""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]

    max_rounds = 15
    for round_num in range(max_rounds):
        try:
            response, tokens = llm_client.chat_with_tools(
                messages=messages,
                tools=TOOLS,
                caller="coder",
            )
            total_new_tokens += tokens
        except Exception as e:
            logger.error(f"LLM call failed in coder round {round_num}: {e}")
            break

        tool_calls = response.choices[0].message.tool_calls

        if not tool_calls:
            # Model is done
            if not has_written_files and round_num == 0:
                # First round, no tools called. Retry with a nudge.
                logger.warning("Coder produced no tool calls on first round. Retrying.")
                messages.append(response.choices[0].message)
                messages.append({
                    "role": "user",
                    "content": (
                        "You need to use the provided tools to write files. "
                        "Please call write_file to create the project files now."
                    ),
                })
                continue
            break

        messages.append(response.choices[0].message)

        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                logger.warning(f"Bad tool call arguments: {tc.function.arguments[:200]}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": "Error: invalid JSON in tool arguments.",
                })
                continue

            result, all_code_files = execute_tool_call(
                name=tc.function.name,
                arguments=args,
                container_id=s.container_id,
                sandbox=sandbox,
                code_files=all_code_files,
            )

            if tc.function.name in ("write_file", "edit_file"):
                has_written_files = True

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    if not has_written_files:
        logger.error("Coder finished without writing any files!")

    logger.info(
        f"Coder finished (iteration {s.iteration}, "
        f"{total_new_tokens} tokens, {len(all_code_files)} files, "
        f"wrote_files={has_written_files})"
    )

    return {
        "code_files": all_code_files,
        "phase": Phase.TESTING,
        "total_tokens_used": s.total_tokens_used + total_new_tokens,
    }
