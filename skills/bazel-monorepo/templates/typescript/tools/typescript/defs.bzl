"""TypeScript targets for this repo (docs/conventions/typescript.md): ts_library, ts_test and vite_app.

Load these from //tools/typescript:defs.bzl, never from rules_js or rules_ts
directly. Each is a symbolic macro that declares the sources for the
bundler and the test runner, the type check, and the lint tests over
exactly its own files, the shape of the Python and Rust wrappers:

    load("//tools/typescript:defs.bzl", "ts_library", "ts_test", "vite_app")

    ts_library(
        name = "web",
        srcs = glob(["*.ts", "*.tsx"], exclude = ["*_test.ts", "*_test.tsx", "vite.config.ts"]),
        tsconfig = ":tsconfig",
        deps = ["//typescript:node_modules/react"],
    )

    ts_test(
        name = "web_test",
        srcs = glob(["*_test.ts", "*_test.tsx"]),
        config = ":vite_config",
        tsconfig = ":tsconfig",
        deps = [":web", "//typescript:node_modules/@testing-library/react"],
    )

A library yields `<name>` (a js_library carrying the sources), `<name>_types`
(a ts_project that type-checks them and emits their declarations; a type
error fails `bazel build //...`, as clippy does), `<name>_eslint_test` and
`<name>_format_test`. A test yields `<name>` (the
Vitest run through //tools/typescript:vitest_runner.mjs) plus the same
`_types`, `_eslint_test` and `_format_test` over its own files. An app
yields `<name>` (the Vite production build, an output directory) and
`<name>_dev` (the Vite dev server, `bazel run`).

Every file is checked by the target that owns it: no second file list exists
to drift. Type checking runs against the app's `ts_config` target, passed as
`tsconfig` (`:tsconfig` at the app root, whose tsconfig.json extends
//typescript:tsconfig_base; a deeper package names the app root's target). Symbolic macros cannot glob, so the
`glob()` stays at the call site. Every list attribute is
`configurable = False`; no TypeScript target needs a `select()`.
"""

load("@aspect_rules_js//js:defs.bzl", _js_library = "js_library", _js_run_devserver = "js_run_devserver", _js_test = "js_test")
load("@aspect_rules_ts//ts:defs.bzl", _ts_project = "ts_project")
load("@npm//typescript:vite/package_json.bzl", vite_bin = "bin")
load(":linters.bzl", "eslint_test")

_PRETTIER_CONFIG = "//typescript:prettier_config"
_PRETTIER_CHECK = "//typescript/tools:prettier_check"
_VITEST_RUNNER = "//typescript/tools:vitest_runner"

def _vitest_filters(kind, name, config, srcs):
    """The app package a Vitest run starts in, and the target's files named from it.

    The app package is the one that owns the Vite config; test files are
    named relative to it, since Vitest runs there.
    """
    app_package = config.package
    here = native.package_name()
    if here != app_package and not here.startswith(app_package + "/"):
        fail("%s %s: config %s must live in this package or a parent of it" % (kind, name, config))
    prefix = here[len(app_package):].lstrip("/")
    return app_package, [
        (prefix + "/" + src.name) if prefix else src.name
        for src in srcs
    ]

_VITE = "//tools/typescript:vite"

def _is_package(label):
    """True for a //typescript:node_modules/<package> dependency."""
    return label.package == "typescript" and label.name.startswith("node_modules/")

def _src_paths(name, srcs):
    """The package-relative paths of a target's sources, as rules_ts wants them.

    A symbolic macro receives labels; ts_project computes its declaration
    outputs from source path strings, so the labels go back to paths here.
    A source outside the package has no such path, and a target owns only
    its own files anyway.
    """
    package = native.package_name()
    for src in srcs:
        if src.package != package:
            fail("%s: source %s is not in package //%s; a target owns only its own files" % (name, src, package))
    return [src.name for src in srcs]

