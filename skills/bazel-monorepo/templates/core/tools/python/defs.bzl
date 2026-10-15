"""Python targets for this repo: py_library, py_test and py_binary.

Load these from //tools/python:defs.bzl, never from rules_py directly. Each
is a symbolic macro over the rules_py rule of the same name that also
declares the lint tests for the files it owns, the way a Rust crate carries
its rust_clippy and rustfmt_test beside it:

    load("//tools/python:defs.bzl", "py_library", "py_test")

    py_library(
        name = "foo",
        srcs = ["foo.py"],
        visibility = ["//python/bar:__subpackages__"],
        deps = ["//python/baz"],
    )

    py_test(
        name = "foo_test",
        srcs = ["foo_test.py"],
        deps = [":foo"],
    )

Beside its rule target, each declaration yields `<name>_ruff_test`,
`<name>_format_test` and `<name>_mypy_test` over exactly its `srcs`. A file
is linted by the target that owns it, so no second file list exists to
drift, and library and test keep separate visibility and dependencies. The
generated tests are visible to this package and inside the macro only, not
to the calling package: `bazel test //...` runs them, and nothing else
needs to name them.

The macros hold the wiring the conventions fix once: the import root, the
`{{name}}` venv, pytest and coverage as test dependencies, pytest's importlib
import mode (the default mode puts the test's own directory first on
sys.path, where a root file named after its directory shadows its package),
the tagged filegroup the ruff aspect visits, the repo's pyproject.toml as an
input of the format test, and the format test's switch that makes it run at
all inside the sandbox. Every list attribute is `configurable = False`, so
a Python target cannot use `select()`; nothing needs one while every
program is stdlib-plus-pyyaml.
"""

load("@aspect_rules_lint//format:defs.bzl", "format_test")
load(
    "@aspect_rules_py//py:defs.bzl",
    _py_binary = "py_binary",
    _py_library = "py_library",
    _py_test = "py_test",
)
load(":imports.bzl", "py_imports")
load(":labels.bzl", "dedupe_labels")
load(":linters.bzl", "ruff_test")
load(":mypy_test.bzl", "mypy_test")

_PYTEST = "@pypi//pytest"
_COVERAGE = "@pypi//coverage"
_VENV = "{{name}}"
_RUFF_CONFIG = "//:pyproject.toml"
_FORMAT = "//:format"

def _lint_targets(name, srcs, deps):
    """Declares the ruff, format and mypy tests over one target's files.

    Args:
        name: The owning target; the tests are `<name>_ruff_test`,
            `<name>_format_test` and `<name>_mypy_test`.
        srcs: The files that target owns.
        deps: What those files import, for mypy.
    """
    files = name + "_lint_files"
    native.filegroup(
        name = files,
        srcs = srcs,
        tags = ["lint-with-ruff"],
    )
    ruff_test(
        name = name + "_ruff_test",
        srcs = [":" + files],
    )

    # Two inputs are load-bearing. disable_git_attribute_checks: rules_lint's
    # runner asks `git check-attr` which files to skip, the test sandbox is
    # not a git repository, and the failed call empties the file list, so
    # without the switch the test runs no formatter and passes on any
    # content. pyproject.toml: the runner passes ruff no --config and the
    # sandbox holds only the test's inputs, so without the file beside the
    # checked sources ruff formats against its built-in defaults rather than
    # the repo's settings. The runner hands ruff only Python files, so the
    # TOML is an input and never a target. rules_lint fixes the test's size
    # itself (the attribute is not forwarded), and fix_target names the
    # command the failure hint prints.
    format_test(
        name = name + "_format_test",
        srcs = [":" + files, _RUFF_CONFIG],
        disable_git_attribute_checks = True,
        fix_target = _FORMAT,
        python = "@aspect_rules_lint//format:ruff",
    )
    mypy_test(
        name = name + "_mypy_test",
        srcs = srcs,
        deps = deps,
    )

