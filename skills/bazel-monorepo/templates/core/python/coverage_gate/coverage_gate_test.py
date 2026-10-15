from __future__ import annotations

from typing import TYPE_CHECKING

from coverage_gate.coverage_gate import (
    REPORT,
    SKIP_VARIABLE,
    coverage_command,
    diff_cover_arguments,
    main,
    report_has_records,
)
from proc.proc import Outcome
from proc.testutil.testutil import FakeRunner

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

ARGS = ["--threshold", "95", "--compare-branch", "origin/main", "--targets", "//..."]


def test_coverage_command_runs_from_the_workspace() -> None:
    command = coverage_command("//... -//skip/...", "/repo")
    assert command.argv == ("bazel", "coverage", "//...", "-//skip/...")
    assert command.cwd == "/repo"
    assert command.interactive


def test_diff_cover_arguments_name_the_threshold_and_branch() -> None:
    assert diff_cover_arguments("r.dat", "origin/main", 95) == [
        "diff-cover",
        "r.dat",
        "--compare-branch=origin/main",
        "--config-file=pyproject.toml",
        "--fail-under=95",
    ]


def test_report_has_records_needs_a_source_file_line(tmp_path: Path) -> None:
    empty = tmp_path / "empty.dat"
    empty.write_text("TN:\n")
    full = tmp_path / "full.dat"
    full.write_text("TN:\nSF:python/x.py\nend_of_record\n")
    assert not report_has_records(tmp_path / "missing.dat")
    assert not report_has_records(empty)
    assert report_has_records(full)


def test_skip_variable_short_circuits() -> None:
    runner = FakeRunner()
    messages: list[str] = []
    status = main(ARGS, {SKIP_VARIABLE: "1"}, runner, lambda _: 7, messages.append)
    assert status == 0
    assert runner.commands == []
    assert "SKIPPED" in messages[0]


def test_outside_bazel_run_is_an_error() -> None:
    messages: list[str] = []
    status = main(ARGS, {}, FakeRunner(), lambda _: 0, messages.append)
    assert status == 1
    assert "BUILD_WORKSPACE_DIRECTORY" in messages[0]


def test_failed_coverage_run_returns_its_status(tmp_path: Path) -> None:
    runner = FakeRunner([Outcome(status=3)])
    status = main(
        ARGS,
        {"BUILD_WORKSPACE_DIRECTORY": str(tmp_path)},
        runner,
        lambda _: 0,
        lambda _: None,
    )
    assert status == 3
    assert runner.argvs == [("bazel", "coverage", "//...")]


def test_empty_report_fails_before_diff_cover(tmp_path: Path) -> None:
    messages: list[str] = []
    status = main(
        ARGS,
        {"BUILD_WORKSPACE_DIRECTORY": str(tmp_path)},
        FakeRunner(),
        lambda _: 0,
        messages.append,
    )
    assert status == 1
    assert "missing or empty" in messages[0]


def test_verdict_is_diff_covers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = tmp_path / REPORT
    report.parent.mkdir(parents=True)
    report.write_text("SF:python/x.py\nend_of_record\n")
    received: list[list[str]] = []

    def fake_diff_cover(arguments: list[str]) -> int:
        received.append(arguments)
        return 2

    monkeypatch.chdir(tmp_path)
    status = main(
        ARGS,
        {"BUILD_WORKSPACE_DIRECTORY": str(tmp_path)},
        FakeRunner(),
        fake_diff_cover,
        lambda _: None,
    )
    assert status == 2
    assert received == [diff_cover_arguments(REPORT, "origin/main", 95)]