def _types(name, visibility, srcs, deps, tsconfig, allow_js, testonly):
    """Declares the ts_project that type-checks one target's files.

    The project emits declarations and nothing else: tsc fails the build on
    a type error, the way clippy fails the Rust build, and the .d.ts files
    are what a dependent target's check resolves imports against, since
    under Bazel a check sees only its own sources and its dependencies'
    outputs. The name says what the target provides, the types of `name`:
    a dependency on another ts_library becomes a dependency on that
    library's `_types`, and a ts_proto_library's `_types` is the generated
    declarations themselves. A node_modules package is passed through, its
    typings come with it. A library written in
    JavaScript is a ts_library like any other, with `allow_js`: its JSDoc
    types become its declarations.

    The tsconfig is a required attribute rather than a default: a symbolic
    macro may only depend on what its caller hands it or what is visible to
    this package, and the app's ts_config is neither by default.
    """
    _ts_project(
        name = name + "_types",
        srcs = _src_paths(name, srcs),
        deps = [
            dep if _is_package(dep) else dep.same_package_label(dep.name + "_types")
            for dep in deps
        ],
        allow_js = allow_js,
        declaration = True,
        emit_declaration_only = True,
        # A .json source is a module with the shape of its contents;
        # tsconfig.base.json says the same.
        resolve_json_module = True,
        testonly = testonly,
        tsconfig = tsconfig,
        visibility = visibility,
    )

def _code(srcs):
    """The sources the format test reads.

    A .json source (data a module imports) is not Prettier's to check.
    ESLint never sees it either, but that is the lint aspect's own doing:
    it visits the type-check project and lints the files whose extensions
    its config covers.
    """
    return [src for src in srcs if not src.name.endswith(".json")]

def _lint_targets(name, srcs, testonly):
    """Declares the ESLint and format tests over one target's files.

    The ESLint test visits the type-check project, so the tsconfig the
    type-aware rules need is an input of the lint action. The format test
    is a js_test over the files themselves.
    """
    srcs = _code(srcs)
    eslint_test(
        name = name + "_eslint_test",
        srcs = [":" + name + "_types"],
        testonly = testonly,
    )

    # Prettier through its API (//typescript/tools:prettier_check): the
    # command line refuses symbolic links, and every sandboxed input is one.
    # Files are named workspace-relative, which the launcher's default
    # working directory (the runfiles root) resolves and the fix hint prints.
    #
    # Under `bazel coverage` rules_js would report the checker's own lines
    # from this run, with V8's line accounting, which disagrees with the
    # Vitest report from the checker's unit test about which lines are
    # statements; merged, the disagreement reads as uncovered lines. An
    # empty COVERAGE_DIR switches that report off: the checker's coverage
    # is its unit test's to measure, not every format test's.
    _js_test(
        name = name + "_format_test",
        args = ["--config", "typescript/prettier.config.js"] + [
            "%s/%s" % (src.package, src.name)
            for src in srcs
        ],
        data = srcs + [_PRETTIER_CONFIG, _PRETTIER_CHECK],
        entry_point = _PRETTIER_CHECK,
        env = {"COVERAGE_DIR": ""},
        size = "small",
        testonly = testonly,
    )

def _ts_library_impl(name, visibility, srcs, deps, data, tsconfig, allow_js, testonly):
    _js_library(
        name = name,
        srcs = srcs,
        data = data,
        deps = deps,
        testonly = testonly,
        visibility = visibility,
    )
    _types(name, visibility, srcs, deps, tsconfig, allow_js, testonly)
    _lint_targets(name, srcs, testonly)

ts_library = macro(
    implementation = _ts_library_impl,
    doc = """A TypeScript library, its type check and the lint tests over its sources.

Yields `<name>` (js_library), `<name>_types` (declarations-only
ts_project), `<name>_eslint_test` and `<name>_format_test` over `srcs`.""",
    attrs = {
        "srcs": attr.label_list(
            mandatory = True,
            configurable = False,
            doc = "The library's .ts and .tsx files, tests excluded.",
        ),
        "deps": attr.label_list(
            default = [],
            configurable = False,
            doc = "ts_library and //typescript:node_modules/<package> targets the sources import.",
        ),
        "data": attr.label_list(
            default = [],
            configurable = False,
            doc = "Runtime files the sources load.",
        ),
        "tsconfig": attr.label(
            mandatory = True,
            configurable = False,
            doc = "The app's ts_config target (`:tsconfig` at the app root; a deeper package names the app root's).",
        ),
        "allow_js": attr.bool(
            default = False,
            configurable = False,
            doc = "True when the package's tsconfig sets allowJs and checkJs: JavaScript sources are checked through their JSDoc types and emit declarations.",
        ),
        "testonly": attr.bool(
            default = False,
            configurable = False,
            doc = "True for test helpers; production targets cannot depend on them.",
        ),
    },
)

