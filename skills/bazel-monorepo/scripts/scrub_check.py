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
  `~/.config/efficiency/scrub-terms.txt`. A list named by the flag or the
  variable must exist. Only when none is named and the default is absent
  does the check run the public patterns alone, and it says so, since that
  verdict is weaker.

Usage:  python3 scrub_check.py [--root DIR] [--terms FILE]
Exit:   0 clean · 1 a leak was found · 2 a named term list is missing
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
    (re.compile(r"/home/[^/\s]+/|/Users/[^/\s]+/|[A-Za-z]:\\Users\\[^\\\s]+"), "absolute home path"),
    (re.compile(r"\bgh (pr|issue|label)\b"), "tracker command"),
)

TEXT_SUFFIXES = (
    ".md", ".py", ".rs", ".toml", ".json", ".jsonc", ".yaml", ".yml", ".ts",
    ".tsx", ".js", ".mjs", ".css", ".html", ".proto", ".sh", ".bazel", ".bzl",
    ".bazelrc", ".bazelversion", ".bazelignore", ".gitignore", ".lock", ".txt", "",
)
SKIP_DIRS = {"__pycache__", ".git", "node_modules"}


class MissingTerms(Exception):
    """An explicitly configured term list does not exist."""


def terms_file(explicit: str | None, env: str | None = None) -> str | None:
    """The private term list to use, or None when none was configured.

    A list named explicitly (`--terms` or the environment variable) must
    exist; a missing one is an error, never a silent fallback to a weaker
    scan. Only the default path may be absent.
    """
    for candidate in (explicit, env):
        if candidate:
            path = os.path.expanduser(candidate)
            if not os.path.isfile(path):
                raise MissingTerms(f"term list not found: {candidate}")
            return path
    default = os.path.expanduser(DEFAULT_TERMS)
    return default if os.path.isfile(default) else None


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
        # This file holds the public patterns' own source text, which the
        # patterns would match; it is scanned for private terms only.
        self_file = os.path.abspath(path) == os.path.abspath(__file__)
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
            if self_file:
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
    try:
        path = terms_file(args.terms, os.environ.get("SCRUB_TERMS_FILE"))
    except MissingTerms as error:
        print(f"scrub: {error}", file=sys.stderr)
        return 2
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
