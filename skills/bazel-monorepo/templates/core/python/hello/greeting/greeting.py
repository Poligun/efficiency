"""Composes greetings. A module library of the hello program."""

from __future__ import annotations


class GreetingError(ValueError):
    """The name cannot be greeted."""


def greet(name: str) -> str:
    """Returns the greeting for `name`.

    Args:
        name: Who to greet; surrounding whitespace is ignored.

    Returns:
        The greeting line, without a trailing newline.

    Raises:
        GreetingError: When `name` is empty or whitespace only.
    """
    trimmed = name.strip()
    if not trimmed:
        msg = "a name is required"
        raise GreetingError(msg)
    return f"Hello, {trimmed}!"
