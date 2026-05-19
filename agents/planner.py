from __future__ import annotations

import logging

from state import AgentState, Phase

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """\
You are a software architect and planner. Your job is to create a clear,
actionable implementation plan for a Python project.

You will receive a task specification with required features. Produce a plan that:

1. Lists the files to create and their purposes.
2. Describes the architecture (what modules, how they interact).
3. Specifies the implementation order (what to build first).
4. Notes any libraries needed (prefer standard library + pygame for games).
5. For each required feature, briefly describe how it will be implemented.

Keep the plan concise but specific. A coder should be able to follow it
without needing to ask questions.

Output your plan as a markdown document.
"""

PLANNER_REVISION_PROMPT = """\
You are revising the implementation plan based on review feedback.

The current code has issues that need to be addressed. Update the plan to
fix the problems identified in the review. Focus on what needs to change,
not what's already working.

Keep the parts of the plan that are working. Only modify sections that
relate to the identified issues.

Output the revised plan as a markdown document.
"""


def planner_node(state: dict, llm_client, sandbox) -> dict:
    s = AgentState(**state)

    if s.iteration == 0:
        user_prompt = f"""## Task: {s.task_name}

## Specification:
{s.task_spec}

## Required Features:
{chr(10).join(f"- {f}" for f in s.required_features)}
"""
        system = PLANNER_SYSTEM_PROMPT
    else:
        review_text = ""
        if s.review:
            review_text = f"""## Review Feedback:
- Verdict: {s.review.verdict}
- Working features: {', '.join(s.review.working_features) or 'None identified'}
- Missing features: {', '.join(s.review.missing_features) or 'None'}
- Bugs: {', '.join(s.review.bugs) or 'None'}
- Suggestions: {s.review.suggestions}
"""

        test_text = ""
        if s.test_result:
            test_text = f"""## Test Results:
- Exit code: {s.test_result.exit_code}
- Stdout: {s.test_result.stdout[:2000]}
- Stderr: {s.test_result.stderr[:2000]}
"""

        user_prompt = f"""## Task: {s.task_name}

## Original Specification:
{s.task_spec}

## Required Features:
{chr(10).join(f"- {f}" for f in s.required_features)}

## Current Plan:
{s.plan}

{review_text}
{test_text}

Revise the plan to address the issues above.
"""
        system = PLANNER_REVISION_PROMPT

    plan_text, tokens = llm_client.chat(
        system_prompt=system,
        user_prompt=user_prompt,
        caller="planner",
    )

    if s.container_id:
        sandbox.write_file(
            s.container_id,
            f"plan_v{s.iteration}.md",
            plan_text,
        )

    logger.info(f"Plan generated (iteration {s.iteration}, {tokens} tokens)")

    return {
        "plan": plan_text,
        "phase": Phase.CODING,
        "total_tokens_used": s.total_tokens_used + tokens,
    }
