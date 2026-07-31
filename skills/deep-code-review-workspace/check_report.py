#!/usr/bin/env python3
"""Mechanically check the structural assertions on a review report.

Some assertions have a right answer that doesn't need a model: does every cited
file:line actually exist, how many findings are there, did the run leave the
working tree dirty. Checking those with a script is faster, exactly repeatable
across iterations, and immune to a grader talking itself into a pass.

Usage:
  python3 check_report.py <report.md> --repo <path> [--baseline-status <file>]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

# `path/to/file.rs:104` — optionally absolute, in backticks, with a line range.
ANCHOR_RE = re.compile(
    r"`?(/?(?:[\w.\-]+/)+[\w.\-]+\.(?:rs|proto|py|go|ts|tsx|js|toml|sql|graphql))"
    r"(?::(\d+)(?:-(\d+))?)?`?"
)
SEVERITY_RE = re.compile(r"\b(CRITICAL|HIGH|MEDIUM|LOW)\b")
FIXCLARITY_RE = re.compile(r"\b(MECHANICAL|SCOPED|NEEDS[- ]DECISION)\b", re.I)
# A finding heading: "### F3 — ...", "### [HIGH] ...", "#### 1. ...", "### 1) ..."
FINDING_HEAD_RE = re.compile(
    r"^#{2,4}\s+(?:\**(?:F|BLR-|Finding\s*)\d+|\[?(?:CRITICAL|HIGH|MEDIUM|LOW)\]?\b|\d+[.)])",
    re.M | re.I)

# Paths a report may legitimately cite that do NOT exist in the reviewed repo:
# memory files it is *proposing* to create, and third-party crate sources it read
# to verify a claim. Counting these as broken anchors punishes correct behavior.
EXEMPT_ANCHOR_RE = re.compile(
    r"(^|/)\.claude/|(^|/)(cel|serde|tokio|bigdecimal|prost|chrono)-\d+\.\d+"
    r"|(^|/)(target|vendor|node_modules)/|\.cargo/registry/"
)


def check_anchors(text: str, repo: str) -> dict:
    seen, bad_path, bad_line, ok, exempt = set(), [], [], 0, []
    repo_abs = os.path.abspath(repo)
    for m in ANCHOR_RE.finditer(text):
        path, line = m.group(1), m.group(2)
        key = (path, line)
        if key in seen:
            continue
        seen.add(key)
        if EXEMPT_ANCHOR_RE.search(path):
            exempt.append(path)
            continue
        # Reports may cite absolute paths; normalise them into the repo.
        rel = path
        if path.startswith("/"):
            rel = os.path.relpath(path, "/")
        if os.path.isabs(path) or rel.startswith(repo_abs.lstrip("/")):
            rel = os.path.relpath("/" + rel, repo_abs) if not path.startswith(repo_abs) \
                  else os.path.relpath(path, repo_abs)
        full = os.path.join(repo, rel)
        if not os.path.isfile(full):
            # Prose routinely abbreviates `src/server/proto.rs` to `server/proto.rs`.
            # Try the common source roots before calling an anchor broken.
            for root in ("src", "lib", "app", "pkg", "internal", "proto"):
                cand = os.path.join(repo, root, rel)
                if os.path.isfile(cand):
                    full = cand
                    break
            else:
                bad_path.append(path)
                continue
        if line:
            try:
                with open(full, "rb") as fh:
                    n = sum(1 for _ in fh)
                if int(line) > n:
                    bad_line.append(f"{path}:{line} (file has {n} lines)")
                    continue
            except OSError:
                bad_path.append(path)
                continue
        ok += 1
    return {
        "anchors_checked": len(seen) - len(exempt),
        "anchors_valid": ok,
        "exempt": sorted(set(exempt)),
        "nonexistent_paths": sorted(set(bad_path)),
        "line_out_of_range": sorted(set(bad_line)),
        "passed": not bad_path and not bad_line,
    }


def check_worktree(repo: str, baseline: str | None) -> dict:
    cur = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                         capture_output=True, text=True).stdout.strip()
    if baseline and os.path.exists(baseline):
        want = open(baseline).read().strip()
        return {"passed": cur == want, "current": cur, "baseline": want}
    return {"passed": None, "current": cur, "note": "no baseline supplied"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--baseline-status")
    ap.add_argument("--max-findings", type=int, default=15)
    args = ap.parse_args()

    text = open(args.report, encoding="utf-8", errors="replace").read()
    findings = FINDING_HEAD_RE.findall(text)

    result = {
        "report": args.report,
        "chars": len(text),
        "S2_anchors_exist": check_anchors(text, args.repo),
        "S5_finding_count": {
            "count": len(findings),
            "cap": args.max_findings,
            "passed": len(findings) <= args.max_findings,
        },
        "S1_labels_present": {
            "severity_mentions": len(SEVERITY_RE.findall(text)),
            "fix_clarity_mentions": len(FIXCLARITY_RE.findall(text)),
            "findings": len(findings),
            "passed": (len(SEVERITY_RE.findall(text)) >= len(findings)
                       and len(FIXCLARITY_RE.findall(text)) >= len(findings)
                       and len(findings) > 0),
        },
        "S4_coverage_section": {
            "passed": bool(re.search(r"coverage|aspects? (ran|run|active|skipped)",
                                     text, re.I)),
        },
        "S7_worktree_clean": check_worktree(args.repo, args.baseline_status),
    }
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
