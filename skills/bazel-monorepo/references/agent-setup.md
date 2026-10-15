# Agent setup

Scope: the files the apply mode writes for a coding-agent harness, what
each assumes, and how a repository without that harness gets the same
effect. Audience: the agent applying the package, and anyone wiring a
different harness. This document stays in the package; it is not copied
into a target repository.

## AG-1. `AGENTS.md` is the one rules file

`AGENTS.md` at the root holds the rules for coding agents: the short
version of every convention document, with a link to the document that
wins when the two disagree. `CLAUDE.md` is one line, `@AGENTS.md`, which
Claude Code follows as an import; other harnesses read `AGENTS.md`
directly. One file to keep in step with the conventions instead of one
per tool.

**Why.** The rules change with the conventions, and two copies drift.

## AG-2. Formatting runs on every edit through a hook

`.claude/settings.json` registers a `PostToolUse` hook on `Edit|Write`
that runs `.claude/hooks/format.sh`, a shim over `bazel run //:format --
<file>` (and `bazel run //:buildifier` for Starlark). Files are formatted
the moment they are written, so the format tests cannot fail later and
no agent turn is spent on formatting. The hook exits without a Bazel
round trip for files outside the repository or of a language the entry
point does not format, so a documentation edit never waits on the
workspace lock.

A `SessionStart` hook runs `tools/setup.sh`, so a session cannot forget
the once-per-clone setup.

No hook runs `bazel test //...` at the end of every agent turn, on
purpose: slow and noisy. The deterministic backstop is the
pre-push hook where git is in use, and a CI job where one exists.

**Another harness.** Wire the same two commands to whatever "after a file
is written" and "at session start" events it offers. Without any harness,
the pre-commit hook catches an unformatted file at commit time.

## AG-3. Everyday commands are pre-approved; risky verbs ask

The settings file allows `bazel build`, `bazel test`, `bazel query`, the
format and buildifier targets, the coverage gate and buildozer without a
prompt. A repository that grows an operator command (automation.md AU-3)
adds its read-only verbs to the allow list and its verbs that reach
another machine or touch secrets to the ask list; anything that decrypts
a secret goes on the deny list.

## AG-4. Two project skills encode the recipes that are easy to get wrong

`.claude/skills/new-module/` scaffolds a module library in any of the
three languages with the two-declaration BUILD file, the root file named
after the directory, and the buildozer wiring. `.claude/skills/add-dependency/`
adds a crate, a Python package or an npm package through the right
manifest and lockfile. Both point at `docs/conventions/` as the authority.
A harness without project skills gets the same content as sections of
`AGENTS.md`.

## AG-5. The agent setup assumes nothing about hosting

No file written here names a hosting platform, a tracker or a CI vendor.
A repository that adopts the pm-setup skill's tracker conventions appends
that skill's `AGENTS.md` section; the two sections do not overlap.
