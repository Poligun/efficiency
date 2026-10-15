# Gates

Scope: which checks exist, where they run, and what counts as done.
Audience: anyone about to call a change finished, and anyone wiring a
hook or a job that runs the checks. Prerequisite: bazel.md.

Formatting, linting and testing must not depend on anyone remembering to
run them. The gates are deterministic, cheap where they run often, and
recorded in one place.

## GA-1. `bazel build //...` and `bazel test //...` are the gate

`bazel build //...` compiles everything and runs the build-time checks:
clippy (a `rust_clippy` target produces a build output) and the
TypeScript type check (a `ts_project` emitting declarations).
`bazel test //...` runs the unit tests, the integration suites that start
their own services, and the test-time checks: rustfmt, ruff, the Python
format test, mypy, ESLint, Prettier and the buildifier check over every
Bazel file. Run both before calling work done; the second alone is "the
gate" in conversation because it builds what it tests.

Every check is a target the wrappers declare (bazel.md BZ-4), so adding a
library adds its checks, and nothing keeps a list of what to lint.

## GA-2. Formatting happens at edit time; the gates only confirm it

`bazel run //:format -- <file>` rewrites a file into shape. The agent
harness runs it after every edit through a hook, so the format tests
cannot fail later and no agent turn is spent on formatting. Starlark
also gets `bazel run //:buildifier` for lint fixes.

## GA-3. The patch-coverage gate runs once per change, before merge

`bazel run //:coverage_gate` runs `bazel coverage //...`, refuses a merged
lcov report with no records (a known failure mode after a Bazel or
toolchain upgrade, where coverage exits green and records nothing), then
runs diff-cover against the main branch with `--fail-under=95`. It judges
only the lines the change touched, so a failure points at what was just
written, not at a repository-wide number nobody can attribute. Project
coverage is a trend, not a gate.

It runs once per change, not in a pre-push hook: patch coverage is a
property of the finished change, and intermediate pushes should stay
fast. `{{ENV_PREFIX}}_SKIP_COVERAGE_GATE=1` skips it, with the same
standing as `git push --no-verify`: an escape hatch for the genuinely
unforeseen, visible when used, never routine.

Exclusions in `pyproject.toml`'s `[tool.diff_cover]` are file-level and
earned by evidence: added only after the gate has bitten twice for the
same justified reason, each with a comment saying what earned it. The
intended order of responses to a gate bite is to structure the code so
the untestable wiring concentrates in the entry point, then exclude the
file, then the skip variable. Moving code into an excluded file to dodge
the gate is not an accepted use.

**Rejected.** A third-party coverage service: every hosted option needs
a repository grant, an upload token, or coverage data leaving the
machine, and the one that keeps data inside the hosting platform presumes
per-change cloud CI. Function-level exclusion: not available in stable
Rust's coverage path as of this writing.

## GA-4. Version-control hooks are shims, checked in, and optional

Where the repository is under git, `githooks/` holds the hooks and
`tools/setup.sh` enables them once per clone with
`git config core.hooksPath githooks`. `pre-commit` checks formatting only
and compiles nothing (the buildifier test, and the rustfmt aspect with a
bare `--output_groups=rustfmt_checks`, which replaces the default output
group so no rustc action runs). `pre-push` runs the full gate. Hooks
check the working tree, not the exact commits pushed; accepted. Each hook
is a shim by policy (automation.md): any logic beyond a guard clause
moves into a `bazel run` target the hook execs.

A repository under another version control system, or none, runs the
same commands by hand or through its harness; nothing in the gates
depends on git.

## GA-5. Continuous integration runs the same commands, and nothing else

A CI job, where one exists, runs `bazel build //...`, `bazel test //...`
and the coverage gate with `--config=ci` (bazel.md BZ-2). The gates are
the local commands; CI makes them non-optional, it does not define them.
Two shapes have worked: a job on every change, and a scheduled daily run
that exits early when the main branch has not moved and reports a red
result as a signal to fix forward. The choice depends on where the warm
build cache lives and what the runner's disk and minutes allow; neither
changes a line in the repository outside the job file.

A scheduled backstop has one weakness worth knowing: a red result on a
scheduled job reaches no inbox unless the job files or notifies, so wire
that notification when choosing that shape.

## GA-6. What "done" means

- `bazel build //... && bazel test //...` passes.
- For a change about to merge, `bazel run //:coverage_gate` passes or
  the skip is called out in the change description with its reason.
- New lints arriving with a toolchain bump are fixed in the bump, not
  allowed away (rust.md RS-8, python.md PY-5).
