# Automation

Scope: scripts, hooks, operator commands and anything else that runs
tools on a developer's or an operator's behalf. Audience: anyone about to
write a script. Prerequisites: bazel.md, python.md.

Script text, checked in or generated, escapes every quality gate the
repository runs: nothing lints it, nothing tests it, nothing measures its
coverage. A repository that holds Rust to `clippy::pedantic` does not
hold its automation to no standard at all.

## AU-1. Automation is a `bazel run` target: a macro or rule plus a program

New automation enters as a `bazel run` target. The `.bzl` macro or rule
owns the wiring: attributes, defaults, dependencies, runfiles. The
runtime logic lives in a real program in a language the repository
builds: Python for tooling (python.md), Rust where the logic earns a
crate. The coverage gate is the template: a `py_binary` whose root file is
a shim over a library with planning functions and one `run` seam.

`.bzl` files hold declarations, not programs. Generating script text
inside a rule is still writing shell, and it is not an accepted pattern.

## AU-2. Shell survives only where it is short, precise and human readable

The bar for a shell script: a reader takes it in at a glance, it has at
most a guard clause of control flow, and it mostly execs into something
real. A seven-line hook enabler passes. A ninety-line script with
prompts, conditionals and cleanup traps does not; that is a program, and
programs get a real language. When in doubt, it is a program.

Hooks that version control or an agent harness runs may keep a thin
shell shim, because those tools require an executable file at a fixed
path; the shim execs into a Bazel-built program rather than carrying
logic. Each surviving shim carries a header line naming this rule, so
the next edit meets the rule in the file itself rather than on a tracker.

**Why the header line.** A migration rule that lives only on an issue
fails: a script changed twice without converting because nothing in the
file said it should.

## AU-3. One operator command with nouns and verbs

Where the repository has an operator surface (deploy, secrets, a local
dependency stack), it is one `bazel run //:ops -- <noun> <verb>` program
rather than a script per job. Each verb plans its commands as data and
runs them through the process seam, so every verb is tested with the
recording runner and no test spawns the real tool. Host tools the verbs
call (a container engine, an SSH client) come from `PATH`, and a verb
that cannot find one reports the tool and its install hint through the
same failure path as any other error. Required host state is data,
checked on every run, with the verb that fixes each missing piece named
in the failure.

An agent harness's permission list follows the verbs: the read-and-build
commands are pre-approved, verbs that reach another machine or touch
secrets ask first.

**Applies when.** The repository operates something. A library has no
operator surface.

## AU-4. A nested `bazel run` is recorded in the docstring

A `bazel run` target may invoke `bazel run` on another target when a
`data` dependency would pull an unrelated build (a container image, an
editor index) into every invocation of the first. The calling program's
docstring records the nested invocation, because Bazel's graph does not
show it.

## AU-5. Programs read Bazel's environment, never version control

A program finds the repository through `BUILD_WORKSPACE_DIRECTORY` and
the invoking directory through `BUILD_WORKING_DIRECTORY`, never through
`git rev-parse`. The one exception is a hook shim, which git itself
starts and which may use `git rev-parse --show-toplevel` to find the
Bazel workspace.
