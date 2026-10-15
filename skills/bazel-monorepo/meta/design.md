# bazel-monorepo: design

> Status: first iteration, 2026-10-15. Distilled from a private
> repository's decision records and build files, with every product,
> domain and host name removed; the scrub check in `scripts/` reads the
> forbidden list from a private file outside the repository.

## What this is

Two use cases share one corpus. An agent bootstrapping a repository wants
the setup applied mechanically and green; an agent designing, reviewing
or planning a migration wants to know what the conventions are, why each
exists, what was rejected, and where deviation is sanctioned. The corpus
(`references/`) serves both: every rule carries an ID, a reason, the
rejected alternatives and an "applies when" line where it is not
universal. The templates implement the corpus; `apply.py` lays them down;
the assess mode reads the corpus as a checklist.

## The shape

- **One skill, two modes, plus consult.** The assess mode is the apply
  mode's checklist read in reverse, so one corpus serves both and nothing
  drifts. A separate assess skill would have duplicated the routing.
- **Deterministic apply.** Copying forty files with conditional sections
  is not model work. `apply.py` does it, with `{{#if feature}}` blocks and
  four placeholders, and refuses to overwrite without `--force`. The
  agent's job is the interview, the adoption record, and the bootstrap.
- **The references double as the target's docs.** `apply.py` copies the
  documents that apply into `docs/conventions/`, so the target is
  self-contained: its `AGENTS.md` points at files it owns, and the
  rationale survives without the skill. No sync obligation back.
- **Fresh examples.** The `hello` programs, the `greeting` proto and
  every example in the references were written for this package. Nothing
  is lifted from the source repository except infrastructure (the
  wrappers, the lint wiring, the tool programs), which carries no domain.
- **Python always on.** The coverage gate and the automation shape need
  a Python toolchain, so the Python layout, wrappers and gates are part of
  the core and not a choice. The interview says so instead of asking.
- **Versions are pins as of the package date.** The templates carry the
  versions verified together on 2026-10-15: Bazel 9.2.0, rules_rust
  0.71.3, Rust 1.97.1, toolchains_llvm 1.10.0 with LLVM 20.1.8, rules_py
  1.12.1 with uv 0.11.6 and CPython 3.14, rules_lint 2.9.0, rules_js
  3.4.1, rules_ts 3.10.1, rules_nodejs 6.7.5 with Node 24.18.0 and pnpm
  10.34.5, protobuf 35.1, the tonic 0.12 set, TypeScript 6.0.3, Vite 7,
  Vitest 5, ESLint 10. The lockfiles for the pinned manifests ship with
  the templates so the first build needs no lock step.

## What was verified

The end-to-end check is `apply.py` with every feature into an empty
directory, then `tools/setup.sh`, `bazel build //...` and
`bazel test //...`. Last passed on 2026-10-15 on Linux x86_64 (WSL2)
with every feature on (87 test targets). The host workaround that
machine needed (a library path for the pinned linker on a newer Linux
distribution) is machine-local and not part of the package.

## Out of scope, on purpose

Hosting platform, tracker, CI vendor, container images, deployment,
secrets, observability, the operator command's verbs, screenshot tests,
the i18n catalog machinery. Each is either covered by another skill in
this collection (the tracker) or too tied to a product to be generic. The
references name the principle where one exists (automation.md AU-3 for
the operator command, typescript.md TS-9 for copy) and stop at the
mechanism sketch.
