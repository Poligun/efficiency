# Rust

Scope: every Rust file and every Rust target. Audience: anyone adding or
changing Rust. Prerequisites: layout.md, bazel.md. Rules on tests are in
testing.md and on dependencies in dependencies.md; this document covers
what is Rust-specific.

Rust is built by Bazel through rules_rust. No Cargo build, `Cargo.toml`
or `Cargo.lock` exists.

## RS-1. Crate names carry the owning binary as a prefix

`hello_greeting`, `hello_app`, never `greeting`. The directory keeps the
short name (`greeting/`); the crate name comes from the target name and
`crate_name` stays unset.

**Why.** A first-party crate named `config` shadows the third-party
`config` crate it depends on: inside it, `use config::...` resolves to the
dependency and the crate's own items need `crate::`. The prefix removes
the trap and says who owns the crate.

## RS-2. The crate root is named after the directory and set explicitly

```python
load("//tools/rust:defs.bzl", "rust_library", "rust_test")

rust_library(
    name = "hello_greeting",
    srcs = glob(["*.rs"]),
    crate_root = "greeting.rs",
    visibility = ["//rust/hello:__subpackages__"],
)

rust_test(
    name = "hello_greeting_test",
    crate = ":hello_greeting",
)
```

A library yields `<name>`, `<name>_clippy` and `<name>_rustfmt_test`; a
test yields `<name>` and `<name>_clippy` (and `<name>_rustfmt_test` when
it has its own `srcs`); a binary yields the same three as a library. The
`clippy::mod_module_files` lint denies `mod.rs` files, so the naming rule
is checked by the build.

## RS-3. Unit tests use `crate =`, never `deps =`

`crate = ":lib"` recompiles the library's sources with `--test`, which is
what makes `#[cfg(test)]` code exist at all. `deps = [":lib"]` links the
already-built rlib, where that code was compiled out, producing a test
binary that passes while running nothing. The wrapper refuses a test with
both or neither of `crate` and `srcs`.

The unit test's clippy target is the one that sees `#[cfg(test)]` code,
because only a crate compiled with `--test` has it; the library's clippy
target sees the production build.

## RS-4. Tests start inline and move out when they outgrow the file

```rust
#[cfg(test)]
mod tests {
    use super::*;
}
```

When the tests grow longer than the code they cover, move them to
`<file>_test.rs` and pull the module back in with
`#[cfg(test)] #[path = "greeting_test.rs"] mod greeting_test;`. The module
is still part of the crate and reaches private items through
`use super::*`. A judgement call, not a threshold: a reader opening the
file should see the production code first.

## RS-5. Standalone tests live in `tests/`; helpers in `testutil/`

A `rust_test` with its own `srcs` (an integration suite, or a test over
the public API) lives in a `tests/` subpackage of its crate, names the
crate under test in `deps` by full label, and keeps its `size`, `tags`
and `args` beside it. The crate's `glob(["*.rs"])` cannot reach it, so no
`exclude` list exists.

Test code needed by more than one crate cannot be `#[cfg(test)]`, because
test items are not visible across crates. It goes in a companion crate
under `testutil/` (root `<module>_testutil.rs`, crate
`<crate>_testutil`) with `testonly = True`, which makes Bazel refuse a
production dependency on it. `rust_test` targets are testonly by
definition and list the helper in `deps`.

## RS-6. Production code does not panic on purpose

Clippy denies `unwrap_used`, `expect_used`, `panic`, `todo`,
`unimplemented`, `unreachable`, `indexing_slicing`, `panic_in_result_fn`
and `exit`. Return a `Result`; if a value truly cannot be absent,
restructure the types so it cannot, or write
`#[allow(clippy::unwrap_used, reason = "...")]` on that one item. Tests
are exempt through `clippy.toml` (`allow-unwrap-in-tests` and its
siblings), because a failed unwrap in a test is a test failure.

What this does not buy: integer overflow, division by zero and allocation
failure still panic. `clippy::arithmetic_side_effects` would catch the
arithmetic cases but flags every `+`, which is not worth it.

## RS-7. Lint levels live in `.bazelrc`, and `-Dwarnings` stays

The policy is a list of `--@rules_rust//rust/settings:clippy_flag=...`
entries in `.bazelrc`, applied to every clippy action so a new target
cannot forget them. `clippy.toml` cannot set levels; it holds options
(the test exemptions) and must be named exactly `clippy.toml` or
rules_rust fails analysis.

`-Dwarnings` must stay first in that list. rules_rust adds it only when
no clippy flags are passed at all; the moment one flag is added, the
default disappears and every lint outside the explicit denies quietly
stops failing the build. Re-check this whenever the list is edited.

**Rejected.** Crate-root `#![deny(...)]` attributes assume a `lib.rs`
world and can be forgotten by a new crate; a per-target `lint_config` can
be omitted. Central flags cannot.

## RS-8. Pedantic is on, with an empty allow-list

`-Wclippy::pedantic` composes with `-Dwarnings`, so every pedantic lint
is fatal, in tests too. No `-A` lines exist: the tree was fixed instead of
allowed, and new pedantic lints arriving with a toolchain bump are fixed
the same way, as part of the bump. `-Wclippy::cognitive_complexity` is
the one nursery lint, a tripwire against monolithic functions; the rest
of nursery stays off and is adopted one lint at a time, if ever.