def _py_library_impl(name, visibility, srcs, deps, data, testonly):
    _py_library(
        name = name,
        srcs = srcs,
        data = data,
        imports = py_imports(),
        testonly = testonly,
        visibility = visibility,
        deps = deps,
    )
    _lint_targets(name, srcs, deps)

py_library = macro(
    implementation = _py_library_impl,
    doc = """A Python library and the lint tests over its sources.

Yields `<name>` (rules_py py_library on the shared import root) plus
`<name>_ruff_test`, `<name>_format_test` and `<name>_mypy_test` over `srcs`.""",
    attrs = {
        "srcs": attr.label_list(
            mandatory = True,
            configurable = False,
            doc = "The library's source files; the root file is named after the directory.",
        ),
        "deps": attr.label_list(
            default = [],
            configurable = False,
            doc = "Libraries and packages the sources import.",
        ),
        "data": attr.label_list(
            default = [],
            configurable = False,
            doc = "Runtime files the library reads.",
        ),
        "testonly": attr.bool(
            default = False,
            configurable = False,
            doc = "True for test helpers under testutil/; production targets cannot depend on them.",
        ),
    },
)

def _py_test_impl(name, visibility, srcs, deps, data, size, tags):
    _py_test(
        name = name,
        size = size,
        srcs = srcs,
        args = ["--import-mode=importlib"],
        data = data,
        imports = py_imports(),
        pytest_main = True,
        tags = tags,
        venv = _VENV,
        visibility = visibility,
        deps = dedupe_labels(deps + [_COVERAGE, _PYTEST]),
    )

    # The tests import pytest by construction, so mypy needs it too.
    _lint_targets(name, srcs, dedupe_labels(deps + [_PYTEST]))

py_test = macro(
    implementation = _py_test_impl,
    doc = """A pytest target and the lint tests over its sources.

Yields `<name>` (rules_py py_test with the pytest entry point, coverage and
the importlib import mode) plus `<name>_ruff_test`, `<name>_format_test` and
`<name>_mypy_test` over `srcs`. pytest and coverage are implied.""",
    attrs = {
        "srcs": attr.label_list(
            mandatory = True,
            configurable = False,
            doc = "The `<file>_test.py` files.",
        ),
        "deps": attr.label_list(
            default = [],
            configurable = False,
            doc = "The library under test and what the tests import beyond pytest.",
        ),
        "data": attr.label_list(
            default = [],
            configurable = False,
            doc = "Runtime files the tests read.",
        ),
        "size": attr.string(
            default = "small",
            configurable = False,
            doc = "Bazel test size.",
        ),
        "tags": attr.string_list(
            default = [],
            configurable = False,
            doc = "Bazel test tags, for example [\"manual\"].",
        ),
    },
)

def _py_binary_impl(name, visibility, srcs, main, deps, data, args):
    _py_binary(
        name = name,
        srcs = srcs,
        args = args,
        data = data,
        imports = py_imports(),
        main = main,
        venv = _VENV,
        visibility = visibility,
        deps = deps,
    )
    _lint_targets(name, srcs, deps)

py_binary = macro(
    implementation = _py_binary_impl,
    doc = """A Python program and the lint tests over its sources.

Yields `<name>` (rules_py py_binary on the shared venv and import root) plus
`<name>_ruff_test`, `<name>_format_test` and `<name>_mypy_test` over `srcs`.
The root file holds argument parsing and dispatch only.""",
    attrs = {
        "srcs": attr.label_list(
            mandatory = True,
            configurable = False,
            doc = "The program's source files, usually the one root file.",
        ),
        "main": attr.label(
            mandatory = True,
            configurable = False,
            doc = "The entry point, one of srcs.",
        ),
        "deps": attr.label_list(
            default = [],
            configurable = False,
            doc = "Libraries and packages the program imports.",
        ),
        "data": attr.label_list(
            default = [],
            configurable = False,
            doc = "Runtime files the program reads.",
        ),
        "args": attr.string_list(
            default = [],
            configurable = False,
            doc = "Fixed arguments the program receives before the command line's, for a target that is one invocation of a library (the coverage gate).",
        ),
    },
)
