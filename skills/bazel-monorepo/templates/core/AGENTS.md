# General

## Language

Use plain language and short sentences. Avoid dense or overly compressed
phrasing. Do not use analogies or coined terms unless they add clarity.

# Build and conventions

This repository builds every language with Bazel. The conventions live
under [docs/conventions/](docs/conventions/); the adoption record is
[docs/decisions/0001-build-conventions.md](docs/decisions/0001-build-conventions.md).
Read the relevant document before adding or changing a file of that
language or a BUILD file. If this summary and a convention document
disagree, the document wins.

## Layout ([layout.md](docs/conventions/layout.md))

- A program owns a directory under its language tree (`rust/`, `python/`,
  `typescript/`); its modules are subdirectories, one library target each
  with its own BUILD file. The tree root is a plain namespace.
- There is no `src/`. Sources sit next to their BUILD file.
- The root file of a module is named after its directory. No `lib.rs`,
  `mod.rs`, `__init__.py` or `index.ts`. No two files under one program's
  tree share a name. Tests are `<file>_test.<ext>` beside the code.
- A module a second program needs moves up to `<tree>/<name>/`; nothing
  reaches sideways into another program's subdirectory.
- When a file gains a second concern, or its production code nears 200
  lines, propose a new module instead of growing the file.

## Bazel ([bazel.md](docs/conventions/bazel.md))

- Load `rust_library`, `rust_test`, `rust_binary` from
  `//tools/rust:defs.bzl`, `py_library`, `py_test`, `py_binary` from
  `//tools/python:defs.bzl`, and `ts_library`, `ts_test`, `vite_app` from
  `//tools/typescript:defs.bzl`. Never load the rulesets directly. Each
  wrapper declares the lint, format and type-check targets over its own
  sources, so a BUILD file never names a lint target or lists another
  target's files.
- Third-party dependencies enter through `MODULE.bazel` (`crate.spec`),
  `pyproject.toml` with `uv.lock`, and `typescript/package.json` with
  `pnpm-lock.yaml`. Lockfiles are committed. No `Cargo.toml`, no
  machine-installed packages.
