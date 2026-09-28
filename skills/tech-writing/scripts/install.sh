#!/usr/bin/env bash
# Installer for the tech-writing skill and its ambient digest (issue #9, ADR 2).
#
# The install logic lives in the repo-level install.py (issue #23), which
# installs every skill on every platform. This shim keeps the original entry
# point: it installs tech-writing alone, and passes --repo <path> through.
# New machine setup: clone + run install.py (or this script for tech-writing).
# TW_DIGEST_FILE overrides the digest path (used by test_install.py).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/../../../install.py" --skill tech-writing "$@"
