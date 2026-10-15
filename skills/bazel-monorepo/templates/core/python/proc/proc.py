"""The one process seam of the Python programs (docs/conventions/python.md).

Every verb of every program plans its work as `Command` values and hands
them to a `Runner`. `run_subprocess` is the production runner; tests pass
a recording fake (`proc.testutil.testutil.FakeRunner`) and assert on the
commands it received, so no test spawns a real process.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

# The shell's status for a program that could not be started; a verb's own
# failure branch then names the tool and its install hint.
NOT_FOUND_STATUS = 127


@dataclass(frozen=True)
class Command:
    """One process to run.

    Attributes:
        argv: The program and its arguments, never a shell string.
        stdin: Text fed to the process, or None to inherit the caller's stdin.
        env: Variables added to (or overriding) the inherited environment.
        interactive: When true the process inherits stdout and stderr, for
            editors and prompts; otherwise both are captured into the Outcome.
        cwd: The working directory, or None to inherit the caller's. `bazel
            run` starts a program inside the runfiles tree, so anything that
            names a repository file relatively runs from the repository root
            (BUILD_WORKSPACE_DIRECTORY) instead.
    """

    argv: tuple[str, ...]
    stdin: str | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    interactive: bool = False
    cwd: str | None = None


@dataclass(frozen=True)
class Outcome:
    """What a process left behind.

    Attributes:
        status: The exit status; zero is success.
        stdout: Captured standard output, empty for interactive commands.
        stderr: Captured standard error, empty for interactive commands.
    """

    status: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        """True when the process exited with status zero."""
        return self.status == 0


Runner = Callable[[Command], Outcome]


def run_subprocess(command: Command) -> Outcome:
    """Runs `command` as a child process and returns its outcome.

    Args:
        command: What to run. Its `argv` is passed as an argument list, so
            no shell is involved and nothing is re-parsed.

    Returns:
        The exit status and, unless the command is interactive, its output.
        A program that cannot be started (missing from PATH, not executable)
        is an outcome with status 127 and the reason on stderr, never an
        exception, so every verb reports it the way it reports any failure.
    """
    env = {**os.environ, **command.env} if command.env else None
    try:
        completed = subprocess.run(  # noqa: S603  # argv is a fixed list built by the planners, never user text
            list(command.argv),
            input=command.stdin,
            capture_output=not command.interactive,
            text=True,
            env=env,
            cwd=command.cwd,
            check=False,
        )
    except OSError as error:
        reason = error.strerror or str(error)
        return Outcome(status=NOT_FOUND_STATUS, stderr=f"{command.argv[0]}: {reason}")
    return Outcome(
        status=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )
