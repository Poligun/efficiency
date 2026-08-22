#!/usr/bin/env bash
# Installer for the tech-writing skill and its ambient digest (issue #9, ADR 2).
#
# Idempotent. What it does:
#   1. Symlinks the skill into $HOME/.claude/skills/tech-writing.
#   2. Writes references/digest.md into a marked block in $HOME/.claude/CLAUDE.md,
#      creating the file if needed; re-runs refresh the block in place.
#   3. With --repo <path>, writes the same marked block into <path>/AGENTS.md.
#
# The digest must pass corpus traceability (prose_checks.py digest) or the
# install aborts before touching anything. New machine setup: clone + run.
# TW_DIGEST_FILE overrides the digest path (used by test_install.py).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
DIGEST="${TW_DIGEST_FILE:-$SKILL_DIR/references/digest.md}"
MARK_OPEN="<!-- tech-writing-digest v1 -->"
MARK_CLOSE="<!-- /tech-writing-digest -->"

REPO_PATH=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      [[ $# -ge 2 ]] || { echo "error: --repo needs a path" >&2; exit 2; }
      REPO_PATH="$2"; shift 2 ;;
    *)
      echo "usage: install.sh [--repo <path>]" >&2; exit 2 ;;
  esac
done

[[ -f "$DIGEST" ]] || { echo "error: digest not found at $DIGEST" >&2; exit 1; }

if ! python3 "$SCRIPT_DIR/prose_checks.py" digest --digest "$DIGEST" > /dev/null; then
  echo "error: digest failed corpus traceability; fix references/digest.md first" >&2
  exit 1
fi

if [[ -n "$REPO_PATH" && ! -d "$REPO_PATH" ]]; then
  echo "error: --repo path does not exist: $REPO_PATH" >&2
  exit 1
fi

link_skill() {
  local link="$HOME/.claude/skills/tech-writing"
  mkdir -p "$HOME/.claude/skills"
  if [[ -e "$link" && ! -L "$link" ]]; then
    echo "error: $link exists and is not a symlink; move it aside first (tech-writing)" >&2
    exit 1
  fi
  ln -sfn "$SKILL_DIR" "$link"
  echo "linked $link -> $SKILL_DIR"
}

write_block() {
  local target="$1"
  mkdir -p "$(dirname "$target")"
  TW_TARGET="$target" TW_DIGEST="$DIGEST" \
  TW_OPEN="$MARK_OPEN" TW_CLOSE="$MARK_CLOSE" python3 - <<'PY'
import os

target = os.environ["TW_TARGET"]
mark_open = os.environ["TW_OPEN"]
mark_close = os.environ["TW_CLOSE"]
with open(os.environ["TW_DIGEST"], encoding="utf-8") as f:
    digest = f.read().strip()

block = f"{mark_open}\n{digest}\n{mark_close}\n"
content = ""
if os.path.exists(target):
    with open(target, encoding="utf-8") as f:
        content = f.read()

if mark_open in content and mark_close in content:
    head, rest = content.split(mark_open, 1)
    _, tail = rest.split(mark_close, 1)
    content = head + block + tail.lstrip("\n")
elif content:
    if not content.endswith("\n"):
        content += "\n"
    content += "\n" + block
else:
    content = block

with open(target, "w", encoding="utf-8") as f:
    f.write(content)
print(f"digest block written to {target}")
PY
}

link_skill
write_block "$HOME/.claude/CLAUDE.md"
if [[ -n "$REPO_PATH" ]]; then
  write_block "$REPO_PATH/AGENTS.md"
fi