The blessed escape hatch is a site-level `#[allow]` with a reason;
`clippy::allow_attributes_without_reason` denies one without. The known
false-positive shape is `must_use_candidate` on a method whose point is
its side effect and whose return value is informational.

**Why.** Most code here is written by agents, and the cheapest correction
is to turn "bad but compiling" into a build failure the agent's own
compile-and-fix loop corrects before a human sees it. A trial over a
small tree found the pedantic fallout cheap to fix.

**Rejected.** A curated per-lint deny list: coverage frozen at whatever
was picked, re-surveyed forever. The group flag gets new coverage for
free.

## RS-9. Documentation lints hold a quality bar

`missing_errors_doc` and `missing_panics_doc` are enforced by pedantic.
A `# Errors` section names the conditions under which the function fails,
not just the error type; "returns an error if loading fails" is filler
that satisfies the lint and helps nobody. Same for `# Panics`.

## RS-10. No prints; log through `tracing`

`print_stdout` and `print_stderr` are denied, as is `dbg_macro`. A
program reports through `tracing` and `tracing-subscriber`. The entry
point carries the one allowed print, for the program's output or the
error that stops it, with an `#[allow]` naming the reason.

A log level is a configuration key, validated by hand: `EnvFilter` reads
a bare unknown word as a target name rather than a level, so an unknown
level would be silently accepted and turn logging off.

## RS-11. Derives follow the bucket policy

When adding a struct or enum, pick its bucket and derive the full set at
once:

- **Identity types** (field-free enums, key structs): `Debug, Clone,
  Copy, PartialEq, Eq, Hash, PartialOrd, Ord` (`Copy` only without owned
  fields). Derived `Ord` follows declaration order; when that order is
  semantic, the doc comment says it is load-bearing, otherwise that it is
  arbitrary but stable.
- **Never `Default`** on an enum that mirrors a proto enum: the wire
  rejects the unspecified value, and a Rust `Default` would silently
  invent the first variant.
- **Value types carrying `f64`**: `Debug, Clone, PartialEq` and stop.
  `Eq` and `Hash` are unsound over floats; NaN makes a value unequal to
  itself, so `PartialEq` is never a dedup key.
- **Validated newtypes over `String`**: construction only through
  `FromStr`, no `From<String>` bypassing validation; add `Display`,
  `AsRef<str>` and `Borrow<str>` for `&str` lookups, and restate in a
  comment why `Borrow` is sound (a one-field newtype's derived
  `Hash`/`Eq`/`Ord` agree with `str`'s).
- **Error types**: `Debug, Clone, PartialEq, Eq`, a hand-rolled `Display`
  and `impl Error`. No derive-macro error crate.

## RS-12. Dependencies are constructed once and passed down

No dependency-injection framework, no globals. The app crate's `run`
function is the composition root: it constructs every long-lived
dependency at startup and passes each down as a plain argument. A task
that needs a dependency gets its own clone; handles are cheap to clone by
design.

Start with a concrete type. Introduce a trait only when a second real
implementation exists. A test wanting different *behavior* counts (a
clock that stands still); a test wanting different *data* does not: give
the test the producing end of the real type instead. A small trait held
by one or two types is a generic parameter (static dispatch); one that
would thread through many types goes behind `Arc<dyn Trait>`.

Shared state that changes at runtime lives in a primitive built for the
access pattern (a `tokio::sync::watch` channel for snapshots), not in a
general lock grabbed by everyone. Never hold a lock or borrow guard across
an `await`.

## RS-13. Configuration is a file plus an environment layer

A program takes one command line option, `--config <file>`; settings live
in the file, not in flags. Layers, later wins: built-in defaults from an
embedded YAML file, the configuration file, then environment variables
with the repository's prefix (`{{ENV_PREFIX}}_`), nesting levels separated
by a double underscore. Every section is its own struct with
`deny_unknown_fields`; every field is required, so a default exists in
exactly one place and drift fails loudly in both directions.

**Rejected.** A flag that duplicates a configuration key: the same setting
in two places and a fourth precedence rule.

## RS-14. The runtime is built in the library

No `#[tokio::main]`. The app crate constructs the runtime and blocks on
the serve loop, so everything stays in testable library code. A server
splits `bind` from `serve`: binding first makes port 0 work and the real
address observable before serving starts. `serve` owns shutdown, installs
the signal handlers itself, and drains in-flight requests; tests inject
their own shutdown future through a crate-private variant.

## RS-15. Third-party crates are `crate.spec` entries

Declared in `MODULE.bazel` in crate_universe's direct-dependency mode,
sorted by package, referenced as `@crates//<package>` (never
`@crates//:<package>`). Direct dependencies need no repin; the next build
updates `MODULE.bazel.lock`. A proc-macro crate that arrives through a
feature (such as a `derive` feature) goes in plain `deps`;
`proc_macro_deps` is only for crates that are themselves proc macros and
are depended on directly. Prefer `default_features = False` with an
explicit feature list when a crate pulls in more than needed.

## RS-16. Editor support is a generated index

`bazel run @rules_rust//tools/rust_analyzer:gen_rust_project` writes
`rust-project.json`, gitignored, which rust-analyzer reads with no editor
settings. Rerun it after changing a BUILD file or `MODULE.bazel`; the edit
hook does so when the file exists.
