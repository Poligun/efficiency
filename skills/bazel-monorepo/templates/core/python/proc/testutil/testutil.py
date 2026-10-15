"""Test helpers shared by the packages that plan commands.

`FakeRunner` stands in for `proc.proc.run_subprocess`: it records every
command it receives and replays scripted outcomes, so a test asserts on the
exact argument lists a verb planned without spawning anything.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from proc.proc import Outcome

if TYPE_CHECKING:
    from collections.abc import Iterable

    from proc.proc import Command


class FakeRunner:
    """Records commands and replays scripted outcomes in order.

    Outcomes are consumed first to last; once they run out every further
    command succeeds with empty output, so a test scripts only the results
    it cares about.
    """

    def __init__(self, outcomes: Iterable[Outcome] = ()) -> None:
        """Creates a runner with the outcomes to replay, in order."""
        self.commands: list[Command] = []
        self._outcomes: deque[Outcome] = deque(outcomes)

    def __call__(self, command: Command) -> Outcome:
        """Records `command` and returns the next scripted outcome."""
        self.commands.append(command)
        if self._outcomes:
            return self._outcomes.popleft()
        return Outcome(status=0)

    @property
    def argvs(self) -> list[tuple[str, ...]]:
        """The argument lists received so far, in order."""
        return [command.argv for command in self.commands]
