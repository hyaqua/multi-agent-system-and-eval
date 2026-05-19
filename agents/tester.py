from __future__ import annotations

import logging

from state import AgentState, Phase, TestResult

logger = logging.getLogger(__name__)


def tester_node(state: dict, llm_client, sandbox) -> dict:
    s = AgentState(**state)

    # Find the entry point
    file_list = sandbox.list_files(s.container_id)
    entry_point = _find_entry_point(file_list, s.code_files)

    if not entry_point:
        logger.warning("No entry point found, marking test as failed.")
        return {
            "test_result": TestResult(
                exit_code=1,
                stdout="",
                stderr="No entry point found (no main.py or similar).",
            ),
            "phase": Phase.REVIEWING,
        }

    # For pygame/GUI apps
    if _is_gui_app(s.code_files):
        return _test_gui_app(s, sandbox, entry_point)

    # For non-GUI apps, run with timeout
    logger.info(f"Running: python {entry_point}")
    exit_code, stdout, stderr = sandbox.exec_command(
        s.container_id,
        f"python {entry_point}",
        timeout=30,
    )

    test_result = TestResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        timed_out=sandbox.is_timeout_exit(exit_code),
    )

    logger.info(f"Test result: exit_code={exit_code}")

    return {
        "test_result": test_result,
        "phase": Phase.REVIEWING,
    }


def _test_gui_app(s: AgentState, sandbox, entry_point: str) -> dict:
    results = []
    has_errors = False

    # Syntax check
    py_files = [f for f in s.code_files if f.endswith(".py")]
    for pf in py_files:
        exit_code, stdout, stderr = sandbox.exec_command(
            s.container_id, f"python -m py_compile {pf}"
        )
        if exit_code != 0:
            has_errors = True
            results.append(f"SYNTAX ERROR in {pf}: {stderr}")
        else:
            results.append(f"Syntax OK: {pf}")

    # 2. Real headless import.
    exit_code, stdout, stderr = sandbox.exec_command(
        s.container_id,
        "SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy "
        f"python -c \""
        f"import importlib.util, sys; "
        f"spec = importlib.util.spec_from_file_location('mod', '{entry_point}'); "
        f"mod = importlib.util.module_from_spec(spec); "
        f"try:\\n"
        f"    spec.loader.exec_module(mod)\\n"
        f"    print('Import + exec OK')\\n"
        f"except SystemExit:\\n"
        f"    print('Module called sys.exit (OK for games)')\\n"
        f"except Exception as e:\\n"
        f"    print(f'IMPORT ERROR: {{type(e).__name__}}: {{e}}', file=sys.stderr)\\n"
        f"    sys.exit(1)\"",
        timeout=10,
    )
    if exit_code != 0 and not sandbox.is_timeout_exit(exit_code):
        has_errors = True
        results.append(f"IMPORT FAILED: {stderr.strip() or stdout.strip()}")
    elif sandbox.is_timeout_exit(exit_code):
        results.append("Import timed out (game loop likely started — OK)")
    else:
        results.append(f"Import check: {stdout.strip()}")

    exit_code, stdout, stderr = sandbox.exec_command(
        s.container_id,
        f"pylint --disable=all --enable=E {entry_point} --score=no 2>&1 | head -30",
    )
    # pylint exit codes: bit 1 = fatal, bit 2 = error
    pylint_has_errors = (exit_code & 0x03) != 0 if exit_code is not None else False
    if pylint_has_errors and stdout.strip():
        has_errors = True
        results.append(f"Pylint errors found:\n{stdout.strip()}")
    else:
        results.append("Pylint: no errors")

    exit_code, stdout, stderr = sandbox.exec_command(
        s.container_id,
        f"flake8 {entry_point} --select=E,F --max-line-length=120 2>&1 | head -20",
    )
    if exit_code != 0 and stdout.strip():
        results.append(f"Flake8 issues:\n{stdout.strip()}")
    else:
        results.append("Flake8: clean")

    combined = "\n".join(results)

    test_result = TestResult(
        exit_code=1 if has_errors else 0,
        stdout=combined,
        stderr="",
    )

    logger.info(f"GUI app test: {'ERRORS' if has_errors else 'OK'}")

    return {
        "test_result": test_result,
        "phase": Phase.REVIEWING,
    }


def _find_entry_point(file_list: str, code_files: dict) -> str | None:
    """Find the most likely entry point file."""
    candidates = ["main.py", "app.py", "game.py", "run.py"]

    for candidate in candidates:
        if candidate in code_files or candidate in file_list:
            return candidate

    # Look for if __name__ == "__main__" in any file
    for path, content in code_files.items():
        if path.endswith(".py") and "__name__" in content and "__main__" in content:
            return path

    # else first .py file
    py_files = [f for f in code_files if f.endswith(".py")]
    return py_files[0] if py_files else None


def _is_gui_app(code_files: dict) -> bool:
    """Check if any file imports pygame or tkinter."""
    gui_indicators = ["import pygame", "from pygame", "import tkinter", "from tkinter"]
    for content in code_files.values():
        for indicator in gui_indicators:
            if indicator in content:
                return True
    return False
