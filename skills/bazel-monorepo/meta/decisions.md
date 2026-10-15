# bazel-monorepo: decision log

Dated entries, newest last. Each records a choice about the package
itself, not about the conventions it carries; those live in `references/`
with their own rationale.

## 2026-10-15: one skill with apply, assess and consult modes

Considered two skills (a setup skill and an assess skill, the pm-setup
and project-manager split). Rejected: the two modes read the same corpus
and the assess checklist is the apply order reversed, so a split would
duplicate the routing table and let the two drift. The tech-writing
skill's two-mode shape is the precedent.

## 2026-10-15: apply is a script, not a procedure

The first draft had the agent copy templates by hand from a manifest.
Rejected on the package's own automation rule: deterministic work is a
program. `apply.py` with `{{#if}}` blocks replaced a "parts" scheme
(language-specific fragments concatenated in order) because a whole file
with conditional sections reads as the file it produces, and a fragment
does not.

## 2026-10-15: references are copied into the target

The alternative was to point the target's `AGENTS.md` at the skill. The
target must stand alone: a later agent session there may not have the
skill installed, and the user asked for the rationale to travel. The cost
is a copy that can drift from the package; accepted, with no sync
obligation in either direction, as pm-setup does with its templates.

## 2026-10-15: Python is part of the core

The source repository's Python arrived for the coverage gate before it
had a Python program, and its conventions came later. Here the coverage
gate, the process seam and the mypy runner are Python programs under the
conventions from the start, so the Python layout is not optional. The
interview tells the user rather than asking.

## 2026-10-15: the Python binary wrapper gains an `args` attribute

The source wrapper had none; the coverage gate there lived outside the
wrappers. Here the gate is a `py_binary` under the wrappers, and its
threshold and compare branch are fixed arguments of the target. A
one-attribute addition, `configurable = False` like the rest.

## 2026-10-15: lockfiles ship with the templates

`uv.lock` and `pnpm-lock.yaml` for the pinned manifests are templates
rather than generated at bootstrap, because rules_js refuses a missing
pnpm lockfile at module resolution and a bootstrap that needs a
two-phase `MODULE.bazel` is a trap. The regeneration commands are in
dependencies.md for when a manifest changes.

## 2026-10-15: fresh examples only

Per the user's instruction: no example is lifted or distilled from the
source repository, with the exception of infrastructure code (wrappers,
lint wiring, the Vitest launcher, the Prettier check, the mypy runner,
the process seam), which carries no domain. The `hello` programs and the
`greeting` proto were written for the package.

## 2026-10-15: the C toolchain and a rules_go pin are part of the core

Found by the core-only acceptance run on a host with no system compiler.
Without Rust, nothing registered a C toolchain, and the format entry
point's launcher (rules_multirun) failed to resolve one; and the
transitive rules_go that rules_lint's format runner pulls in predates
Bazel 9's removal of the native CcInfo symbol, which the proto feature's
protobuf dependency had been lifting by accident. The LLVM toolchain
block moved from the Rust feature into the core, and `rules_go` is
pinned at the root with a comment saying why. Both keep the promise that
a fresh Linux machine needs only Bazel.
