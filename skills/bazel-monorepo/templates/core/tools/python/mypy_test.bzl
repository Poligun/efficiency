"""mypy in strict mode as a per-target test.

mypy comes from the repo's own uv hub and runs on the same pinned interpreter
as the code it checks; python/mypy_check/mypy_check.py is the runner. The
rules_mypy aspect was passed over because its release pins mypy 1.17 on a
Python 3.12 interpreter, which predates the 3.14 this repo targets, and its
stub mechanism expects a pip hub rather than the uv hub used here.

The py_library, py_test and py_binary macros in defs.bzl declare one of
these per target over that target's own sources, with the target's `deps`
as the libraries and packages mypy must resolve. Nothing else calls it: the
import root it needs exists only under python/, and docs/conventions/python.md admits no
Python target outside those macros. The runner's own library is added here,
so callers never list it.
"""

load("@aspect_rules_py//py:defs.bzl", "py_test")
load(":imports.bzl", "py_imports")
load(":labels.bzl", "dedupe_labels")

_RUNNER = "//python/mypy_check:mypy_check.py"
_RUNNER_LIB = "//python/mypy_check"
_CONFIG = "//:pyproject.toml"

def mypy_test(name, srcs, deps = [], **kwargs):
    """Declares a py_test that runs mypy over `srcs`.

    Args:
        name: Name of the test target.
        srcs: Python source files mypy checks.
        deps: Libraries and packages the checked sources import.
        **kwargs: Passed through to py_test. `size` defaults to small.
    """
    kwargs.setdefault("size", "small")
    py_test(
        name = name,
        srcs = [_RUNNER],
        args = ["--config", "$(rootpath %s)" % _CONFIG] +
               ["$(rootpath %s)" % src for src in srcs],
        data = srcs + [_CONFIG],
        imports = py_imports(),
        main = _RUNNER,
        venv = "{{name}}",
        # Canonical-label deduplication, so the runner library is one entry
        # however a caller spells it, including the runner's own package.
        deps = dedupe_labels(deps + [_RUNNER_LIB]),
        **kwargs
    )
