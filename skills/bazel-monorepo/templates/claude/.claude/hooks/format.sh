#!/usr/bin/env bash
# Claude Code PostToolUse hook: formats the file just edited through the one
# formatter entry point (bazel run //:format), and for Starlark also applies
# buildifier's lint fixes (bazel run //:buildifier), so the format test
# targets cannot fail later on formatting. Receives the tool call as JSON on
# stdin; the edited path is .tool_input.file_path. Exit 2 is the hook code
# that feeds stderr back to the model.
#
# A shim by policy (docs/conventions/automation.md): it holds no formatting
# logic.
set -euo pipefail
cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

file="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input", {}).get("file_path", ""))')"

# Only act on files inside this repo, and only on the languages the entry
# point formats; anything else exits without a Bazel round trip, so a
# documentation edit never waits on the workspace lock.
case "$file" in
    "$PWD"/*) ;;
    *) exit 0 ;;
esac
case "$file" in
    *.py | *.bzl | *.bazel) ;;
{{#if rust}}
    *.rs) ;;
{{/if}}
{{#if typescript}}
    *.ts | *.tsx | *.js | *.mjs | *.cjs | *.json | *.jsonc | *.css | *.html) ;;
{{/if}}
    *) exit 0 ;;
esac

bazel run //:format -- "$file" || { echo "formatting failed: $file" >&2; exit 2; }

# Starlark: buildifier's lint fixes (an unused load, for example), which the
# format entry point does not apply.
case "$file" in
    *.bzl | *.bazel)
        bazel run //:buildifier || { echo "buildifier failed: $file" >&2; exit 2; }
{{#if rust}}
        # The rust-analyzer index for the human's editor, which only exists
        # on machines where someone generated it.
        if [[ -f rust-project.json ]]; then
            bazel run @rules_rust//tools/rust_analyzer:gen_rust_project || exit 2
        fi
{{/if}}
        ;;
esac
