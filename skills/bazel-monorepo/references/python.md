# Python

Scope: every Python file in the repository, where it lives, how it is
built and which gates it passes. Audience: anyone adding or changing
Python. Prerequisites: layout.md, bazel.md. Python 3 only; the pinned
interpreter is the only one the build knows.

Python is the tooling language: the coverage gate, the automation behind
`bazel run` targets, and any program whose job is argument lists and file
moves. It is always present, even in a repository with no other Python.

## PY-1. The layout mirrors the Rust tree

```
python/
  hello/
    BUILD.bazel        py_binary "hello"
    hello.py           argument parsing and dispatch only
    greeting/          py_library "hello_greeting"
```

- One `py_library` per module, each with its own BUILD file. No `src/`.
- The root file is named after its directory. No two files under one
  program's tree share a name, so there are no `__init__.py` files;
  packages are namespace packages. The import root is `python/`, so
  `python/hello/greeting/greeting.py` imports as `hello.greeting.greeting`,
  and the wrapper sets that root; no file touches `sys.path`.
- Target names carry the owning program: `//python/hello/greeting:hello_greeting`.
- The binary's root file holds argument parsing and dispatch and nothing
  else; everything testable lives in a library.
- A library a second program needs moves up to `python/<name>/`.

## PY-2. Targets come from the wrappers, which lint their own sources

```python
load("//tools/python:defs.bzl", "py_library", "py_test")

py_library(
    name = "hello_greeting",
    srcs = ["greeting.py"],
    visibility = ["//python/hello:__subpackages__"],
)

py_test(
    name = "hello_greeting_test",
    srcs = ["greeting_test.py"],
    deps = [":hello_greeting"],
)
```

Each declaration yields `<name>_ruff_test`, `<name>_format_test` and
`<name>_mypy_test` over exactly its `srcs`. The wrappers fix the import
root, the venv, pytest and coverage as implied test dependencies,
pytest's importlib import mode, the tagged filegroup the ruff aspect
visits, and `pyproject.toml` as an input of the format test.

Two inputs of the format test are load-bearing and easy to lose: the
switch that disables git attribute checks (the sandbox is not a git
repository, and without it the runner formats nothing and passes on any
content), and `pyproject.toml` beside the checked sources (without it ruff
formats against its defaults).

## PY-3. Tests run under pytest, beside the code

`<file>_test.py` next to the file it covers, from the first test on, one
`py_test` per library. pytest is the framework because rules_py's pytest
entry point is the one that writes lcov under `bazel coverage`; a plain
unittest `py_test` writes no coverage at all. Test files may skip the
docstring rules, use bare `assert`, and use literals in assertions.

pytest runs with `--import-mode=importlib`: the default mode puts the
test's own directory first on `sys.path`, where a root file named after
its directory shadows its package.

## PY-4. External state is an argument; subprocesses go through one seam

Tests do not read the environment. Code that runs other programs is pure
planning functions that build argument lists and interpret results, plus
one `run` function that executes them: `//python/proc` holds `Command`,
`Outcome`, the `Runner` type and `run_subprocess`; its `testutil` package
holds `FakeRunner`, which records commands and replays scripted outcomes.
Tests call the planning functions directly and hand the orchestration the
fake. No test patches internals through `unittest.mock`. One allowance:
pytest's `tmp_path` for code whose job is writing files.

Subprocesses take argument lists, never `shell=True` or `os.system`;
ruff's `S602` and `S605` enforce it. A program that cannot be started is
an `Outcome` with status 127, never an exception, so every verb reports
it the way it reports any failure.

## PY-5. ruff formats and lints from `select = ["ALL"]`

The linter starts from everything on, the ruff spelling of
`clippy::pedantic`, and turns rules off only through a short ignore list
in `pyproject.toml` where every entry carries a comment naming what
earned it. Off from the start: the rules ruff documents as conflicting
with its formatter, the `ANN` family (mypy strict reports a missing
annotation with a better message), `INP001` (no `__init__.py`), `T201`
(a command-line tool's output is its interface, so print is the
mechanism) and `CPY` (no copyright headers). A `# noqa` carries the rule
code and a reason; a bare `# noqa` is a review finding. Docstrings on
public functions name the behavior and the failure conditions, not the
signature restated.

Import sorting needs one line per program: `known-first-party` in
`pyproject.toml` names each program directory under `python/`, because a
lint action has only its own target's files as inputs and ruff would
otherwise classify a test's import of its own library as third-party
(`I001`). A missing entry fails loudly on that program's first test.

## PY-6. Every function is annotated and mypy strict verifies it

Type hints are syntax the interpreter ignores, so the guard is the
checker. mypy runs in strict mode over every package's files as a
`py_test` (`tools/python/mypy_test.bzl`, runner `python/mypy_check/`),
with mypy from the repository's uv hub on the same pinned interpreter as
the code. A `# type: ignore[code]` names the error code and carries a
reason. A runtime dependency without inline types brings its `types-*`
stub package as a pinned entry in `pyproject.toml`, and the library that
imports the package lists the hub's `@pypi//types_<name>` label in its
`deps`, so the mypy test sees the stubs through the same graph as the
code.

**Rejected.** pyright: no maintained Bazel integration. The rules_mypy
aspect: its release pinned an older mypy on an older interpreter and its
stub mechanism expects a pip hub rather than the uv hub. A per-package
test runs a current mypy on the repository's own interpreter.

## PY-7. The gates are the same commands as for every language

- `bazel test //...` fails on a ruff finding, an unformatted file and a
  mypy error.
- `bazel run //:format -- <file>` formats through ruff.
- `bazel run //:coverage_gate` counts Python lines: the instrumentation
  filter admits `//python`, and `coverage` is a dependency of every
  `py_test`.
- `bazel build //...` builds every binary and test but cannot lint them,
  and skips a bare library with a pypi dependency as incompatible rather
  than failing: the uv hub resolves packages only inside a
  venv-configured binary or test. The test gate is where Python findings
  surface. `bazel build --config=ruff //...` is the whole-tree escape
  hatch.

## PY-8. Programs run through Bazel and read Bazel's environment

A program is a `py_binary` behind a `bazel run` target. It finds the
repository through `BUILD_WORKSPACE_DIRECTORY` and the invoking directory
through `BUILD_WORKING_DIRECTORY`, never through `git rev-parse`. Results
go to stdout and diagnostics to stderr through plain `print`. A hook that
an agent harness or version control runs is a shim that execs the
`bazel run` target, so the Python behind it lives under `python/` and
passes the gates.

One pattern joins the accepted shapes: a `bazel run` target may invoke
`bazel run` on another target when a `data` dependency would pull an
unrelated build into every invocation of the first. The calling program's
docstring records the nested invocation, because Bazel's graph does not
show it.

## PY-9. Dependencies enter through the lock

Third-party packages are declared in `pyproject.toml` and resolved into
`uv.lock` (`bazel run @uv -- lock`), one hub for the repository. Test and
tooling dependencies (pytest, coverage, mypy, stub packages) are routine
additions. A runtime dependency for a program is a visible decision: the
change that adds it records why the standard library did not suffice. The
Python minor version lives in three files (`requires-python`, the
interpreter toolchain in `MODULE.bazel`, the `python_version` flag in
`.bazelrc`) and moves in all three at once, then re-locks.

**Rejected.** Rust for the operator-style tooling: clippy and coverage
would come for free, but process orchestration is hard to cover without a
command-runner seam, and the code is argument lists and file moves, where
Rust's type system buys little over annotated Python.
