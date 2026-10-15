#!/usr/bin/env python3
"""Fail if the package leaks anything from the repository it was distilled from.

The skill, its references, templates and meta notes are public and generic.
Nothing in them may name the originating repository, its product, its
domain, its hosts, its people or its tracker. This check scans every text
file in the package for two things:

- the shapes that smuggle a name in: references to numbered decision
  records, tracker issues by number, tracker commands and absolute home
  paths; these patterns are public and live here;
- a list of forbidden terms, which is private by construction and lives
  outside every repository: one term per line, matched case-insensitively,
  read from `--terms FILE`, else `$SCRUB_TERMS_FILE`, else
  `~/.config/efficiency/scrub-terms.txt`. Without the file the check runs
  the public patterns alone and says so, so a clean verdict on a machine
  without the list is weaker and the output makes that visible.

Usage:  python3 scrub_check.py [--root DIR] [--terms FILE]
Exit:   0 clean · 1 a leak was found
"""

from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.normpath(os.path.join(HERE, ".."))
DEFAULT_TERMS = os.path.join("~", ".config", "efficiency", "scrub-terms.txt")

# Patterns that smuggle a term in by shape.
PATTERNS = (
    (re.compile(r"\bADR\s*0\d{3}\b"), "numbered decision record from the source repository"),
    (re.compile(r"\(#\d+\)|\bissue #\d+|\bepic #\d+|\bPR #\d+"), "tracker reference"),
    (re.compile(r"/home/[a-z]+/|/Users/[a-z]+/"), "absolute home path"),
    (re.compile(r"\bgh (pr|issue|label)\b"), "tracker command"),
)

TEXT_SUFFIXES = (
    ".md", ".py", ".rs", ".toml", ".json", ".jsonc", ".yaml", ".yml", ".ts",
    ".tsx", ".js", ".mjs", ".css", ".html", ".proto", ".sh", ".bazel", ".bzl",
    ".bazelrc", ".bazelversion", ".bazelignore", ".gitignore", ".lock", ".txt", "",
)
SKIP_DIRS = {"__pycache__", ".git", "node_modules"}


def terms_file(explicit: str | None) -> str | None:
    """The private term list to use, or None when none exists."""
    for candidate in (explicit, os.environ.get("SCRUB_TERMS_FILE"), DEFAULT_TERMS):
        if candidate:
            path = os.path.expanduser(candidate)
            if os.path.isfile(path):
                return path
    return None


def load_terms(path: str | None) -> list[str]:
    if path is None:
        return []
    with open(path, encoding="utf-8") as handle:
        return [
            line.strip().lower() for line in handle
            if line.strip() and not line.lstrip().startswith("#")
        ]


def text_files(root: str):
    for current, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(names):
            suffix = os.path.splitext(name)[1]
            if suffix in TEXT_SUFFIXES or name in ("pre-commit", "pre-push"):
                yield os.path.join(current, name)


def scan(root: str, terms: list[str]) -> list[tuple[str, int, str, str]]:
    hits = []
    forbidden = re.compile("|".join(re.escape(term) for term in terms), re.IGNORECASE) if terms else None
    for path in text_files(root):
        if os.path.abspath(path) == os.path.abspath(__file__):
            continue
        relative = os.path.relpath(path, root)
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                lines = handle.readlines()
        except OSError:
            continue
        for number, line in enumerate(lines, 1):
            found = forbidden.search(line) if forbidden else None
            if found:
                hits.append((relative, number, found.group(0), line.strip()[:110]))
                continue
            for pattern, label in PATTERNS:
                if pattern.search(line):
                    hits.append((relative, number, label, line.strip()[:110]))
                    break
    return hits


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=PACKAGE)
    parser.add_argument("--terms", help="the private term list; see the module docstring for the defaults")
    args = parser.parse_args(argv)
    path = terms_file(args.terms)
    terms = load_terms(path)
    if path is None:
        print("scrub: no private term list found; checking the public patterns only", file=sys.stderr)
    hits = scan(args.root, terms)
    if not hits:
        source = f"{len(terms)} private terms and" if terms else "no term list,"
        print(f"CLEAN: {source} the public patterns, under {args.root}")
        return 0
    print(f"LEAK: {len(hits)} occurrence(s) under {args.root}:\n")
    for relative, number, term, text in hits:
        print(f"  {relative}:{number}  [{term}]")
        print(f"      {text}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
