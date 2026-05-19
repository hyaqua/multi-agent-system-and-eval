#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> tuple[str, str, int]:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return r.stdout, r.stderr, r.returncode


def collect_py_files(code_dir: Path) -> list[Path]:
    return sorted(code_dir.rglob("*.py"))

def run_flake8(code_dir: Path) -> dict:
    """Returns error/warning counts and raw issues."""
    stdout, _, _ = run(
        ["flake8", "--format=%(path)s:%(row)d:%(col)d: %(code)s %(text)s",
         "--statistics", "."],
        cwd=code_dir,
    )
    issues = []
    for line in stdout.splitlines():
        line = line.strip()
        if line:
            issues.append(line)

    # Count by category
    errors   = sum(1 for i in issues if ": E" in i)
    warnings = sum(1 for i in issues if ": W" in i)
    style    = sum(1 for i in issues if ": C" in i or ": F" in i)

    return {
        "total_issues": len(issues),
        "errors": errors,
        "warnings": warnings,
        "style": style,
        "issues": issues,
    }


def run_pylint(code_dir: Path, py_files: list[Path]) -> dict:
    if not py_files:
        return {"score": None, "total_issues": 0, "categories": {}, "issues": []}

    rel_files = [str(f.relative_to(code_dir)) for f in py_files]

    # Run 1: get structured issues
    stdout, _, _ = run(
        ["pylint", "--output-format=json", "--score=no"] + rel_files,
        cwd=code_dir,
    )

    issues = []
    try:
        messages = json.loads(stdout)
        for m in messages:
            issues.append({
                "file": m.get("path"),
                "line": m.get("line"),
                "type": m.get("type"),
                "symbol": m.get("symbol"),
                "message": m.get("message"),
            })
    except json.JSONDecodeError:
        pass

    # Run 2: get score from text output
    score = None
    stdout2, _, _ = run(
        ["pylint", "--output-format=text", "--score=yes", "--reports=no"] + rel_files,
        cwd=code_dir,
    )
    for line in stdout2.splitlines():
        if "Your code has been rated at" in line:
            try:
                score = float(line.split(" at ")[1].split("/")[0].strip())
            except (IndexError, ValueError):
                pass
            break

    categories = {}
    for issue in issues:
        t = issue.get("type", "unknown")
        categories[t] = categories.get(t, 0) + 1

    return {
        "score": score,
        "total_issues": len(issues),
        "categories": categories,
        "issues": issues,
    }


def run_radon(code_dir: Path, py_files: list[Path]) -> dict:
    if not py_files:
        return {"avg_complexity": None, "avg_mi": None, "details": []}

    rel_files = [str(f.relative_to(code_dir)) for f in py_files]

    # Cyclomatic complexity
    cc_out, _, _ = run(["radon", "cc", "--json", "-a"] + rel_files, cwd=code_dir)
    mi_out, _, _ = run(["radon", "mi", "--json"] + rel_files, cwd=code_dir)

    # Parse CC
    complexities = []
    try:
        cc_data = json.loads(cc_out)
        for file_blocks in cc_data.values():
            for block in file_blocks:
                complexities.append(block.get("complexity", 0))
    except (json.JSONDecodeError, AttributeError):
        pass

    avg_complexity = (sum(complexities) / len(complexities)) if complexities else None

    # Parse MI
    mi_scores = []
    try:
        mi_data = json.loads(mi_out)
        for file_info in mi_data.values():
            if isinstance(file_info, dict) and "mi" in file_info:
                mi_scores.append(file_info["mi"])
    except (json.JSONDecodeError, AttributeError):
        pass

    avg_mi = (sum(mi_scores) / len(mi_scores)) if mi_scores else None

    return {
        "avg_complexity": round(avg_complexity, 2) if avg_complexity else None,
        "avg_maintainability_index": round(avg_mi, 2) if avg_mi else None,
        "function_count": len(complexities),
        "file_count": len(py_files),
    }


def parse_folder_name(name: str) -> dict:
    parts = name.split("_")
    arch = parts[0] if parts else "unknown"          # multi / single
    run_part = next((p for p in parts if p.startswith("run")), None)
    run_num = int(run_part[3:]) if run_part else None
    # task name is everything between arch and runX
    try:
        run_idx = parts.index(run_part)
        task_parts = parts[1:run_idx]
        # drop leading task number if numeric
        task_name = "_".join(task_parts[1:]) if task_parts[0].isdigit() else "_".join(task_parts)
        task_num = int(task_parts[0]) if task_parts[0].isdigit() else None
    except (ValueError, IndexError):
        task_name = "unknown"
        task_num = None

    return {"architecture": arch, "task_number": task_num,
            "task_name": task_name, "run": run_num}


def find_result_folders(results_dir: Path) -> list[Path]:
    """Find all folders that contain a code/ subdirectory."""
    return sorted(
        p.parent for p in results_dir.rglob("code")
        if p.is_dir() and p.parent != results_dir
    )


def analyze_folder(folder: Path) -> dict:
    code_dir = folder / "code"
    if not code_dir.exists():
        return None

    py_files = collect_py_files(code_dir)
    meta = parse_folder_name(folder.name)

    print(f"  Analyzing {folder.name} ({len(py_files)} .py files)...")

    flake = run_flake8(code_dir)
    pylint = run_pylint(code_dir, py_files)
    radon = run_radon(code_dir, py_files)

    return {
        "folder": folder.name,
        **meta,
        "py_file_count": len(py_files),
        "flake8": flake,
        "pylint": pylint,
        "radon": radon,
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze LLM result folders with static tools")
    parser.add_argument("results_dir", help="Path to the results directory")
    parser.add_argument("--output", default="analysis_results.json",
                        help="Output JSON file (default: analysis_results.json)")
    parser.add_argument("--no-issues", action="store_true",
                        help="Omit individual issue lists from output (smaller file)")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        print(f"Error: {results_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    folders = find_result_folders(results_dir)
    print(f"Found {len(folders)} result folders in {results_dir}\n")

    all_results = []
    for folder in folders:
        result = analyze_folder(folder)
        if result:
            if args.no_issues:
                result["flake8"].pop("issues", None)
                result["pylint"].pop("issues", None)
            all_results.append(result)

    output_path = Path(args.output)
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nFull results written to {output_path}")

    # Print summary table
    print("\n── Summary ─────────────────────────────────────────────────────")
    print(f"{'Folder':<45} {'Arch':<7} {'Run':<4} {'Files':<6} "
          f"{'Flake8':<8} {'Pylint':<8} {'CC':<6} {'MI':<6}")
    print("-" * 100)
    for r in all_results:
        print(
            f"{r['folder'][:44]:<45} "
            f"{r['architecture']:<7} "
            f"{str(r['run']):<4} "
            f"{r['py_file_count']:<6} "
            f"{r['flake8']['total_issues']:<8} "
            f"{str(r['pylint']['score'] or 'N/A'):<8} "
            f"{str(r['radon']['avg_complexity'] or 'N/A'):<6} "
            f"{str(r['radon']['avg_maintainability_index'] or 'N/A'):<6}"
        )


if __name__ == "__main__":
    main()
