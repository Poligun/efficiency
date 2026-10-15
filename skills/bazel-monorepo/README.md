# bazel-monorepo

A skill that lays a Bazel-built, multi-language repository layout into a
new repository, or holds an existing repository or a design up against
that layout. The set covers Rust, Python 3, TypeScript and protobuf under
one build, with per-language lint, format and type checks as Bazel
targets, a patch-coverage gate, rules for where tests live and what they
may touch, automation as `bazel run` targets instead of shell, dependency
pinning with pinned sets, and the files a coding-agent harness needs.

## What is in the package

```
bazel-monorepo/
├── SKILL.md            the modes (apply, assess, consult) and the routing table
├── references/         the conventions: one document per concern, every rule with
│                       an ID, its reason, the rejected alternatives and when it applies;
│                       decisions.md is the generated one-page index
├── templates/          the files that implement the set, one directory per feature
│                       (core, rust, proto, typescript, hooks, claude, and compound
│                       directories such as proto+rust); conditional blocks and a few
│                       placeholders make one template serve every feature combination
├── scripts/            apply.py lays the templates into a target; build_index.py
│                       regenerates the index; scrub_check.py fails on any term the
│                       package must not contain (the term list stays outside the
│                       repository); test_apply.py covers all three
└── meta/               design rationale, the decision log and the improvement list
```

## Apply

```
python3 skills/bazel-monorepo/scripts/apply.py --target <repo> --name <module> --env-prefix <PREFIX> \
    --rust --proto --typescript --hooks --claude
```

Then, in the target: `tools/setup.sh`, `bazel build //...`,
`bazel test //...`. The target receives the convention documents under
`docs/conventions/`, an adoption record under `docs/decisions/`, an
`AGENTS.md` with the short version of every rule, and a `hello` program
per language that proves the wiring and is meant to be replaced. Python
is always present as the tooling language; the other languages are
chosen per repository. Every version is a pin verified together on the
date meta/design.md records.

## Assess

The agent walks `references/decisions.md` rule by rule against the
repository and writes a gap table with a verdict per rule, the migration
step, a cost, and a recommended order. For a design question it answers
with the rule, the reason and the rejected alternative.

## What it does not cover

Hosting platform, tracker, CI vendor, container registry, deployment,
secrets and observability. The references say what the gates expect of a
CI job and stop there; the pm-setup skill in this collection covers the
tracker.

## Keeping it honest

`python3 scripts/test_apply.py` and `python3 scripts/scrub_check.py` run
before any change lands. The end-to-end check is an apply with every
feature into an empty directory, through `bazel test //...`.
