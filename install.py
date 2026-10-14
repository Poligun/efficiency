#!/usr/bin/env python3
"""Install this repo's skills into the current user's agent skill trees.

Idempotent and cross-platform (Linux, macOS, WSL, native Windows). What it does:

1. Links every skill under skills/ (a directory holding a SKILL.md) into
   <home>/.claude/skills/<name>, and into <home>/.agents/skills/<name> when that
   cross-harness tree exists. A link is a symlink; on Windows without symlink
   rights (Developer Mode off, not elevated) it falls back to a junction.
   An existing link is re-pointed; a real file or directory aborts the install.
2. For tech-writing, checks the digest's corpus traceability first, then writes
   references/digest.md into a marked block in <home>/.claude/CLAUDE.md, and
   with --repo also into <repo>/AGENTS.md. Re-runs refresh the block in place.

Skills link by absolute path, so moving the clone means re-running the install.
The block logic is the ADR 2 contract that skills/tech-writing/scripts/install.sh
used to carry; that script is now a shim over this one.

Usage:
  python3 install.py                          all skills + global digest
  python3 install.py --repo PATH              also the digest in PATH/AGENTS.md
  python3 install.py --skill tech-writing     only the named skills (repeatable)
  python3 install.py --dry-run                print the plan, change nothing

On native Windows run it as `python install.py` (or `py install.py`):
`python3` there is often the Microsoft Store stub. TW_DIGEST_FILE overrides the
digest path (used by the tests).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
SKILLS_DIR = os.path.join(REPO_DIR, "skills")
TECH_WRITING = "tech-writing"
MARK_OPEN = "<!-- tech-writing-digest v1 -->"
MARK_CLOSE = "<!-- /tech-writing-digest -->"


class InstallError(Exception):
    pass


def discover_skills(skills_dir: str = SKILLS_DIR) -> list[str]:
    """Names of the directories under skills_dir that hold a SKILL.md."""
    return sorted(
        name for name in os.listdir(skills_dir)
        if os.path.isfile(os.path.join(skills_dir, name, "SKILL.md")))


def is_junction(path: str) -> bool:
    if hasattr(os.path, "isjunction"):  # Python 3.12+
        return os.path.isjunction(path)
    if os.name != "nt":
        return False
    try:
        return bool(os.readlink(path)) and not os.path.islink(path)
    except (OSError, ValueError):
        return False


def is_link(path: str) -> bool:
    return os.path.islink(path) or is_junction(path)


def make_link(target: str, link: str) -> str:
    """Create link -> target; returns the kind of link made."""
    try:
        os.symlink(target, link, target_is_directory=True)
        return "symlink"
    except OSError:
        if os.name != "nt":
            raise
    # Junctions need no privilege and work for local directories.
    proc = subprocess.run(["cmd", "/c", "mklink", "/J", link, target],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise InstallError(f"could not link {link}: {proc.stderr.strip()}")
    return "junction"


def link_skill(name: str, tree: str, dry_run: bool) -> None:
    target = os.path.join(SKILLS_DIR, name)
    link = os.path.join(tree, name)
    if dry_run:
        print(f"would link {link} -> {target}")
        return
    os.makedirs(tree, exist_ok=True)
    if os.path.lexists(link):
        # Removes the link only; on Windows this covers directory symlinks
        # and junctions too. The target's contents are never touched.
        os.unlink(link)
    kind = make_link(target, link)
    print(f"linked {link} -> {target} ({kind})")


def digest_path() -> str:
    return os.environ.get("TW_DIGEST_FILE") or os.path.join(
        SKILLS_DIR, TECH_WRITING, "references", "digest.md")


def check_digest(digest: str) -> None:
    if not os.path.isfile(digest):
        raise InstallError(f"digest not found at {digest}")
    checker = os.path.join(SKILLS_DIR, TECH_WRITING, "scripts", "prose_checks.py")
    proc = subprocess.run([sys.executable, checker, "digest", "--digest", digest],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise InstallError("digest failed corpus traceability; "
                           "fix references/digest.md first")


def render_block(content: str, digest_body: str) -> str:
    """content with the marked digest block replaced, or appended if absent."""
    block = f"{MARK_OPEN}\n{digest_body}\n{MARK_CLOSE}\n"
    if MARK_OPEN in content and MARK_CLOSE in content:
        head, rest = content.split(MARK_OPEN, 1)
        _, tail = rest.split(MARK_CLOSE, 1)
        return head + block + tail.lstrip("\r\n")
    if not content:
        return block
    if not content.endswith("\n"):
        content += "\n"
    return content + "\n" + block


def write_block(target: str, digest: str, dry_run: bool) -> None:
    if dry_run:
        print(f"would write digest block to {target}")
        return
    with open(digest, encoding="utf-8") as f:
        digest_body = f.read().strip()
    content = ""
    if os.path.exists(target):
        # newline="" keeps the file's own line endings on every platform.
        with open(target, encoding="utf-8", newline="") as f:
            content = f.read()
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="") as f:
        f.write(render_block(content, digest_body))
    print(f"digest block written to {target}")


def install(home: str, skills: list[str], repo: str | None, dry_run: bool) -> None:
    known = discover_skills()
    unknown = sorted(set(skills) - set(known))
    if unknown:
        raise InstallError(f"unknown skill(s): {', '.join(unknown)}; "
                           f"known: {', '.join(known)}")
    if repo is not None and not os.path.isdir(repo):
        raise InstallError(f"--repo path does not exist: {repo}")
    digest = digest_path()
    if TECH_WRITING in skills:
        check_digest(digest)

    trees = [os.path.join(home, ".claude", "skills")]
    agents_tree = os.path.join(home, ".agents", "skills")
    if os.path.isdir(agents_tree):
        trees.append(agents_tree)
    # Check every link path before changing any, so a conflict aborts cleanly.
    for tree in trees:
        for name in skills:
            link = os.path.join(tree, name)
            if os.path.lexists(link) and not is_link(link):
                raise InstallError(
                    f"{link} exists and is not a link; move it aside first ({name})")
    for tree in trees:
        for name in skills:
            link_skill(name, tree, dry_run)

    if TECH_WRITING in skills:
        write_block(os.path.join(home, ".claude", "CLAUDE.md"), digest, dry_run)
        if repo is not None:
            write_block(os.path.join(repo, "AGENTS.md"), digest, dry_run)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install this repo's skills for the current user.")
    parser.add_argument("--skill", action="append", dest="skills", metavar="NAME",
                        help="install only this skill (repeatable); default: all")
    parser.add_argument("--repo", metavar="PATH",
                        help="also write the tech-writing digest into PATH/AGENTS.md")
    parser.add_argument("--home", default=os.path.expanduser("~"),
                        help="home directory to install into (default: ~)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would change and change nothing")
    args = parser.parse_args(argv)
    try:
        install(args.home, args.skills or discover_skills(), args.repo, args.dry_run)
    except (InstallError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
