from __future__ import annotations

import os

import pytest

from mypy_check.mypy_check import main, mypy_arguments, parse_args


def test_parse_args_reads_config_and_sources() -> None:
    args = parse_args(["--config", "pyproject.toml", "a.py", "b.py"])
    assert args.config == "pyproject.toml"
    assert args.sources == ["a.py", "b.py"]


def test_parse_args_requires_a_source() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--config", "pyproject.toml"])


def test_parse_args_requires_a_config() -> None:
    with pytest.raises(SystemExit):
        parse_args(["a.py"])


def test_mypy_arguments_disable_the_cache() -> None:
    arguments = mypy_arguments("cfg.toml", ["x.py"])
    assert arguments == ["--config-file", "cfg.toml", "--cache-dir", os.devnull, "x.py"]


def test_main_forwards_output_and_status(capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[list[str]] = []

    def fake_run(arguments: list[str]) -> tuple[str, str, int]:
        calls.append(arguments)
        return ("report\n", "warning\n", 1)

    status = main(["--config", "pyproject.toml", "m.py"], run=fake_run)

    captured = capsys.readouterr()
    assert status == 1
    assert captured.out == "report\n"
    assert captured.err == "warning\n"
    assert calls == [
        ["--config-file", "pyproject.toml", "--cache-dir", os.devnull, "m.py"],
    ]
