#!/usr/bin/env python3
"""Lay the bazel-monorepo templates into a target repository.

The templates live under ../templates/<feature>/, one directory per
feature; a directory named `a+b` applies only when both features are
selected. `core` is always selected. Inside a template, lines between
`{{#if feature ...}}` and `{{/if}}` survive only when every named feature
is selected (a `!` prefix negates one name); the marker lines themselves
are dropped. `{{name}}`, `{{ENV_PREFIX}}`, `{{main_branch}}` and `{{date}}`
are substituted everywhere; any other `{{placeholder}}` is left for the
agent to fill (the adoption record uses several).

The convention documents under ../references/ are copied into the
target's docs/conventions/, filtered by feature, with a README index.

Usage:
  python3 apply.py --target DIR --name NAME --env-prefix PREFIX
                   [--rust] [--proto] [--typescript] [--hooks] [--claude]
                   [--main-branch main] [--force] [--dry-run]

Exit: 0 on success, 1 when a target file exists and --force is not given.
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import shutil
import stat
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, "..", "templates")
REFERENCES = os.path.join(HERE, "..", "references")

FEATURES = ("rust", "proto", "typescript", "hooks", "claude")

# Which convention documents a target repository receives, by feature.
# `core` documents always apply.
CONVENTION_DOCS = (
    ("layout.md", "core"),
    ("bazel.md", "core"),
    ("rust.md", "rust"),
    ("python.md", "core"),
    ("typescript.md", "typescript"),
    ("proto.md", "proto"),
    ("testing.md", "core"),
    ("gates.md", "core"),
    ("automation.md", "core"),
    ("dependencies.md", "core"),
)

IF_RE = re.compile(r"^\s*\{\{#if ([^}]+)\}\}\s*$")
ENDIF_RE = re.compile(r"^\s*\{\{/if\}\}\s*$")
TEXT_SUFFIXES = (
    ".bazel", ".bzl", ".bazelrc", ".bazelversion", ".bazelignore", ".gitignore",
    ".md", ".py", ".rs", ".toml", ".json", ".jsonc", ".yaml", ".yml", ".ts",
    ".tsx", ".js", ".mjs", ".css", ".html", ".proto", ".sh", ".lock", ".txt",
)
TEXT_NAMES = {"pre-commit", "pre-push", "CLAUDE.md", "AGENTS.md"}
EXECUTABLE_NAMES = {"pre-commit", "pre-push", "setup.sh", "format.sh"}


class ApplyError(Exception):
    pass


def condition_holds(expression: str, selected: set[str]) -> bool:
    """True when every name in `expression` is selected (or, with `!`, not)."""
    for term in expression.split():
        negated = term.startswith("!")
        name = term[1:] if negated else term
        if name not in FEATURES and name != "core":
            raise ApplyError(f"unknown feature in condition: {term}")
        if (name in selected) == negated:
            return False
    return True


def render(text: str, selected: set[str], values: dict[str, str]) -> str:
    """Resolves the conditional blocks and substitutes the known placeholders."""
    out: list[str] = []
    stack: list[bool] = []
    for line in text.splitlines(keepends=True):
        opened = IF_RE.match(line)
        if opened:
            stack.append(condition_holds(opened.group(1), selected))
            continue
        if ENDIF_RE.match(line):
            if not stack:
                raise ApplyError("{{/if}} without {{#if}}")
            stack.pop()
            continue
        if all(stack):
            out.append(line)
    if stack:
        raise ApplyError("{{#if}} without {{/if}}")
    rendered = "".join(out)
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered


def is_text(path: str) -> bool:
    name = os.path.basename(path)
    return name in TEXT_NAMES or name.endswith(TEXT_SUFFIXES)


def feature_dirs(selected: set[str]) -> list[str]:
    """The template directories that apply, core first, in a stable order."""
    chosen = []
    for entry in sorted(os.listdir(TEMPLATES)):
        parts = set(entry.split("+"))
        if parts <= (selected | {"core"}):
            chosen.append(entry)
    chosen.sort(key=lambda entry: (entry != "core", entry))
    return chosen


def plan(selected: set[str]) -> list[tuple[str, str]]:
    """(source path, target-relative path) for every template file that applies."""
    files: list[tuple[str, str]] = []
    for feature in feature_dirs(selected):
        base = os.path.join(TEMPLATES, feature)
        for root, dirs, names in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            for name in sorted(names):
                source = os.path.join(root, name)
                files.append((source, os.path.relpath(source, base)))
    return files


def conventions(selected: set[str]) -> list[str]:
    """The convention documents the target receives."""
    return [doc for doc, feature in CONVENTION_DOCS if feature == "core" or feature in selected]


def conventions_index(docs: list[str]) -> str:
    lines = [
        "# Conventions",
        "",
        "The rules this repository builds and tests by, one document per concern.",
        "Each rule carries an ID, the reason behind it and the alternatives it",
        "rejected, so a reader can judge when a deviation is warranted; the",
        "adoption record in docs/decisions/0001-build-conventions.md lists the",
        "deviations this repository chose.",
        "",
    ]
    for doc in docs:
        lines.append(f"- [{doc}]({doc})")
    lines.append("")
    return "\n".join(lines)


def write(target: str, relative: str, content: bytes, force: bool, dry_run: bool, executable: bool) -> str:
    destination = os.path.join(target, relative)
    exists = os.path.exists(destination)
    if exists and not force:
        raise ApplyError(f"refusing to overwrite {relative}; pass --force to replace existing files")
    if not dry_run:
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        with open(destination, "wb") as handle:
            handle.write(content)
        if executable:
            mode = os.stat(destination).st_mode
            os.chmod(destination, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return f"{'replace' if exists else 'write'}  {relative}"


def apply(target: str, selected: set[str], values: dict[str, str], force: bool, dry_run: bool) -> list[str]:
    actions = []
    for source, relative in plan(selected):
        if is_text(source):
            with open(source, encoding="utf-8") as handle:
                content = render(handle.read(), selected, values).encode("utf-8")
        else:
            with open(source, "rb") as handle:
                content = handle.read()
        executable = os.path.basename(source) in EXECUTABLE_NAMES
        actions.append(write(target, relative, content, force, dry_run, executable))
    docs = conventions(selected)
    for doc in docs:
        with open(os.path.join(REFERENCES, doc), encoding="utf-8") as handle:
            content = render(handle.read(), selected, values).encode("utf-8")
        actions.append(write(target, os.path.join("docs", "conventions", doc), content, force, dry_run, False))
    actions.append(write(
        target, os.path.join("docs", "conventions", "README.md"),
        conventions_index(docs).encode("utf-8"), force, dry_run, False,
    ))
    return actions


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", required=True, help="the repository to write into")
    parser.add_argument("--name", required=True, help="the Bazel module name (lowercase, underscores)")
    parser.add_argument("--env-prefix", required=True, help="the environment variable prefix (uppercase)")
    parser.add_argument("--main-branch", default="main")
    for feature in FEATURES:
        parser.add_argument(f"--{feature}", action="store_true")
    parser.add_argument("--force", action="store_true", help="replace files that already exist")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[a-z][a-z0-9_]*", args.name):
        parser.error("--name must be lowercase letters, digits and underscores, starting with a letter")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", args.env_prefix):
        parser.error("--env-prefix must be uppercase letters, digits and underscores")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    selected = {feature for feature in FEATURES if getattr(args, feature)}
    if "proto" in selected and not ({"rust", "typescript"} & selected):
        print("apply: --proto needs --rust or --typescript to generate code for", file=sys.stderr)
        return 1
    values = {
        "name": args.name,
        "ENV_PREFIX": args.env_prefix,
        "main_branch": args.main_branch,
        "date": datetime.date.today().isoformat(),
    }
    try:
        actions = apply(os.path.abspath(args.target), selected, values, args.force, args.dry_run)
    except ApplyError as error:
        print(f"apply: {error}", file=sys.stderr)
        return 1
    for action in actions:
        print(action)
    print(f"{'planned' if args.dry_run else 'wrote'} {len(actions)} files into {args.target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
