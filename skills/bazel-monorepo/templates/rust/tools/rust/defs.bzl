"""Rust targets for this repo: rust_library, rust_test and rust_binary.

Load these from //tools/rust:defs.bzl, never from rules_rust directly. Each
is a symbolic macro over the rules_rust rule of the same name that also
declares the lint targets over the crate it owns, the same shape as the
Python wrappers in //tools/python:defs.bzl:

    load("//tools/rust:defs.bzl", "rust_library", "rust_test")

    rust_library(
        name = "hello_greeting",
        srcs = glob(["*.rs"]),
        crate_root = "greeting.rs",
        visibility = ["//rust/hello:__subpackages__"],
        deps = ["@crates//tracing"],
    )

    rust_test(
        name = "hello_greeting_test",
        crate = ":hello_greeting",
    )

A library yields `<name>`, `<name>_clippy` and `<name>_rustfmt_test`. A
test yields `<name>` and `<name>_clippy`, and when it has its own `srcs`
(an integration test in a `tests/` package) `<name>_rustfmt_test` as well;
a unit test built from `crate` shares the library's sources, so the
library's rustfmt target already covers them. A binary yields the same
three as a library. Every crate is linted by the target that owns it: the
unit test's clippy is what sees `#[cfg(test)]` code, because only a crate
compiled with `--test` has it, and no target lists another target's files,
so nothing drifts. The generated targets are visible to the calling
package and inside this file only; `bazel build //...` builds the clippy
targets and `bazel test //...` runs the rustfmt tests, and nothing else
needs to name them.

A library in a `testutil/` package must say `testonly = True`; the wrapper
refuses one that does not, so the rule that production code cannot depend
on test helpers is checked at load time rather than by a comment.

Symbolic macros cannot glob, so `glob(["*.rs"])` stays at the call site.
Every list attribute is `configurable = False`; no Rust target here needs
a `select()`.
"""

load(
    "@rules_rust//rust:defs.bzl",
    _rust_binary = "rust_binary",
    _rust_clippy = "rust_clippy",
    _rust_library = "rust_library",
    _rust_test = "rust_test",
    _rustfmt_test = "rustfmt_test",
)

def _clippy(name, testonly):
    _rust_clippy(
        name = name + "_clippy",
        testonly = testonly,
        deps = [":" + name],
    )

def _rustfmt(name):
    _rustfmt_test(
        name = name + "_rustfmt_test",
        size = "small",
        targets = [":" + name],
    )

def _rust_library_impl(name, visibility, srcs, crate_root, deps, data, compile_data, rustc_env, testonly, target_compatible_with):
    if native.package_name().endswith("/testutil") and not testonly:
        fail("rust_library %s: a testutil/ crate must set testonly = True, so production targets cannot depend on it" % name)
    _rust_library(
        name = name,
        srcs = srcs,
        compile_data = compile_data,
        crate_root = crate_root,
        data = data,
        rustc_env = rustc_env,
        target_compatible_with = target_compatible_with,
        testonly = testonly,
        visibility = visibility,
        deps = deps,
    )
    _clippy(name, testonly)
    _rustfmt(name)

rust_library = macro(
    implementation = _rust_library_impl,
    doc = """A Rust library crate and the lint targets over its sources.

Yields `<name>` (rules_rust rust_library) plus `<name>_clippy` and
`<name>_rustfmt_test` over the crate as built for production. The
`#[cfg(test)]` code is linted by the unit test's own clippy target.""",
    attrs = {
        "srcs": attr.label_list(
            mandatory = True,
            configurable = False,
            doc = "The crate's source files, normally glob([\"*.rs\"]).",
        ),
        "crate_root": attr.label(
            mandatory = True,
            configurable = False,
            doc = "The root file, named after the directory (docs/conventions/layout.md).",
        ),
        "deps": attr.label_list(
            default = [],
            configurable = False,
            doc = "Crates the sources use.",
        ),
        "data": attr.label_list(
            default = [],
            configurable = False,
            doc = "Runfiles the code reads at run time, located through the runfiles crate.",
        ),
        "compile_data": attr.label_list(
            default = [],
            configurable = False,
            doc = "Files the sources embed at compile time (include_str!, embed_migrations!).",
        ),
        "rustc_env": attr.string_dict(
            default = {},
            configurable = False,
            doc = "Environment for rustc; $(execpath) and $(rlocationpath) expand against data and compile_data.",
        ),
        "testonly": attr.bool(
            default = False,
            configurable = False,
            doc = "True for test helpers under testutil/; production targets cannot depend on them.",
        ),
        "target_compatible_with": attr.label_list(
            default = [],
            doc = "Constraints the host must satisfy, else the crate and everything depending on it are skipped. The one configurable attribute: //tools/stores:defs.bzl hands a store-starting testutil its host rule as a select.",
        ),
    },
)

