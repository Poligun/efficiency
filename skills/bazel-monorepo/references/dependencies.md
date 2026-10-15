# Dependencies and version pins

Scope: how a dependency enters, how versions are pinned, which pins move
together, and how they are moved. Audience: anyone adding a dependency or
touching a version. Prerequisites: bazel.md and the per-language
documents.

## DE-1. Every version is a pin, and every pin has an owner

Each ruleset (`bazel_dep`), toolchain (Rust, LLVM, the Linux sysroots,
uv, the Python interpreter, Node, pnpm), third-party package
(`crate.spec`, `pyproject.toml`, `package.json`), service archive
(`http_archive` with the publisher's checksum) and container base image
(by digest) is an exact version or a caret range resolved into a
committed lockfile. Nothing floats. A new kind of pin names, in the same
change, the mechanism that will move it.

## DE-2. Dependencies enter through their manifest and lockfile

| Language | Declare in | Resolve into | Regenerate with | Reference as |
| --- | --- | --- | --- | --- |
| Rust | `MODULE.bazel` `crate.spec` | `MODULE.bazel.lock` | the next build | `@crates//<package>` |
| Python | `pyproject.toml` | `uv.lock` | `bazel run @uv -- lock` | `@pypi//<package>` |
| TypeScript | `typescript/package.json` | `typescript/pnpm-lock.yaml` | `bazel run -- @pnpm//:pnpm --dir $PWD/typescript install --lockfile-only` | `//typescript:node_modules/<package>` |
| Bazel rulesets | `MODULE.bazel` `bazel_dep` | `MODULE.bazel.lock` | the next build | by apparent name |

Lockfiles are committed. A manifest change without a regenerated lockfile
fails the build (`--lockfile_mode=error` under `--config=ci`). No
`Cargo.toml`, no machine-installed packages, no `pip install`.

A runtime dependency is a visible decision: the change that adds one
records why the standard library or an existing dependency did not
suffice. Test and tooling dependencies are routine. Prefer explicit
feature lists over default features when a package pulls in more than
needed.

## DE-3. Pinned sets move together or not at all

A pinned set is a coupling, not a freeze: its members move together when
the recorded trigger is met, and the trigger is checked whenever versions
are reviewed. The sets this layout starts with, each with its trigger:

| Set | Members | Trigger |
| --- | --- | --- |
| tonic set | tonic, prost, prost-types, protoc-gen-prost, protoc-gen-tonic | rules_rust's prost toolchain supports the newer tonic codec split |
| rules_rust set | rules_rust, rules_rust_prost | a release exists; new clippy lints are fixed, not allowed |
| Python minor | `requires-python`, the interpreter toolchain and release date in `MODULE.bazel`, `python_version` in `.bazelrc`; then `uv lock` | a new CPython minor the ruleset ships |
| Rust edition | `rust.toolchain(edition)` and `rustfmt.toml` | an edition move, by hand |
| TypeScript 7 | typescript stays on 6.x | typescript-eslint supports the native compiler |
| Vite 8 | vite stays on 7 | the Bazel-sandbox bundler issue in rules_js closes |
| mypy 2 | mypy stays below 2 | rules_py 2.x lands (the uv hub gains the free-threaded ABI constraint) |
| Node and pnpm | versions must exist in rules_nodejs's and rules_js's mirrored tables | a release inside the tables, or a bump with an integrity value |

Record a new set in this table, in the manifest comment beside the pin,
and in the update tool's grouping configuration where one exists, so the
three agree by construction.

## DE-4. Routine bumps and proposals

A bump within a caret range, a ruleset minor, an exact pin moving by a
patch or minor, a lock re-resolution or a patch or minor image tag is
routine work. A major bump, a toolchain bump (Rust, LLVM, Bazel, Python,
Node, pnpm, uv) and any move of a pinned set is a proposal: it may be
attempted, but the result waits for a human unless the diff is trivial.
Toolchain bumps are proposals because new lints must be fixed, not
allowed away, and that is code work.

A trivial diff is version strings, lockfiles and generated files with
the gate green, or a patch or minor image tag. Anything that changes a
source line beyond a small mechanical adaptation waits.

## DE-5. Derived files and prose move with the pin

A bump regenerates every file derived from the pin (`MODULE.bazel.lock`,
`uv.lock`, `pnpm-lock.yaml`, `tools/preset.bazelrc` after a Bazel bump,
any golden a toolchain bump moves) and fixes every statement in the
documentation, `AGENTS.md` and manifest comments that names the old
version or a command the bump invalidates. Drift between a pin and the
prose that names it is a defect of the bump.

## DE-6. Version discovery is a tool's job; the routine is local

Which versions exist is detected by a dependency-update tool run locally
in lookup-only mode against a checked-in configuration, holding no
credential and writing nothing; the deterministic work (editing the pin
files, regenerating locks, rendering a report) is a `bazel run` program
(automation.md AU-1), and a person or an agent session reviews the
result. A claimed pin the detector did not read is a failure of the
routine, and a test can check that the configuration claims every pin
kind the repository holds.

**Why local.** No third-party service gets a repository grant, a token or
build data, and the gate that verifies every change is the same local
gate.

**Rejected.** A hosted update bot: it cannot refresh `MODULE.bazel.lock`
and would need a repository grant. A hosted bot that reads nothing inside
module extensions misses most of the pins here.

**Applies when.** The repository is maintained over time. A throwaway
has no routine; it still has pins.
