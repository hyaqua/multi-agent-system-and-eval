#!/usr/bin/env python3
"""
Interactive feature checker for LLM code generation results.

For each result folder, shows the task's feature list and lets you
mark each feature as pass/fail. Results are saved to a single JSON file
and the session can be resumed at any time.

Usage:
    python check_features.py <results_dir> <tasks_dir> [--output feature_results.json]

    results_dir : folder containing multi_*/single_* result folders
    tasks_dir   : folder containing the task JSON files (01_todo_manager.json etc.)
"""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path


# ── ANSI colours ─────────────────────────────────────────────────────────────

def green(s):  return f"\033[92m{s}\033[0m"
def red(s):    return f"\033[91m{s}\033[0m"
def yellow(s): return f"\033[93m{s}\033[0m"
def bold(s):   return f"\033[1m{s}\033[0m"
def dim(s):    return f"\033[2m{s}\033[0m"
def cyan(s):   return f"\033[96m{s}\033[0m"


# ── helpers ───────────────────────────────────────────────────────────────────

def clear():
    os.system("cls" if os.name == "nt" else "clear")


def parse_folder_name(name: str) -> dict:
    parts = name.split("_")
    arch = parts[0]  # multi / single
    run_part = next((p for p in parts if p.startswith("run")), None)
    run_num = int(run_part[3:]) if run_part else None
    try:
        run_idx = parts.index(run_part)
        task_parts = parts[1:run_idx]
        task_num = int(task_parts[0]) if task_parts and task_parts[0].isdigit() else None
        task_name = "_".join(task_parts[1:]) if task_num is not None else "_".join(task_parts)
    except (ValueError, IndexError):
        task_num, task_name = None, "unknown"
    return {"architecture": arch, "task_number": task_num,
            "task_name": task_name, "run": run_num}


def find_result_folders(results_dir: Path) -> list[Path]:
    return sorted(
        p.parent for p in results_dir.rglob("code")
        if p.is_dir() and p.parent != results_dir
    )


def load_task_specs(tasks_dir: Path) -> dict:
    """Parse all task JSON files once, return {task_num: spec_dict}."""
    specs = {}
    for f in tasks_dir.glob("*.json"):
        stem = f.stem  # e.g. "01_todo_manager"
        num_part = stem.split("_")[0]
        if not num_part.isdigit():
            continue
        try:
            specs[int(num_part)] = json.loads(f.read_text())
        except (json.JSONDecodeError, ValueError):
            continue
    return specs


