#!/usr/bin/env python3
"""Tests for install.py, the repo-level skill installer (issue #23).

The contract: link every directory under skills/ that holds a SKILL.md into
<home>/.claude/skills (and <home>/.agents/skills when present), re-point
existing links, refuse to replace a real directory before changing anything,
and write the tech-writing digest block the way ADR 2 describes. The digest
block's own edge cases are covered by skills/tech-writing/scripts/test_install.py
through the install.sh shim; this suite covers what is new.

Every test installs into a throwaway --home, so the real machine is never
touched. Runs on POSIX and native Windows.

Run:  python3 test_install.py   (stdlib only; `python` on native Windows)
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import install  # noqa: E402

INSTALL = os.path.join(HERE, "install.py")
MARK_OPEN = install.MARK_OPEN


def run_install(home, *args):
    return subprocess.run([sys.executable, INSTALL, "--home", home, *args],
                          capture_output=True, text=True)


def target_of(link):
    return os.path.normcase(os.path.realpath(link))


class TestDiscovery(unittest.TestCase):
    def test_finds_every_skill_and_skips_workspaces(self):
        skills = install.discover_skills()
        self.assertIn("deep-code-review", skills)
        self.assertIn("tech-writing", skills)
        self.assertNotIn("deep-code-review-workspace", skills)
        for name in skills:
            self.assertTrue(os.path.isfile(
                os.path.join(install.SKILLS_DIR, name, "SKILL.md")))


class TestRenderBlock(unittest.TestCase):
    def test_empty_content_is_just_the_block(self):
        out = install.render_block("", "body")
        self.assertEqual(out, f"{MARK_OPEN}\nbody\n{install.MARK_CLOSE}\n")

    def test_appends_after_a_blank_line(self):
        out = install.render_block("# notes", "body")
        self.assertTrue(out.startswith("# notes\n\n" + MARK_OPEN))

    def test_replaces_in_place_and_keeps_crlf_tail(self):
        first = install.render_block("head\r\n", "old")
        second = install.render_block(first + "tail\r\n", "new")
        self.assertNotIn("old", second)
        self.assertEqual(second.count(MARK_OPEN), 1)
        self.assertTrue(second.startswith("head\r\n"))
        self.assertTrue(second.endswith("tail\r\n"))


class TestInstall(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.home = self._td.name
        self.tree = os.path.join(self.home, ".claude", "skills")
        self.claude_md = os.path.join(self.home, ".claude", "CLAUDE.md")

    def tearDown(self):
        self._td.cleanup()

    def assertLinked(self, tree, name):
        link = os.path.join(tree, name)
        self.assertTrue(install.is_link(link), f"{link} is not a link")
        self.assertEqual(target_of(link),
                         target_of(os.path.join(install.SKILLS_DIR, name)))

    def test_links_every_skill_and_writes_digest(self):
        proc = run_install(self.home)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for name in install.discover_skills():
            self.assertLinked(self.tree, name)
        with open(self.claude_md, encoding="utf-8") as f:
            self.assertIn(MARK_OPEN, f.read())

    def test_rerun_is_idempotent(self):
        run_install(self.home)
        with open(self.claude_md, encoding="utf-8") as f:
            first = f.read()
        proc = run_install(self.home)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(self.claude_md, encoding="utf-8") as f:
            self.assertEqual(first, f.read())
        self.assertLinked(self.tree, "repo-index")

    def test_links_into_agents_tree_when_present(self):
        agents = os.path.join(self.home, ".agents", "skills")
        os.makedirs(agents)
        proc = run_install(self.home)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for name in install.discover_skills():
            self.assertLinked(agents, name)

    def test_skill_subset_without_tech_writing_skips_digest(self):
        proc = run_install(self.home, "--skill", "repo-index")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(os.listdir(self.tree), ["repo-index"])
        self.assertFalse(os.path.exists(self.claude_md))

    def test_repoints_an_existing_link(self):
        elsewhere = os.path.join(self.home, "elsewhere")
        os.makedirs(elsewhere)
        os.makedirs(self.tree)
        install.make_link(elsewhere, os.path.join(self.tree, "repo-index"))
        proc = run_install(self.home, "--skill", "repo-index")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertLinked(self.tree, "repo-index")
        self.assertTrue(os.path.isdir(elsewhere))

    @unittest.skipUnless(os.name == "nt", "junctions are Windows-only")
    def test_falls_back_to_junction_without_symlink_rights(self):
        os.makedirs(self.tree)
        link = os.path.join(self.tree, "repo-index")
        denied = OSError(1314, "A required privilege is not held by the client")
        with mock.patch("os.symlink", side_effect=denied):
            kind = install.make_link(
                os.path.join(install.SKILLS_DIR, "repo-index"), link)
            self.assertEqual(kind, "junction")
            self.assertTrue(install.is_junction(link))
            with contextlib.redirect_stdout(io.StringIO()):
                install.install(self.home, ["repo-index"], None, dry_run=False)
        self.assertLinked(self.tree, "repo-index")
        self.assertTrue(install.is_junction(link))

    def test_real_directory_aborts_before_any_change(self):
        os.makedirs(os.path.join(self.tree, "tech-writing"))
        proc = run_install(self.home)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("tech-writing", proc.stderr)
        self.assertEqual(os.listdir(self.tree), ["tech-writing"])
        self.assertFalse(os.path.exists(self.claude_md))

    def test_unknown_skill_aborts(self):
        proc = run_install(self.home, "--skill", "no-such-skill")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no-such-skill", proc.stderr)
        self.assertFalse(os.path.exists(self.tree))

    def test_dry_run_changes_nothing(self):
        proc = run_install(self.home, "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("would link", proc.stdout)
        self.assertEqual(os.listdir(self.home), [])


if __name__ == "__main__":
    unittest.main()