def _rust_test_impl(name, visibility, crate, srcs, deps, data, compile_data, rustc_env, size, tags, args, target_compatible_with):
    if (crate == None) == (len(srcs) == 0):
        fail("rust_test %s: set exactly one of crate (a unit test over the library's sources) or srcs (an integration test with its own)" % name)
    _rust_test(
        name = name,
        size = size,
        srcs = srcs,
        args = args,
        compile_data = compile_data,
        crate = crate,
        data = data,
        rustc_env = rustc_env,
        tags = tags,
        target_compatible_with = target_compatible_with,
        visibility = visibility,
        deps = deps,
    )
    _clippy(name, True)
    if srcs:
        _rustfmt(name)

rust_test = macro(
    implementation = _rust_test_impl,
    doc = """A Rust test and the lint targets over it.

Yields `<name>` (rules_rust rust_test) plus `<name>_clippy`. With `crate`
the test recompiles the library's sources with `--test`, which is what
makes `#[cfg(test)]` code exist, and its clippy target is the one that
lints that code. With `srcs` the test is an integration test over the
public API, lives in a `tests/` package of its own, and also yields
`<name>_rustfmt_test`.""",
    attrs = {
        "crate": attr.label(
            configurable = False,
            doc = "The library under test, for a unit test. Never `deps`: that links the rlib, where the test code was compiled out.",
        ),
        "srcs": attr.label_list(
            default = [],
            configurable = False,
            doc = "The integration test's own source file.",
        ),
        "deps": attr.label_list(
            default = [],
            configurable = False,
            doc = "What the tests use beyond the library: testutil crates, the crate under test for an integration test.",
        ),
        "data": attr.label_list(
            default = [],
            configurable = False,
            doc = "Runfiles the tests read at run time, located through the runfiles crate.",
        ),
        "compile_data": attr.label_list(
            default = [],
            configurable = False,
            doc = "Files the tests embed at compile time.",
        ),
        "rustc_env": attr.string_dict(
            default = {},
            configurable = False,
            doc = "Environment for rustc; $(execpath) and $(rlocationpath) expand against data and compile_data.",
        ),
        "size": attr.string(
            default = "small",
            configurable = False,
            doc = "Bazel test size.",
        ),
        "tags": attr.string_list(
            default = [],
            configurable = False,
            doc = "Bazel test tags: manual, exclusive, requires-network. The lint targets carry none of them.",
        ),
        "args": attr.string_list(
            default = [],
            configurable = False,
            doc = "Arguments to the test binary, for example [\"--test-threads=1\"].",
        ),
        "target_compatible_with": attr.label_list(
            default = [],
            doc = "Constraints the host must satisfy, else bazel test //... skips the test. The one configurable attribute: //tools/stores:defs.bzl hands a store-backed test its host rule as a select.",
        ),
    },
)

def _rust_binary_impl(name, visibility, srcs, deps, compile_data, rustc_env):
    _rust_binary(
        name = name,
        srcs = srcs,
        compile_data = compile_data,
        rustc_env = rustc_env,
        visibility = visibility,
        deps = deps,
    )
    _clippy(name, False)
    _rustfmt(name)

rust_binary = macro(
    implementation = _rust_binary_impl,
    doc = """A Rust binary and the lint targets over its sources.

Yields `<name>` (rules_rust rust_binary) plus `<name>_clippy` and
`<name>_rustfmt_test`. main.rs holds no logic to test, so
there is no test target.""",
    attrs = {
        "srcs": attr.label_list(
            mandatory = True,
            configurable = False,
            doc = "The binary's source files, normally just main.rs.",
        ),
        "deps": attr.label_list(
            default = [],
            configurable = False,
            doc = "Crates the binary uses.",
        ),
        "compile_data": attr.label_list(
            default = [],
            configurable = False,
            doc = "Files the sources embed at compile time.",
        ),
        "rustc_env": attr.string_dict(
            default = {},
            configurable = False,
            doc = "Environment for rustc; $(execpath) and $(rlocationpath) expand against data and compile_data.",
        ),
    },
)
