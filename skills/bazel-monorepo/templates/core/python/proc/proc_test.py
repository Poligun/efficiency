from __future__ import annotations

import sys
from pathlib import Path

from proc.proc import NOT_FOUND_STATUS, Command, Outcome, run_subprocess


def test_outcome_ok_is_status_zero() -> None:
    assert Outcome(status=0).ok
    assert not Outcome(status=2).ok


def test_run_subprocess_captures_output_and_status() -> None:
    command = Command(
        argv=(
            sys.executable,
            "-c",
            "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)",
        ),
    )
    outcome = run_subprocess(command)
    assert outcome.status == 3
    assert outcome.stdout == "out\n"
    assert outcome.stderr == "err\n"


def test_run_subprocess_feeds_stdin_and_env() -> None:
    command = Command(
        argv=(
            sys.executable,
            "-c",
            "import os, sys; print(sys.stdin.read() + os.environ['PROC_PROBE'])",
        ),
        stdin="in:",
        env={"PROC_PROBE": "set"},
    )
    outcome = run_subprocess(command)
    assert outcome.ok
    assert outcome.stdout == "in:set\n"


def test_run_subprocess_honors_cwd(tmp_path: Path) -> None:
    command = Command(
        argv=(sys.executable, "-c", "import os; print(os.getcwd())"),
        cwd=str(tmp_path),
    )
    outcome = run_subprocess(command)
    assert outcome.ok
    assert Path(outcome.stdout.strip()).resolve() == tmp_path.resolve()


def test_run_subprocess_interactive_captures_nothing() -> None:
    command = Command(argv=(sys.executable, "-c", "pass"), interactive=True)
    outcome = run_subprocess(command)
    assert outcome.ok
    assert outcome.stdout == ""
    assert outcome.stderr == ""


def test_run_subprocess_reports_a_missing_program_as_an_outcome() -> None:
    outcome = run_subprocess(Command(argv=("/nonexistent/program",)))
    assert outcome.status == NOT_FOUND_STATUS
    assert outcome.stderr.startswith("/nonexistent/program: ")
