"""The patch-coverage gate (docs/conventions/gates.md).

The chain: honor the skip variable, run `bazel coverage` from the workspace
root, refuse a merged lcov report with no records, then hand the report to
diff-cover, which fails when the changed lines against the compare branch
are covered below the threshold. The exit code is the verdict: zero
passes, non-zero fails.

diff-cover runs in-process, as a library, so its exit status cannot be
lost between processes. The planning functions below build the commands
and arguments; `main` executes them through the runner it is handed.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from proc.proc import Command, Runner

SKIP_VARIABLE = "{{ENV_PREFIX}}_SKIP_COVERAGE_GATE"
REPORT = "bazel-out/_coverage/_coverage_report.dat"

EMPTY_REPORT_MESSAGE = f"""\
coverage gate: the merged coverage report ({REPORT}) is missing or empty.
coverage gate: this is a known failure mode after a Bazel or toolchain
coverage gate: upgrade: bazel coverage exits green but records nothing.
coverage gate: Coverage itself is broken; fix that before trusting any
coverage gate: patch-coverage verdict."""

DiffCover = Callable[[list[str]], int]
Report = Callable[[str], None]


def to_stderr(message: str) -> None:
    """The default `report`: diagnostics go to stderr, results to stdout."""
    print(message, file=sys.stderr)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parses the gate's arguments.

    Args:
        argv: `--threshold N --compare-branch REF --targets PATTERNS`.

    Returns:
        A namespace with `threshold` (int), `compare_branch` and `targets`.

    Raises:
        SystemExit: From argparse, when an argument is missing or malformed.
    """
    parser = argparse.ArgumentParser(prog="coverage_gate")
    parser.add_argument("--threshold", type=int, required=True)
    parser.add_argument("--compare-branch", required=True)
    parser.add_argument("--targets", required=True)
    return parser.parse_args(argv)


def coverage_command(targets: str, workspace: str) -> Command:
    """The `bazel coverage` invocation over `targets`, run from the workspace root."""
    return Command(
        argv=("bazel", "coverage", *targets.split()), cwd=workspace, interactive=True
    )


def diff_cover_arguments(report: str, compare_branch: str, threshold: int) -> list[str]:
    """The argument list diff-cover's `main` accepts, program name first."""
    return [
        "diff-cover",
        report,
        f"--compare-branch={compare_branch}",
        "--config-file=pyproject.toml",
        f"--fail-under={threshold}",
    ]


def report_has_records(path: Path) -> bool:
    """True if the lcov report at `path` names at least one source file."""
    try:
        with path.open(encoding="utf-8", errors="replace") as report:
            return any(line.startswith("SF:") for line in report)
    except OSError:
        return False


def main(
    argv: Sequence[str],
    env: Mapping[str, str],
    run: Runner,
    diff_cover: DiffCover,
    report: Report = to_stderr,
) -> int:
    """Runs the gate and returns its verdict as an exit status.

    Args:
        argv: The gate's arguments, see `parse_args`.
        env: The process environment; `BUILD_WORKSPACE_DIRECTORY` locates the
            repository and the skip variable turns the gate off.
        run: Executes commands; `run_subprocess` in production.
        diff_cover: diff-cover's `main`; a fake in tests.
        report: Where diagnostics go.

    Returns:
        Zero when the gate passes or is skipped; the failing step's status
        otherwise.
    """
    args = parse_args(argv)
    if env.get(SKIP_VARIABLE):
        report(
            f"coverage gate: SKIPPED because {SKIP_VARIABLE} is set.\n"
            "coverage gate: an escape hatch, visible when used, never routine.",
        )
        return 0
    workspace = env.get("BUILD_WORKSPACE_DIRECTORY")
    if not workspace:
        report(
            "coverage gate: BUILD_WORKSPACE_DIRECTORY is unset; invoke via bazel run."
        )
        return 1
    coverage = run(coverage_command(args.targets, workspace))
    if not coverage.ok:
        return coverage.status
    if not report_has_records(Path(workspace) / REPORT):
        report(EMPTY_REPORT_MESSAGE)
        return 1
    os.chdir(workspace)
    return diff_cover(diff_cover_arguments(REPORT, args.compare_branch, args.threshold))
