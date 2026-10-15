"""Runs mypy over the sources of one Bazel target.

The `mypy_test` macro in tools/python/mypy_test.bzl wires this file as the
main of a py_test per package and passes the configuration file and the
sources as arguments. mypy comes from the repo's uv hub and runs on the same
interpreter as the checked code, so the check follows the pinned Python
version. The incremental cache is disabled through mypy's documented
`--cache-dir=/dev/null` spelling: a Bazel test runs in a fresh sandbox, so
nothing would survive between runs anyway.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Sequence

from mypy import api

Runner = Callable[[list[str]], tuple[str, str, int]]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parses the runner's own arguments.

    Args:
        argv: Arguments after the program name: `--config <file>` and then
            one or more source paths.

    Returns:
        A namespace with `config` (a path) and `sources` (a non-empty list of
        paths).

    Raises:
        SystemExit: From argparse, with status 2 and the usage on stderr,
            when `--config` is absent or no source path is given.
    """
    parser = argparse.ArgumentParser(
        prog="mypy_check",
        description="Run mypy over the given sources with the given configuration.",
    )
    parser.add_argument("--config", required=True, help="mypy configuration file")
    parser.add_argument("sources", nargs="+", help="source files to check")
    return parser.parse_args(argv)


def mypy_arguments(config: str, sources: Sequence[str]) -> list[str]:
    """Builds the mypy command line.

    Args:
        config: The configuration file, passed as `--config-file`.
        sources: The files to check.

    Returns:
        The argument list mypy's API accepts, without the program name, with
        the cache disabled.
    """
    return ["--config-file", config, "--cache-dir", os.devnull, *sources]


def main(argv: Sequence[str], run: Runner = api.run) -> int:
    """Runs mypy and reports its verdict as the exit code.

    Args:
        argv: The runner's arguments, see `parse_args`.
        run: The function that executes mypy; `mypy.api.run` in production,
            a recording fake in tests.

    Returns:
        mypy's exit status: zero when every source type-checks.
    """
    args = parse_args(argv)
    stdout, stderr, status = run(mypy_arguments(args.config, args.sources))
    sys.stdout.write(stdout)
    sys.stderr.write(stderr)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
