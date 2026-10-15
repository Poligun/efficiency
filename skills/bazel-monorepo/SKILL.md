---
name: bazel-monorepo
description: Bootstraps a repository with a Bazel-built, multi-language layout (Rust, Python 3, TypeScript, protobuf) and the conventions, lint and format posture, testing rules, coverage gate and agent setup that go with it; or assesses an existing repository or a design against those conventions and produces a gap table and migration plan. Use this skill when the user wants to set up a new repo "the Bazel way", asks how a polyglot Bazel repo should be laid out, wants to convert an existing repo to Bazel with per-language gates, asks what the convention is for crates, modules, tests, lints, protos or dependency pins, or wants a design checked against established repo conventions before building it. Trigger on phrases like "set up a new repo", "bootstrap a Bazel repo", "bazel monorepo", "repo conventions", "how should I lay out", "convert this repo to Bazel", "what does the convention say about", "assess this repo against the conventions", "migration plan to Bazel".
---

# Bazel monorepo

You are either laying a known-good build and convention set into a
repository, or holding a repository or a design up against that set. The
set lives in `references/`: ten documents, one per concern, each rule with
a stable ID, the reason behind it, the alternatives it rejected and, where
it is not universal, when it applies. `templates/` holds the files that
implement the set, and `scripts/apply.py` lays them into a target. The
prose you write for people (the adoption record, a gap report, a plan)
follows the house voice: invoke the tech-writing skill once per run and
hold its rules.

Three facts bound everything below:

- **The set is opinionated and the rationale travels with it.** Deviate
  where a rule's "applies when" line says it does not apply, or where the
  user decides otherwise; record every deviation in the target's adoption
  record. Never silently drop a rule.
- **Versions are pins as of the package's date** (meta/design.md names
  it). Every toolchain and ruleset version in the templates was verified
  together on that date. Newer releases may exist; a bump is the target
  repository's decision, made with references/dependencies.md in hand,
  and pinned sets move together or not at all.
- **The package is generic on purpose.** It knows nothing about a hosting
  platform, a tracker, a CI vendor, deployment, secrets or observability.
  Where the user's context supplies one, the references say what the
  gates expect of it and nothing more.

## Pick the mode

- **Apply**: the target is a new or nearly empty repository and the user
  wants the setup in place. Procedure below.
- **Assess**: the target is an existing repository, or the user is
  designing something and wants it checked, or wants a plan to convert.
  Procedure below.
- **Consult**: the user asks what the convention is, or why. Load the one
  document the routing table names, answer with the rule ID, the rule, the
  reason and the rejected alternative, and say whether the rule's
  "applies when" line admits the user's case. No procedure.

## Routing table

Load only what the question needs. Each document opens with its scope.

| Question is about | Load |
| --- | --- |
| directory layout, file names, where tests go, when to split a file | references/layout.md |
| MODULE.bazel, .bazelrc, the wrappers, buildozer, the preset, hermeticity | references/bazel.md |
| crates, clippy policy, derives, error types, DI, config, the runtime | references/rust.md |
| Python modules, ruff, mypy, pytest, the process seam, program shape | references/python.md |
| apps, tsconfig, ESLint, Vitest, Vite, pnpm, knip, copy and locales | references/typescript.md |
| protos, codegen targets, the tonic set, contract style, reflection | references/proto.md |
| what a test may touch, seams, tests that start a service, coverage | references/testing.md |
| the gate commands, format-on-edit, the coverage gate, hooks, CI | references/gates.md |
| scripts, hooks, operator commands, shell policy | references/automation.md |
| adding a dependency, pins, pinned sets, bumps, the update routine | references/dependencies.md |
| every rule ID at a glance | references/decisions.md |
| the agent harness files (hooks, permissions, skills) and what they assume | references/agent-setup.md |

## Apply

### 1. Discover

Before asking anything, collect: whether the target directory is empty
or holds a build already (a `MODULE.bazel`, `WORKSPACE`, `Cargo.toml`,
`package.json` or `pyproject.toml` at the root means **assess**, not
apply); whether it is a git repository; whether an agent harness is in
use (`.claude/`, `AGENTS.md`); which `bazel` or `bazelisk` is on `PATH`
and whether the host is Linux x86_64, Linux arm64 or macOS arm64 (the
only hosts the pinned toolchains cover; say so if it is another).

### 2. Interview

One round, at most these questions, with proposals pre-filled from
discovery:

1. **Module name** (lowercase, underscores): the Bazel module, the uv
   venv, the npm tree's name. Propose the directory name.
2. **Environment prefix** (uppercase): for the coverage gate's skip
   variable and any configuration a program reads. Propose the module
   name upper-cased.
3. **Languages**: Rust, TypeScript, protobuf (needs Rust or TypeScript).
   Python is always present as the tooling language; say so rather than
   asking.