def _ts_test_impl(name, visibility, srcs, deps, data, config, tsconfig, allow_js, size, tags):
    _js_library(
        name = name + "_lib",
        srcs = srcs,
        deps = deps,
        testonly = True,
        visibility = visibility,
    )
    _types(name, visibility, srcs, deps, tsconfig, allow_js, True)
    _lint_targets(name, srcs, True)

    app_package, filters = _vitest_filters("ts_test", name, config, srcs)
    _js_test(
        name = name,
        args = ["--package", app_package] + filters,
        chdir = app_package,
        data = [":" + name + "_lib", config, _VITEST_RUNNER] + data,
        entry_point = _VITEST_RUNNER,
        size = size,
        tags = tags,
        visibility = visibility,
    )

ts_test = macro(
    implementation = _ts_test_impl,
    doc = """A Vitest target and the checks over its sources.

Yields `<name>` (js_test running the target's files through
//typescript/tools:vitest_runner, with lcov under `bazel coverage`) plus `<name>_types`,
`<name>_eslint_test` and `<name>_format_test` over `srcs`.""",
    attrs = {
        "srcs": attr.label_list(
            mandatory = True,
            configurable = False,
            doc = "The `<file>_test.ts` and `<file>_test.tsx` files.",
        ),
        "deps": attr.label_list(
            default = [],
            configurable = False,
            doc = "The ts_library under test and the packages the tests import.",
        ),
        "data": attr.label_list(
            default = [],
            configurable = False,
            doc = "Runtime files the tests read.",
        ),
        "config": attr.label(
            mandatory = True,
            configurable = False,
            doc = "The app's Vite config library (a js_library over vite.config.ts and its plugins).",
        ),
        "tsconfig": attr.label(
            mandatory = True,
            configurable = False,
            doc = "The app's ts_config target (`:tsconfig` at the app root; a deeper package names the app root's).",
        ),
        "allow_js": attr.bool(
            default = False,
            configurable = False,
            doc = "True when the package's tsconfig sets allowJs and checkJs: JavaScript sources are checked through their JSDoc types and emit declarations.",
        ),
        "size": attr.string(
            default = "small",
            configurable = False,
            doc = "Bazel test size.",
        ),
        "tags": attr.string_list(
            default = [],
            configurable = False,
            doc = "Bazel test tags.",
        ),
    },
)

def _vite_app_impl(name, visibility, srcs, deps, config):
    inputs = srcs + deps + [config]
    vite_bin.vite(
        name = name,
        srcs = inputs,
        chdir = native.package_name(),
        fixed_args = ["build"],
        out_dirs = ["dist"],
        visibility = visibility,
    )
    _js_run_devserver(
        name = name + "_dev",
        chdir = native.package_name(),
        data = inputs,
        tool = _VITE,
        visibility = visibility,
    )

vite_app = macro(
    implementation = _vite_app_impl,
    doc = """A Vite application: the production build and the dev server.

Yields `<name>` (the `dist/` output directory from `vite build`) and
`<name>_dev` (`bazel run` starts the dev server on localhost).""",
    attrs = {
        "srcs": attr.label_list(
            mandatory = True,
            configurable = False,
            doc = "index.html and any other files Vite reads that no library owns.",
        ),
        "deps": attr.label_list(
            mandatory = True,
            configurable = False,
            doc = "The ts_library the entry point lives in, and its dependencies.",
        ),
        "config": attr.label(
            mandatory = True,
            configurable = False,
            doc = "The Vite config library (a js_library over vite.config.ts and its plugins).",
        ),
    },
)
