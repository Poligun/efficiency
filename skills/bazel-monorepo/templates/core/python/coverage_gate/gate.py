"""The entry point of the coverage gate: argument parsing and dispatch only.

Everything testable lives in coverage_gate.py; this file wires the real
runner, the real diff-cover and the process environment to it.
"""

from __future__ import annotations

import os
import sys

from diff_cover.diff_cover_tool import (  # type: ignore[import-untyped]  # diff-cover ships no stubs and no py.typed marker
    main as diff_cover_main,
)

from coverage_gate.coverage_gate import main
from proc.proc import run_subprocess

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], os.environ, run_subprocess, diff_cover_main))
