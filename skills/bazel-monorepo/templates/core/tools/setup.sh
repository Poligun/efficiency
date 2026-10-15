#!/usr/bin/env bash
# One-time repo setup. Safe to re-run. Shell is admitted here because the
# script is short and mostly configuration (docs/conventions/automation.md).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
{{#if hooks}}

git config core.hooksPath githooks
echo "git hooks enabled (core.hooksPath = githooks)"
{{/if}}
{{#if typescript}}

# The JavaScript tree resolves packages from the Bazel-built store, never
# from a local install. Editors and bazel run //typescript:knip read the
# store through this link; it is gitignored and dangles until the first
# build of a //typescript target.
if [ -e typescript/node_modules ] && [ ! -L typescript/node_modules ]; then
  echo "error: typescript/node_modules is a real directory (a local install?);" >&2
  echo "remove it so the link to the Bazel store can take its place." >&2
  exit 1
fi
ln -sfn ../bazel-bin/typescript/node_modules typescript/node_modules
echo "typescript/node_modules linked to the Bazel store"
{{/if}}
