from __future__ import annotations

import argparse
import json
import logging
import os
import time

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel

from config import Config
from tools.sandbox import SandboxManager
from tools.shared_tools import TOOLS, execute_tool_call
from utils.llm_client import LLMClient

console = Console()

# --- The single agent's system prompt ---

SINGLE_AGENT_SYSTEM_PROMPT = """\
You are an expert Python developer. You will receive a task specification
with a list of required features. Your job is to implement the complete
project from scratch, test it, and make sure all features work.

You have tools available: write_file, edit_file, bash, and read_file.

Your workflow:
1. Think about the architecture and plan your approach.
2. Write the code files using write_file.
3. Run the code with bash to test it.
4. Read and fix any errors.
5. Verify each required feature works.

Rules:
- Write complete, working Python code. No placeholders or TODOs.
- Create ALL files needed for the project.
- After writing files, run the code to verify it works.
- If you need external packages, install them with pip first.
- For games using pygame, include a main entry point that runs the game.
- Handle errors gracefully.
- Use edit_file for small targeted changes to existing files.
- Use write_file when creating new files or rewriting entire files.

When you believe all features are implemented and working, write a progress
report by calling write_file with path "progress.md" containing:
- Which features are implemented and working
- Which features are still missing or broken
- What you tried and what issues remain

If all features are working, start your progress report with "STATUS: COMPLETE".
If there are still issues, start with "STATUS: IN PROGRESS".
"""


def load_task(task_path: str) -> dict:
    with open(task_path) as f:
        task = json.load(f)
    for key in ["name", "spec", "features"]:
        if key not in task:
            raise ValueError(f"Task file missing required key: {key}")
    return task