def load_results(output_path: Path) -> dict:
    if output_path.exists():
        try:
            return json.loads(output_path.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def save_results(output_path: Path, results: dict):
    output_path.write_text(json.dumps(results, indent=2))


def open_terminal_in_folder(folder: Path):
    """Open an Alacritty window with cwd set to the code folder so the
    user can immediately run the generated Python files. Falls back
    silently if Alacritty isn't installed."""
    code_dir = (folder / "code").resolve()
    if not code_dir.exists():
        return
    if shutil.which("alacritty") is None:
        # Alacritty not on PATH — print a hint once instead of failing loudly.
        print(dim(f"  (alacritty not found on PATH — open {code_dir} manually)"))
        return
    try:
        subprocess.Popen(
            ["alacritty", "--working-directory", str(code_dir)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as e:
        print(dim(f"  (could not launch alacritty: {e})"))


# ── feature checking session ──────────────────────────────────────────────────

def check_folder(folder: Path, meta: dict, spec: dict,
                 existing: dict | None) -> dict:
    """
    Interactive session for one result folder.
    Returns a result dict with feature checks.
    """
    features = spec.get("features", [])
    n = len(features)

    # Pre-fill from existing if resuming. `existing` may be None (new folder)
    # or a dict from a prior session.
    if existing:
        checks = existing.get("feature_checks") or [None] * n
        notes  = existing.get("notes", "") or ""
    else:
        checks = [None] * n
        notes  = ""

    # `feature_checks` from disk is a list of dicts, normalise to list of bool/None
    if checks and isinstance(checks[0], dict):
        checks = [c.get("passed") for c in checks]

    # Pad/trim checks list to match current feature count
    if len(checks) < n:
        checks += [None] * (n - len(checks))
    checks = checks[:n]

    # Open Alacritty ONCE when we enter this folder, not on every redraw.
    code_dir = (folder / "code").resolve()
    open_terminal_in_folder(folder)

    i = 0  # current feature index
    while True:
        clear()

        # ── header ────────────────────────────────────────────────────────
        arch_label = green("MULTI") if meta["architecture"] == "multi" else yellow("SINGLE")
        print(bold(f"  {arch_label}  {meta['task_name']}  run {meta['run']}  "
                   f"({meta['architecture']}_{meta['task_number']:02d}_{meta['task_name']}_run{meta['run']})"))
        print(dim(f"  Difficulty: {spec.get('difficulty', '?')}   "
                  f"Features: {n}   "
                  f"Done: {sum(1 for c in checks if c is not None)}/{n}"))
        print(dim(f"  Code: {code_dir}"))
        print()

        # ── spec summary ──────────────────────────────────────────────────
        spec_text = spec.get("spec", "")
        print(dim("  Spec: ") + spec_text[:120] + ("..." if len(spec_text) > 120 else ""))
        print()

        # ── feature list ──────────────────────────────────────────────────
        print(bold("  Features:"))
        for j, (feat, check) in enumerate(zip(features, checks)):
            if check is True:
                marker = green("✓")
            elif check is False:
                marker = red("✗")
            else:
                marker = dim("·")

            prefix = bold(cyan(f"  ▶ [{j+1}]")) if j == i else f"    [{j+1}]"
            print(f"{prefix} {marker}  {feat}")

        print()

        # ── current feature prompt ────────────────────────────────────────
        current = features[i]
        print(bold(f"  Checking [{i+1}/{n}]: ") + current)
        print()
        print(dim("  Commands: ") +
              green("y") + dim("/") + green("1") + dim(" = pass   ") +
              red("n") + dim("/") + red("0") + dim(" = fail   ") +
              yellow("s") + dim(" = skip   ") +
              cyan("b") + dim(" = back   ") +
              bold("g") + dim(" <num> = jump   ") +
              bold("t") + dim(" = re-open terminal   ") +
              bold("note") + dim(" = add note   ") +
              bold("done") + dim(" = finish   ") +
              bold("q") + dim(" = save & quit"))

        if notes:
            print()
            print(dim(f"  Note: {notes}"))

        print()

        try:
            raw = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n\n  Saving progress and quitting...")
            result = _build_result(meta, spec, features, checks, notes, complete=False)
            result["_quit"] = True
            return result

        if raw in ("y", "1", "yes"):
            was_complete = all(c is not None for c in checks)
            checks[i] = True
            i = _next_unchecked(checks, i, n)
            just_completed = not was_complete and all(c is not None for c in checks)

        elif raw in ("n", "0", "no"):
            was_complete = all(c is not None for c in checks)
            checks[i] = False
            i = _next_unchecked(checks, i, n)
            just_completed = not was_complete and all(c is not None for c in checks)

        elif raw in ("s", "skip"):
            i = min(i + 1, n - 1)
            just_completed = False

        elif raw in ("b", "back"):
            i = max(i - 1, 0)
            just_completed = False

        elif raw.startswith("g "):
            try:
                target = int(raw.split()[1]) - 1
                if 0 <= target < n:
                    i = target
            except (ValueError, IndexError):
                pass
            just_completed = False

        elif raw == "t":
            # Manually re-open the terminal if the user closed it.
            open_terminal_in_folder(folder)
            just_completed = False

        elif raw == "note":
            print("  Enter note (blank to clear): ", end="", flush=True)
            try:
                notes = input().strip()
            except (EOFError, KeyboardInterrupt):
                pass
            just_completed = False

        elif raw in ("done", "d"):
            complete = all(c is not None for c in checks)
            return _build_result(meta, spec, features, checks, notes, complete=complete)

        elif raw in ("q", "quit"):
            result = _build_result(meta, spec, features, checks, notes, complete=False)
            result["_quit"] = True
            return result

        else:
            # Unknown command — just redraw, don't trigger summary
            just_completed = False

        # Show summary only when the user JUST finished the last feature
        # (not every time we're in an all-checked state, or 'back' would re-trap)
        if just_completed:
            clear()
            print(bold("\n  All features checked!"))
            for j, (feat, check) in enumerate(zip(features, checks)):
                marker = green("✓") if check else red("✗")
                print(f"    [{j+1}] {marker}  {feat}")
            passed = sum(1 for c in checks if c is True)
            print(f"\n  Score: {passed}/{n} ({100*passed//n}%)")
            print(dim("\n  Press Enter to save and continue, or 'b' to go back: "), end="", flush=True)
            try:
                ans = input().strip().lower()
            except (EOFError, KeyboardInterrupt):
                ans = ""
            if ans == "b":
                i = n - 1
            else:
                return _build_result(meta, spec, features, checks, notes, complete=True)


def _next_unchecked(checks: list, current: int, n: int) -> int:
    """Return index of next unchecked feature after `current`, or stay if none."""
    for j in range(current + 1, n):
        if checks[j] is None:
            return j
    # fall through: just step forward by one if possible
    return min(current + 1, n - 1)


def _build_result(meta, spec, features, checks, notes, complete):
    passed = sum(1 for c in checks if c is True)
    total  = len(features)
    checked = sum(1 for c in checks if c is not None)
    return {
        "folder": f"{meta['architecture']}_{meta['task_number']:02d}_{meta['task_name']}_run{meta['run']}",
        "architecture": meta["architecture"],
        "task_number": meta["task_number"],
        "task_name": meta["task_name"],
        "task_difficulty": spec.get("difficulty"),
        "run": meta["run"],
        "complete": complete,
        "features_total": total,
        "features_checked": checked,
        "features_passed": passed,
        "features_failed": sum(1 for c in checks if c is False),
        "feature_score_pct": round(100 * passed / total, 1) if total else None,
        "notes": notes,
        "feature_checks": [
            {"feature": feat, "passed": check}
            for feat, check in zip(features, checks)
        ],
    }


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Interactive feature checker")
    parser.add_argument("results_dir", help="Path to results directory")
    parser.add_argument("tasks_dir",   help="Path to task JSON files directory")
    parser.add_argument("--output", default="feature_results.json")
    parser.add_argument("--only", help="Only check folders matching this substring")
    parser.add_argument("--incomplete", action="store_true",
                        help="Only show folders not yet fully checked")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    tasks_dir   = Path(args.tasks_dir)
    output_path = Path(args.output)

    folders = find_result_folders(results_dir)
    if args.only:
        folders = [f for f in folders if args.only in f.name]

    specs_by_num = load_task_specs(tasks_dir)
    saved = load_results(output_path)

    if args.incomplete:
        folders = [f for f in folders
                   if not saved.get(f.name, {}).get("complete", False)]

    total = len(folders)
    print(bold(f"\n  Feature checker — {total} folders to process"))
    print(dim(f"  Output: {output_path.resolve()}\n"))

    if total == 0:
        print("  Nothing to check. All done!")
        return

    for idx, folder in enumerate(folders):
        meta = parse_folder_name(folder.name)

        if meta["task_number"] is None or meta["run"] is None:
            print(yellow(f"  Skipping {folder.name} — could not parse folder name"))
            continue

        spec = specs_by_num.get(meta["task_number"])

        if spec is None:
            print(yellow(f"  Skipping {folder.name} — no matching task spec found"))
            continue

        existing = saved.get(folder.name)

        # Skip already completed unless --incomplete flag is set
        if existing and existing.get("complete") and not args.incomplete:
            print(dim(f"  [{idx+1}/{total}] {folder.name} — already complete, skipping"))
            continue

        result = check_folder(folder, meta, spec, existing)
        quit_requested = result.pop("_quit", False)
        saved[folder.name] = result
        save_results(output_path, saved)

        if quit_requested:
            print(bold("\n  Progress saved. Resume anytime with the same command."))
            print(dim(f"  Tip: use --incomplete to skip already-finished folders."))
            return

        completed = sum(1 for v in saved.values() if v.get("complete"))
        print(dim(f"\n  Saved. Progress: {completed}/{total} complete."))

    # Final summary
    clear()
    completed = [v for v in saved.values() if v.get("complete")]
    print(bold(f"\n  Session complete — {len(completed)}/{total} folders checked\n"))

    if completed:
        avg = sum(r["feature_score_pct"] for r in completed
                  if r["feature_score_pct"] is not None) / len(completed)
        multi  = [r for r in completed if r["architecture"] == "multi"]
        single = [r for r in completed if r["architecture"] == "single"]
        avg_m  = sum(r["feature_score_pct"] for r in multi)  / len(multi)  if multi  else 0
        avg_s  = sum(r["feature_score_pct"] for r in single) / len(single) if single else 0
        print(f"  Overall avg feature score : {avg:.1f}%")
        print(f"  Multi-agent avg           : {green(f'{avg_m:.1f}%')}")
        print(f"  Single-agent avg          : {yellow(f'{avg_s:.1f}%')}")

    print(dim(f"\n  Full results: {output_path.resolve()}\n"))


if __name__ == "__main__":
    main()