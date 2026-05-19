from __future__ import annotations

import json
import logging

from state import AgentState, Phase, ReviewResult, ReviewVerdict

logger = logging.getLogger(__name__)

REVIEWER_SYSTEM_PROMPT = """\
You are a senior code reviewer evaluating a Python project against its
specification. You must be thorough but fair.

You will receive:
- The task specification and required features list
- The implementation plan
- The actual code files
- Test/execution results

Your job is to evaluate:
1. Which required features are correctly implemented and working?
2. Which required features are missing or broken?
3. Are there any bugs (beyond missing features)?
4. What specific changes would fix the issues?

Respond ONLY with a JSON object in this exact format:
{
    "verdict": "approve" or "revise",
    "working_features": ["feature 1 that works", "feature 2 that works"],
    "missing_features": ["feature that's missing or broken"],
    "bugs": ["description of bug 1"],
    "suggestions": "Specific actionable suggestions for the coder."
}

Rules for your verdict:
- "approve" if ALL required features work and there are no critical bugs.
- "revise" if any required feature is missing/broken or there are critical bugs.
- Be strict about the required features — partial implementations count as missing.
- Cosmetic issues alone are NOT grounds for "revise".
"""


def reviewer_node(state: dict, llm_client, sandbox) -> dict:
    s = AgentState(**state)

    code_listing = ""
    for path, content in s.code_files.items():
        code_listing += f"\n### {path}\n```python\n{content}\n```\n"

    test_text = "No test results available."
    if s.test_result:
        test_text = (
            f"Exit code: {s.test_result.exit_code}\n"
            f"Stdout:\n{s.test_result.stdout[:3000]}\n"
            f"Stderr:\n{s.test_result.stderr[:3000]}"
        )

    static_analysis = ""
    if s.container_id:
        py_files = [f for f in s.code_files if f.endswith(".py")]
        for pf in py_files:
            _, cc_out, _ = sandbox.exec_command(
                s.container_id, f"radon cc {pf} -s 2>&1 | head -20"
            )
            _, flake_out, _ = sandbox.exec_command(
                s.container_id, f"flake8 {pf} --max-line-length=120 2>&1 | head -20"
            )
            static_analysis += f"\n**{pf}**\nComplexity:\n{cc_out}\nFlake8:\n{flake_out}\n"

    user_prompt = f"""## Task: {s.task_name}

## Specification:
{s.task_spec}

## Required Features:
{chr(10).join(f"- {f}" for f in s.required_features)}

## Implementation Plan:
{s.plan}

## Code:
{code_listing}

## Test Results:
{test_text}

## Static Analysis:
{static_analysis or "Not available."}

## Iteration: {s.iteration + 1}

Evaluate this implementation. Respond with JSON only.
"""

    tokens = 0
    try:
        review_data, tokens = llm_client.chat_json(
            system_prompt=REVIEWER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            caller="reviewer",
        )
        review = ReviewResult(
            verdict=ReviewVerdict(review_data.get("verdict", "revise")),
            working_features=review_data.get("working_features", []),
            missing_features=review_data.get("missing_features", []),
            bugs=review_data.get("bugs", []),
            suggestions=review_data.get("suggestions", ""),
        )
    except Exception as e:
        logger.error(f"Failed to parse review response: {e}")
        review = ReviewResult(
            verdict=ReviewVerdict.REVISE,
            suggestions=f"Review parsing failed: {e}. Please try again.",
        )

    if s.container_id:
        sandbox.write_file(
            s.container_id,
            f"review_v{s.iteration}.json",
            json.dumps(review.model_dump(), indent=2),
        )

    snapshot = {
        "iteration": s.iteration,
        "verdict": review.verdict,
        "working_features": review.working_features,
        "missing_features": review.missing_features,
        "bugs": review.bugs,
        "num_files": len(s.code_files),
        "tokens_this_iter": tokens,
    }

    new_history = list(s.iteration_history) + [snapshot]

    logger.info(
        f"Review (iteration {s.iteration}): {review.verdict} — "
        f"{len(review.working_features)} working, "
        f"{len(review.missing_features)} missing"
    )

    return {
        "review": review,
        "iteration_history": new_history,
        "phase": Phase.DONE if review.verdict == ReviewVerdict.APPROVE else Phase.PLANNING,
        "total_tokens_used": s.total_tokens_used + tokens,
    }
