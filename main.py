from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel

from config import Config
from state import AgentState, Phase
from graph import build_graph
from tools.sandbox import SandboxManager
from utils.llm_client import LLMClient

console = Console()


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def load_task(task_path: str) -> dict:
    with open(task_path) as f:
        task = json.load(f)

    required_keys = ["name", "spec", "features"]
    for key in required_keys:
        if key not in task:
            raise ValueError(f"Task file missing required key: {key}")

    return task


def save_results(state: dict, output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    s = AgentState(**state)

    # Summary
    summary = {
        "task_name": s.task_name,
        "final_phase": s.phase,
        "total_iterations": s.iteration + 1,
        "total_tokens_used": s.total_tokens_used,
        "duration_seconds": round((s.end_time or time.time()) - s.start_time, 2),
        "num_files": len(s.code_files),
        "iteration_history": s.iteration_history,
        "final_review": s.review.model_dump() if s.review else None,
        "final_test": s.test_result.model_dump() if s.test_result else None,
    }

    with open(os.path.join(output_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)

    code_dir = os.path.abspath(os.path.join(output_dir, "code"))
    os.makedirs(code_dir, exist_ok=True)
    for filepath, content in s.code_files.items():
        # Normalize and strip leading slashes / parent refs
        safe_path = os.path.normpath(filepath).lstrip(os.sep)
        if ".." in safe_path.split(os.sep):
            logging.warning(f"Skipping unsafe path: {filepath}")
            continue
        full_path = os.path.join(code_dir, safe_path)
        # Double-check resolved path is still inside code_dir
        if not os.path.abspath(full_path).startswith(code_dir):
            logging.warning(f"Skipping path escaping results tree: {filepath}")
            continue
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)

    # Save plan
    with open(os.path.join(output_dir, "plan.md"), "w") as f:
        f.write(s.plan)

    console.print(f"\n[green]Results saved to {output_dir}[/green]")


def run_task(task_path: str, config: Config, run_id: str | None = None):
    task = load_task(task_path)
    task_name = task["name"]
    run_id = run_id or f"{task_name}_{int(time.time())}"

    console.print(Panel(f"[bold]Task: {task_name}[/bold]\n{task['spec'][:200]}..."))

    # Initialize components
    llm = LLMClient(config.llm)
    sandbox = SandboxManager(config.docker)

    # Create sandbox container
    container_id = sandbox.create_container()

    try:
        # Build initial state
        initial_state = AgentState(
            task_name=task_name,
            task_spec=task["spec"],
            required_features=task["features"],
            phase=Phase.PLANNING,
            container_id=container_id,
            work_dir="/workspace",
        ).model_dump()

        # Build and run the graph
        graph = build_graph(config, llm, sandbox)

        console.print("[bold blue]Starting agent loop...[/bold blue]\n")

        final_state = None
        for step in graph.stream(initial_state):
            # Log each step
            for node_name, node_output in step.items():
                if node_name == "__end__":
                    continue
                phase = node_output.get("phase", "?")
                tokens = node_output.get("total_tokens_used", "?")
                console.print(
                    f"  [dim]Step:[/dim] {node_name:12s} "
                    f"[dim]→[/dim] phase={phase} "
                    f"[dim]tokens=[/dim]{tokens}"
                )
                final_state = node_output

        # Merge final state
        merged = dict(initial_state)
        if final_state:
            merged.update(final_state)
        merged["end_time"] = time.time()

        # Save results
        output_dir = os.path.join("results", run_id)
        save_results(merged, output_dir)

        # Save LLM call log for thesis analysis
        llm.save_call_log(os.path.join(output_dir, "llm_calls.json"))

        # Print summary
        s = AgentState(**merged)
        console.print(
            Panel(
                f"[bold]Completed: {task_name}[/bold]\n"
                f"Iterations: {s.iteration + 1}\n"
                f"Tokens used: {s.total_tokens_used:,}\n"
                f"Final verdict: {s.review.verdict if s.review else 'N/A'}\n"
                f"Files produced: {len(s.code_files)}\n"
                f"Working features: {len(s.review.working_features) if s.review else 0}/"
                f"{len(s.required_features)}",
                title="Results",
                border_style="green" if s.phase == Phase.DONE else "yellow",
            )
        )

    finally:
        sandbox.destroy_container(container_id)


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Agent Coding System — run a task through the agent loop."
    )
    parser.add_argument(
        "task",
        help="Path to a task JSON file.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="LLM API base URL (overrides config).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name (overrides config).",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key (overrides config).",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Max iterations (overrides config).",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Custom run ID for results directory.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging.",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    # Build config with overrides
    config = Config()
    if args.base_url:
        config.llm.base_url = args.base_url
    if args.model:
        config.llm.model = args.model
    if args.api_key:
        config.llm.api_key = args.api_key
    if args.max_iterations:
        config.agent.max_iterations = args.max_iterations

    run_task(args.task, config, args.run_id)


if __name__ == "__main__":
    main()