- For mechanical BUILD edits (adding a dep, renaming a target), prefer
  buildozer over text edits:
  `bazel run @buildozer -- 'add deps //rust/hello/greeting:hello_greeting' //rust/hello/app:hello_app`.
{{#if rust}}

## Rust ([rust.md](docs/conventions/rust.md))

- Crate names are prefixed with the owning binary: `hello_greeting`, not
  `greeting`. The crate root is `greeting.rs`, set with `crate_root`.
- `rust_test` uses `crate = ":lib"`, never `deps = [":lib"]`. A test with
  its own source file lives in a `tests/` subpackage. Shared test helpers
  go in a `testonly = True` crate under `testutil/`.
- Production code may not use `unwrap`, `expect`, `panic!`, `todo!`, `[i]`
  indexing, `println!` or `eprintln!`. Clippy denies them. Return a
  `Result` and log through `tracing`. Tests are exempt.
- `clippy::pedantic` and `clippy::cognitive_complexity` are on and fatal,
  in tests too. Fix what they flag; do not allow it away. An `#[allow]`
  carries `reason = "..."`.
- A `# Errors` doc section names the conditions under which the function
  fails, not just the error type. Same for `# Panics`.
- Derives by bucket: identity types get the full set through `Ord`; `f64`
  value types stop at `PartialEq`; validated newtypes construct only through
  `FromStr`; error types hand-roll `Display` and `Error`. Never `Default`
  on an enum that mirrors a proto enum.
- `main.rs` holds no logic. No DI framework, no globals: the app crate's
  `run` constructs dependencies and passes them down as arguments. A trait
  needs a second real implementation; "the test needs different data" does
  not count.
{{/if}}

## Python ([python.md](docs/conventions/python.md))

- Every function is annotated and mypy strict checks it. ruff formats and
  lints from `select = ["ALL"]`. Every `# noqa` and `# type: ignore[code]`
  carries a reason. `bazel test //...` is where Python findings surface.
- Code that runs other programs is pure planning functions plus one `run`
  seam (`//python/proc`); tests hand it a recording fake. Subprocesses take
  argument lists, never `shell=True`.
- Programs are `bazel run` targets and read `BUILD_WORKSPACE_DIRECTORY`,
  never `git rev-parse`. Add each new program directory under `python/` to
  `known-first-party` in `pyproject.toml`.
{{#if typescript}}

## TypeScript ([typescript.md](docs/conventions/typescript.md))

- One app per directory under `typescript/`; its screens are subpackages.
  The entry point `main.tsx` mounts the app and holds nothing else.
- A type error fails `bazel build //...`. ESLint runs the type-aware
  strict presets, every rule an error; an `eslint-disable` comment carries
  a description. Prettier defaults. No default exports outside tool
  configs.
- Dependencies enter `typescript/package.json` as exact versions through
  Bazel's pnpm:
  `bazel run -- @pnpm//:pnpm --dir $PWD/typescript add --save-dev --save-exact <pkg>@<version>`.
- `bazel run //typescript/web:app_dev` serves the app;
  `bazel run //typescript:knip` finds dead exports and unused dependencies.
{{/if}}
{{#if proto}}

## Protos ([proto.md](docs/conventions/proto.md))

- Protos live in `proto/<package path>/`, one directory per proto package,
  with `strip_import_prefix = "/proto"`. Generated code is produced at
  build time and never checked in.
{{#if rust}}
- The Rust codegen target (`rust_prost_library`) sits next to the
  `proto_library` and is exempt from the lint-targets rule. tonic, prost
  and the protoc-gen plugins are a pinned set.
- Generated types stay at the API edge; internal code speaks the domain's
  own types, and conversions are free functions in the edge crate.
{{/if}}
{{#if typescript}}
- The TypeScript codegen target (`ts_proto_library`) lives under
  `typescript/proto/` in the directory that mirrors the proto's import
  path; the rule refuses any other package.
{{/if}}
{{/if}}

## Testing ([testing.md](docs/conventions/testing.md))

- Unit tests sit with the code. Tests do not read the environment or the
  filesystem; the sources of external state are arguments.
- A test that needs a service starts its own instance from an archive
  Bazel fetches, one per test function, and declares
  `target_compatible_with` so unsupported hosts skip it.

## Gates ([gates.md](docs/conventions/gates.md))

`bazel test //...` is the gate. Run it before calling work done. It covers
unit tests, formatting, lint and type checks. `bazel build //...` covers
clippy and the TypeScript type check.

Before calling a change ready to merge, also run the patch-coverage gate:
`bazel run //:coverage_gate`. It fails when less than 95% of the changed
lines against the main branch are covered by tests, and names the
uncovered lines. `{{ENV_PREFIX}}_SKIP_COVERAGE_GATE=1` skips it: an escape
hatch for the genuinely unforeseen, visible when used, never routine.

## Automation ([automation.md](docs/conventions/automation.md))

Do not write shell scripts. New automation is a `bazel run` target: a
`.bzl` macro or rule for the wiring, paired with a Python (or Rust)
program for the logic. Shell survives only as a short shim that execs
into something real.

## Dependencies ([dependencies.md](docs/conventions/dependencies.md))

Every version is a pin. Pinned sets move together or not at all, when
their recorded trigger is met. A runtime dependency is a visible decision:
the change that adds it says why nothing already present sufficed.

## Commands

    tools/setup.sh                      # once per clone
    bazel build //...                   # build, clippy, type checks
    bazel test //...                    # tests, format, lint, type and BUILD-file checks
    bazel run //:coverage_gate          # patch-coverage gate; run before calling a change ready to merge
    bazel run //:format -- <files>      # rewrite files into shape; no arguments: tracked and modified files
    bazel run //:buildifier             # rewrite BUILD files into shape
{{#if rust}}
    bazel run @rules_rust//tools/rust_analyzer:gen_rust_project
                                        # IDE index; rerun after BUILD or MODULE changes
{{/if}}
{{#if typescript}}
    bazel run //typescript/web:app_dev  # the dev server
    bazel run //typescript:knip         # dead exports and unused npm dependencies
{{/if}}
