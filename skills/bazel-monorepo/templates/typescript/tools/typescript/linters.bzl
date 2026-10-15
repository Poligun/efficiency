"""ESLint as a Bazel lint aspect, and the test wrapper around it.

The ts_library and ts_test macros in defs.bzl declare an `eslint_test` per
target over that target's type-check project, so the tsconfig the
type-aware rules need is an input of the lint action. The aspect reads
//typescript/eslint.config.js, which travels with its plugins as the
eslint_config library. The whole-tree form is
`bazel build --config=eslint //...` (see .bazelrc).
"""

load("@aspect_rules_lint//lint:eslint.bzl", "lint_eslint_aspect")
load("@aspect_rules_lint//lint:lint_test.bzl", "lint_test")

eslint = lint_eslint_aspect(
    binary = Label("//tools/typescript:eslint"),
    configs = [
        Label("//typescript:eslint_config"),
        Label("//typescript:package_json"),
        Label("//typescript:tsconfig.base.json"),
    ],
)

eslint_test = lint_test(aspect = eslint)
