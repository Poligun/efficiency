"""The hello program: argument parsing and dispatch, nothing else."""

from __future__ import annotations

import argparse
import sys

from hello.greeting.greeting import GreetingError, greet


def main(argv: list[str]) -> int:
    """Prints a greeting for the name given on the command line.

    Args:
        argv: The arguments after the program name.

    Returns:
        Zero on success, one when the name is refused.
    """
    parser = argparse.ArgumentParser(prog="hello")
    parser.add_argument("name", help="who to greet")
    args = parser.parse_args(argv)
    try:
        print(greet(args.name))
    except GreetingError as error:
        print(f"hello: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
