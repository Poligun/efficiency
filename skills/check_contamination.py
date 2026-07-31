#!/usr/bin/env python3
"""Fail if a skill's instructions leak identifiers from its eval fixtures.

Why this exists: iteration 1 shipped skill files containing examples lifted
straight from the eval target — including a finding keyed to an uncommitted
change and a *fabricated* user quote. An agent could have reproduced several
must-find assertions without reading any code, which quietly invalidates the
benchmark. A hand-run grep caught most of it; a second pass with a wider
pattern list caught seven more. That is exactly the kind of check that should
not depend on remembering the right pattern list.

Terms are derived automatically from the fixtures and ground-truth files, so
adding a new eval target extends the check for free.

Usage:  python3 check_contamination.py [--verbose]
Exit:   0 clean · 1 contamination found
"""

from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Files that legitimately name the eval targets: design source and test definitions.
# Everything else is loaded by an agent mid-task and must stay generic.
EXEMPT_DIR_PARTS = ("/meta/", "/evals/", "-workspace/")

# Seed terms that no amount of derivation would produce, plus obvious repo names.
SEED_TERMS = {
    "ninniku", "poligun", "cel-alert", "billing-service", "AAPL",
    "rust_rules", "renko",
}

IDENT_RE = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+){1,}\b")
SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b")


def derive_terms(verbose: bool = False) -> set[str]:
    """Pull distinctive identifiers out of fixture source and ground-truth docs."""
    terms = set(SEED_TERMS)

    fixtures = os.path.join(HERE, "deep-code-review-workspace", "fixtures")
    for root, dirs, files in os.walk(fixtures):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for fn in files:
            if not fn.endswith((".py", ".rs", ".go", ".ts", ".proto")):
                continue
            try:
                body = open(os.path.join(root, fn), encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            # Multi-word snake_case identifiers are distinctive enough to matter and
            # rare enough not to false-positive on ordinary prose.
            terms.update(m for m in IDENT_RE.findall(body) if len(m) > 8)

    gt = os.path.join(HERE, "deep-code-review", "meta", "ground-truth")
    if os.path.isdir(gt):
        for fn in os.listdir(gt):
            body = open(os.path.join(gt, fn), encoding="utf-8", errors="replace").read()
            for m in re.findall(r"`([^`\s]+\.(?:rs|py|proto|yaml|ts|go))`", body):
                terms.add(os.path.basename(m))
            terms.update(SHA_RE.findall(body))

    # Generic across the whole ecosystem, or belonging to this skill rather than a
    # fixture. A term only indicts if seeing it in an instruction file would let an
    # agent guess a finding — `mod.rs` and `build.rs` exist in every Rust repo, and
    # `scope_detect.py` is our own script.
    terms -= {
        "repository", "conventions", "occurred_at", "account_id", "amount_cents",
        "requires_python", "application", "description", "properties", "operation_id",
        "scope_detect.py", "check_report.py", "build_benchmark.py",
        "mod.rs", "build.rs", "index.ts", "__init__.py", "main.rs", "lib.rs",
        "openapi.yaml", "pyproject.toml", "conftest.py",
    }
    if verbose:
        print(f"derived {len(terms)} terms", file=sys.stderr)
    return terms


def scan(terms: set[str]) -> list[tuple[str, int, str, str]]:
    hits = []
    pattern = re.compile("|".join(sorted((re.escape(t) for t in terms), key=len, reverse=True)))
    for skill in ("deep-code-review", "business-logic-review", "repo-index"):
        base = os.path.join(HERE, skill)
        if not os.path.isdir(base):
            continue
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
            rel_root = root.replace(HERE, "")
            if any(part in rel_root + "/" for part in EXEMPT_DIR_PARTS):
                continue
            for fn in files:
                if not fn.endswith((".md", ".py")):
                    continue
                path = os.path.join(root, fn)
                for i, line in enumerate(open(path, encoding="utf-8", errors="replace"), 1):
                    m = pattern.search(line)
                    if m:
                        hits.append((os.path.relpath(path, HERE), i, m.group(0), line.strip()[:110]))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    hits = scan(derive_terms(args.verbose))
    if not hits:
        print("CLEAN — no eval-fixture identifiers in skill instruction files")
        return 0

    print(f"CONTAMINATED — {len(hits)} occurrence(s):\n")
    for path, line, term, text in hits:
        print(f"  {path}:{line}  [{term}]")
        print(f"      {text}")
    print("\nSkill instructions must not name the repos they are evaluated against.")
    print("An agent can reproduce a leaked example without reading code, which makes")
    print("the benchmark measure recall of the instructions rather than of the diff.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
