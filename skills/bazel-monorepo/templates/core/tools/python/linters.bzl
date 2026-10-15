"""ruff as a Bazel lint aspect, and the test wrapper around it.

The py_library, py_test and py_binary macros in defs.bzl declare a
`ruff_test` per target over a filegroup of that target's Python files,
tagged `lint-with-ruff` so the aspect visits it. The aspect visits filegroups
rather than the rule targets because the uv hub in rules_py resolves
packages only inside a venv-configured binary or test: a py_library with a
pypi dependency is incompatible at top level, and an aspect cannot analyze
it there. ruff needs no dependencies, so files are enough.

The aspect reads its rules from [tool.ruff] in the root pyproject.toml. The
whole-tree form is `bazel build --config=ruff //...` (see .bazelrc); there
the aspect visits the filegroup and the venv-configured test or binary that
carries the same files, so a finding is reported twice.
"""

load("@aspect_rules_lint//lint:lint_test.bzl", "lint_test")
load("@aspect_rules_lint//lint:ruff.bzl", "lint_ruff_aspect")

ruff = lint_ruff_aspect(
    binary = Label("@aspect_rules_lint//lint:ruff_bin"),
    configs = [Label("@//:pyproject.toml")],
)

ruff_test = lint_test(aspect = ruff)
