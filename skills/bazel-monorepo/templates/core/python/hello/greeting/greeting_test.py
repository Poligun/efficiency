from __future__ import annotations

import pytest

from hello.greeting.greeting import GreetingError, greet


def test_greet_names_the_person() -> None:
    assert greet("Ada") == "Hello, Ada!"


def test_greet_trims_whitespace() -> None:
    assert greet("  Ada ") == "Hello, Ada!"


def test_greet_refuses_an_empty_name() -> None:
    with pytest.raises(GreetingError, match="a name is required"):
        greet("   ")