4. **Hooks**: git hooks (pre-commit format check, pre-push gate), only
   when the target is a git repository.
5. **Agent harness**: the Claude Code files (settings with pre-approved
   commands, the format-on-edit hook, two project skills), or none. The
   `AGENTS.md` rules file is written either way.
6. **Main branch name**, which the coverage gate diffs against. Propose
   `main`.

Any further deviation the user asks for is fine; it goes into the
adoption record, not into a template edit.

### 3. Lay the files

```
python3 <skill>/scripts/apply.py --target <repo> --name <name> --env-prefix <PREFIX> \
    [--rust] [--proto] [--typescript] [--hooks] [--claude] [--main-branch main]
```

The script refuses to overwrite an existing file unless `--force` is
given; on a re-run, pass it only after showing the user what changes.
It writes the templates, copies the convention documents that apply into
`docs/conventions/` with an index, and leaves the adoption record at
`docs/decisions/0001-build-conventions.md` with `{{placeholders}}` for
the interview answers. Fill those by hand (languages, hooks, harness,
deviations); the record is the one file whose prose is yours.

### 4. Bootstrap and verify

In the target, in this order, and fix what fails before moving on:

1. `tools/setup.sh` (enables the hooks, links the npm store for editors).
2. `bazel build //...` then `bazel test //...`. The first run fetches
   every toolchain; expect minutes. The lockfiles are shipped for the
   pinned manifests, so no lock step is needed unless the user changed a
   dependency.
3. `bazel run //python/hello -- world`, and `bazel run //rust/hello -- world`
   and `bazel build //typescript/web:app` where those languages are
   present, to see the example programs run.
4. `bazel run //:coverage_gate` runs only once there is a diff against
   the main branch; mention it rather than running it on an empty history.
5. `grep -rn '{{' docs/` finds any placeholder left unfilled.

The `hello` programs and the `greeting` proto are scaffolding that prove
the wiring: tell the user they are meant to be replaced by the first real
module, not kept, and that `/new-module` (when the harness files were
written) scaffolds a module the same shape.

### 5. Report

Say what was written (features, file count), what passed, the versions
pinned and the package date, and what the user owns from here: the
conventions under `docs/conventions/` are theirs to edit, with no sync
obligation back to this package.

## Assess

### 1. Read the target

Collect, without changing anything: the build system and manifests at
the root; the language trees and how modules are laid out; where tests
live; which linters, formatters and type checkers run and where (hooks,
CI, nowhere); how dependencies are declared and locked; whether any
version floats; how automation is written; what the agent setup is.
`references/decisions.md` is the checklist; walk it rule by rule.

### 2. Judge each rule

For every rule ID, one of: **holds**, **partial** (say what is missing),
**absent**, or **not applicable** (cite the rule's "applies when" line, or
the language's absence). Where the repository does something different on
purpose, say what and whether the rule's rationale still argues against
it; a reasoned local choice is a deviation to record, not a defect.

### 3. Write the gap table and the plan

The deliverable is a Markdown document the user can keep (propose
`docs/plans/bazel-conventions-gap.md` in the target, or wherever the
repository keeps plans). It holds:

- a verdict paragraph first: how far the repository is from the set, and
  the two or three moves that buy the most;
- the gap table: rule ID, verdict, what is missing, the migration step,
  and a cost (small, medium, large);
- the migration order, which is nearly always: Bazel core and toolchains
  (bazel.md) first, because nothing else runs without it; then the
  wrappers and gates for one language at a time, the one with the most
  code last; then layout moves (layout.md), which are mechanical once the
  gates catch mistakes; then testing seams and the coverage gate; then
  automation and dependency routine. Say why when the repository's shape
  argues for a different order;
- the rules the user should decide to decline, with the rationale they
  are declining, so the adoption record can carry them.

When the user is designing rather than converting, skip the table and
answer the design directly: which rules the design touches, what each
says, where the design and the rule part ways, and what to record if the
user keeps the design. Load only the documents the design touches.

## What this package does not do

It does not choose or configure a hosting platform, a tracker, a CI
vendor, a container registry, a deployment target, a secrets store or an
observability stack. The references say what the gates expect of a CI
job (run the same commands with `--config=ci`) and stop there. The
pm-setup skill in this collection covers the tracker.

## Keeping the package honest

`python3 scripts/test_apply.py` exercises the template renderer, the
feature selection and the generated index; `python3 scripts/scrub_check.py`
fails on any term the package must not contain, reading the term list
from a private file outside every repository (its docstring names the
path) and checking the public patterns alone when the file is absent.
Both run before any change to the package lands. The end-to-end check is the apply procedure
itself against an empty directory with every feature on, through
`bazel test //...`; meta/design.md records the last date it passed and on
which host.