def save_results(
    task_name: str,
    code_files: dict,
    total_tokens: int,
    iterations: int,
    iteration_history: list[dict],
    duration: float,
    final_status: str,
    output_dir: str,
):
    os.makedirs(output_dir, exist_ok=True)

    summary = {
        "task_name": task_name,
        "system": "single_agent",
        "final_status": final_status,
        "total_iterations": iterations,
        "total_tokens_used": total_tokens,
        "duration_seconds": round(duration, 2),
        "num_files": len(code_files),
        "iteration_history": iteration_history,
    }

    with open(os.path.join(output_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    # Save code files (with path sanitization)
    code_dir = os.path.abspath(os.path.join(output_dir, "code"))
    os.makedirs(code_dir, exist_ok=True)
    for filepath, content in code_files.items():
        safe_path = os.path.normpath(filepath).lstrip(os.sep)
        if ".." in safe_path.split(os.sep):
            continue
        full_path = os.path.join(code_dir, safe_path)
        if not os.path.abspath(full_path).startswith(code_dir):
            continue
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)

    console.print(f"\n[green]Results saved to {output_dir}[/green]")


def run_single_agent(task_path: str, config: Config, run_id: str | None = None):
    task = load_task(task_path)
    task_name = task["name"]
    run_id = run_id or f"single_{task_name}_{int(time.time())}"

    console.print(Panel(
        f"[bold]Single Agent — Task: {task_name}[/bold]\n{task['spec'][:200]}...",
        border_style="blue",
    ))

    # Initialize
    llm = LLMClient(config.llm)
    sandbox = SandboxManager(config.docker)
    container_id = sandbox.create_container()

    start_time = time.time()
    code_files: dict[str, str] = {}
    total_tokens = 0
    iteration_history = []
    final_status = "incomplete"

    try:
        # Build initial prompt
        features_text = "\n".join(f"- {f}" for f in task["features"])
        user_prompt = f"""## Task: {task_name}

## Specification:
{task['spec']}

## Required Features (all must be implemented):
{features_text}

Implement this project now. Create all necessary files, test the code,
and make sure every required feature works. Write a progress.md report
when you've completed a pass through all features.
"""

        messages = [
            {"role": "system", "content": SINGLE_AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # Main agent loop
        max_iterations = config.agent.max_iterations
        max_tool_rounds_per_iter = 30  # generous budget per iteration
        iteration = 0

        for iteration in range(max_iterations):
            console.print(
                f"\n[bold cyan]── Iteration {iteration + 1}/{max_iterations} ──[/bold cyan]"
            )

            has_written_files = False
            tool_rounds_this_iter = 0

            # Tool use loop within this iteration
            for round_num in range(max_tool_rounds_per_iter):
                # Check token budget
                if total_tokens >= config.agent.max_total_tokens:
                    console.print("[yellow]Token budget exceeded. Stopping.[/yellow]")
                    final_status = "token_limit"
                    break

                try:
                    response, tokens = llm.chat_with_tools(
                        messages=messages,
                        tools=TOOLS,
                        caller="single_agent",
                    )
                    total_tokens += tokens
                except Exception as e:
                    logger.error(f"LLM call failed: {e}")
                    break

                tool_calls = response.choices[0].message.tool_calls

                if not tool_calls:
                    # No tool calls — model is done with this round
                    if not has_written_files and round_num == 0:
                        # Nudge it to use tools
                        messages.append(response.choices[0].message)
                        messages.append({
                            "role": "user",
                            "content": (
                                "You need to use the provided tools to write files. "
                                "Please call write_file to create the project files."
                            ),
                        })
                        continue
                    # Model sent a text-only response, add it and break
                    messages.append(response.choices[0].message)
                    break

                # Execute tool calls
                messages.append(response.choices[0].message)

                for tc in tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": "Error: invalid JSON in tool arguments.",
                        })
                        continue

                    result, code_files = execute_tool_call(
                        name=tc.function.name,
                        arguments=args,
                        container_id=container_id,
                        sandbox=sandbox,
                        code_files=code_files,
                    )

                    if tc.function.name in ("write_file", "edit_file"):
                        has_written_files = True

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

                tool_rounds_this_iter += 1

            # Check if the agent wrote a progress report
            progress = sandbox.read_file(container_id, "progress.md")

            iter_snapshot = {
                "iteration": iteration,
                "tool_rounds": tool_rounds_this_iter,
                "tokens_so_far": total_tokens,
                "num_files": len(code_files),
                "has_progress_report": progress is not None,
            }

            if progress:
                iter_snapshot["status"] = (
                    "complete" if "STATUS: COMPLETE" in progress else "in_progress"
                )
                console.print(f"  Progress report: {iter_snapshot['status']}")

                if "STATUS: COMPLETE" in progress:
                    final_status = "complete"
                    iteration_history.append(iter_snapshot)
                    console.print("[green]Agent declared task complete.[/green]")
                    break

            iteration_history.append(iter_snapshot)

            # If token limit was hit, stop
            if total_tokens >= config.agent.max_total_tokens:
                final_status = "token_limit"
                break

            # Prompt next iteration — ask agent to review and continue
            messages.append({
                "role": "user",
                "content": (
                    "Review your progress. Check which required features are still "
                    "missing or broken, fix them, and update progress.md. "
                    "If everything works, set STATUS: COMPLETE in progress.md."
                ),
            })

        else:
            final_status = "max_iterations"

        duration = time.time() - start_time

        # Save results
        output_dir = os.path.join("results", run_id)
        save_results(
            task_name=task_name,
            code_files=code_files,
            total_tokens=total_tokens,
            iterations=iteration + 1,
            iteration_history=iteration_history,
            duration=duration,
            final_status=final_status,
            output_dir=output_dir,
        )

        # Save LLM call log for thesis analysis
        llm.save_call_log(os.path.join(output_dir, "llm_calls.json"))

        # Print summary
        console.print(
            Panel(
                f"[bold]Completed: {task_name}[/bold]\n"
                f"Status: {final_status}\n"
                f"Iterations: {iteration + 1}\n"
                f"Tokens used: {total_tokens:,}\n"
                f"Files produced: {len(code_files)}\n"
                f"Duration: {duration:.1f}s",
                title="Single Agent Results",
                border_style="green" if final_status == "complete" else "yellow",
            )
        )

    finally:
        sandbox.destroy_container(container_id)


logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def main():
    parser = argparse.ArgumentParser(
        description="Single-Agent Baseline — run a task with one agent."
    )
    parser.add_argument("task", help="Path to a task JSON file.")
    parser.add_argument("--base-url", default=None, help="LLM API base URL.")
    parser.add_argument("--model", default=None, help="Model name.")
    parser.add_argument("--api-key", default=None, help="API key.")
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--run-id", default=None, help="Custom run ID.")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()
    setup_logging(args.verbose)

    config = Config()
    if args.base_url:
        config.llm.base_url = args.base_url
    if args.model:
        config.llm.model = args.model
    if args.api_key:
        config.llm.api_key = args.api_key
    if args.max_iterations:
        config.agent.max_iterations = args.max_iterations

    run_single_agent(args.task, config, args.run_id)


if __name__ == "__main__":
    main()
