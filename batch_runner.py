"""
Batch runner.

Runs all tasks in a directory (optionally multiple times each)
and collects results for thesis analysis. Supports running both
multi-agent and single-agent systems for comparison.
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import time

from rich.console import Console
from rich.table import Table

from config import Config
from main import run_task, setup_logging
from single_agent import run_single_agent

console = Console()


def run_batch(
    tasks_dir: str,
    config: Config,
    runs_per_task: int = 1,
    systems: list[str] | None = None,
):
    """
    Run all task files with the specified systems.

    Args:
        systems: List of systems to run. Options: "multi", "single", or both.
                 Defaults to both.
    """
    systems = systems or ["multi", "single"]
    task_files = sorted(glob.glob(os.path.join(tasks_dir, "*.json")))

    if not task_files:
        console.print(f"[red]No task files found in {tasks_dir}[/red]")
        return

    total_runs = len(task_files) * runs_per_task * len(systems)
    console.print(
        f"[bold]Batch run: {len(task_files)} tasks × {runs_per_task} runs × "
        f"{len(systems)} systems = {total_runs} total runs[/bold]\n"
    )

    results = []

    for task_path in task_files:
        task_name = os.path.splitext(os.path.basename(task_path))[0]

        for system in systems:
            for run_num in range(runs_per_task):
                run_id = f"{system}_{task_name}_run{run_num}_{int(time.time())}"
                console.print(
                    f"\n[bold cyan]═══ [{system.upper()}] {task_name} "
                    f"(run {run_num + 1}/{runs_per_task}) ═══[/bold cyan]"
                )

                try:
                    if system == "multi":
                        run_task(task_path, config, run_id)
                    elif system == "single":
                        run_single_agent(task_path, config, run_id)
                    else:
                        console.print(f"[red]Unknown system: {system}[/red]")
                        continue

                    # Load the saved summary
                    summary_path = os.path.join("results", run_id, "summary.json")
                    if os.path.exists(summary_path):
                        with open(summary_path) as f:
                            summary = json.load(f)
                        summary["run_id"] = run_id
                        summary["system"] = system
                        results.append(summary)

                except Exception as e:
                    console.print(
                        f"[red]FAILED: [{system}] {task_name} run {run_num}: {e}[/red]"
                    )
                    results.append({
                        "task_name": task_name,
                        "system": system,
                        "run_id": run_id,
                        "error": str(e),
                    })

    # Save batch results
    batch_id = f"batch_{int(time.time())}"
    os.makedirs(f"results/{batch_id}", exist_ok=True)
    with open(f"results/{batch_id}/all_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    # Print summary table
    _print_summary_table(results)

    console.print(f"\n[green]Batch results saved to results/{batch_id}/[/green]")


def _print_summary_table(results: list[dict]):
    """Print a rich table summarizing all runs."""
    table = Table(title="Batch Results Summary")
    table.add_column("System", style="bold")
    table.add_column("Task", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Iterations", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Features", justify="right")

    for r in results:
        system = r.get("system", "?")
        system_style = "blue" if system == "multi" else "magenta"

        if "error" in r:
            table.add_row(
                f"[{system_style}]{system}[/{system_style}]",
                r["task_name"],
                "[red]ERROR[/red]",
                "-", "-", "-", "-",
            )
            continue

        # Handle both multi-agent and single-agent result formats
        if system == "multi":
            verdict = r.get("final_review", {}).get("verdict", "?")
            working = len(r.get("final_review", {}).get("working_features", []))
            missing = len(r.get("final_review", {}).get("missing_features", []))
            total_features = working + missing
            status = verdict
        else:
            status = r.get("final_status", "?")
            total_features = 0
            working = 0

        status_style = "green" if status in ("approve", "complete") else "yellow"

        table.add_row(
            f"[{system_style}]{system}[/{system_style}]",
            r["task_name"],
            f"[{status_style}]{status}[/{status_style}]",
            str(r.get("total_iterations", "?")),
            f"{r.get('total_tokens_used', 0):,}",
            f"{r.get('duration_seconds', 0):.1f}s",
            f"{working}/{total_features}" if total_features > 0 else "-",
        )

    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="Batch runner — run tasks with multi-agent and/or single-agent systems."
    )
    parser.add_argument(
        "--tasks-dir",
        default="tasks",
        help="Directory containing task JSON files.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of runs per task per system (for consistency analysis).",
    )
    parser.add_argument(
        "--system",
        choices=["multi", "single", "both"],
        default="both",
        help="Which system(s) to run. Default: both.",
    )
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--max-iterations", type=int, default=None)
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

    if args.system == "both":
        systems = ["multi", "single"]
    else:
        systems = [args.system]

    run_batch(args.tasks_dir, config, args.runs, systems)


if __name__ == "__main__":
    main()
