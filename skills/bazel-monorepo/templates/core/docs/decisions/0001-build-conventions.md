# 1. Build and language conventions

Status: accepted
Date: {{date}}

## Context

This repository adopts a Bazel-based build with one set of conventions for
every language it holds. The conventions were bootstrapped from a reusable
package rather than designed here, so this record states what this
repository chose and where it deviates; the conventions themselves, with
their rationale and the alternatives they rejected, live under
[docs/conventions/](../conventions/) and are owned by this repository from
now on. This repository owes the package no updates and takes none.

## Decisions

### What this repository answered

- **Languages**: {{languages}}. Python is always present as the tooling
  language behind the coverage gate and the automation.
- **Module name**: `{{name}}`, also the uv venv and the npm tree's name.
- **Environment prefix**: `{{ENV_PREFIX}}_`, for the skip variable of the
  coverage gate and any configuration a program reads from the environment.
- **Main branch**: `{{main_branch}}`, which the coverage gate diffs against.
- **Version control hooks**: {{hooks_answer}}
- **Agent harness**: {{harness_answer}}

### Deviations from the package

{{deviations}}

## Consequences

- `bazel build //... && bazel test //...` is the gate, and
  `bazel run //:coverage_gate` the patch-coverage gate, as
  [gates.md](../conventions/gates.md) describes.
- Every version in `MODULE.bazel`, `pyproject.toml` and
  `typescript/package.json` is a pin this repository now owns;
  [dependencies.md](../conventions/dependencies.md) says how they move.
- A continuous-integration job, where one exists, runs the same two gate
  commands with `--config=ci`; nothing else about the gate changes.
