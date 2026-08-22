#!/usr/bin/env python3
"""Tests for install.sh, the digest installer (issue #9).

The installer's contract, per ADR 2: symlink the skill into ~/.claude/skills,
write the digest into a marked block in global ~/.claude/CLAUDE.md, mirror the
block into a repo's AGENTS.md under --repo, refresh blocks in place on re-run,
and refuse to install a digest that fails corpus traceability. Every test runs
against a throwaway HOME so the real machine is never touched; the digest can
be overridden via TW_DIGEST_FILE for the failure-path tests.

Run:  python3 test_install.py            (stdlib only, no pytest needed)
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
INSTALL = os.path.join(HERE, "install.sh")
DIGEST = os.path.join(SKILL_DIR, "references", "digest.md")

MARK_OPEN = "<!-- tech-writing-digest v1 -->"
MARK_CLOSE = "<!-- /tech-writing-digest -->"


def run_install(home, *args, digest=None):
    env = dict(os.environ, HOME=home)
    if digest:
        env["TW_DIGEST_FILE"] = digest
    return subprocess.run(["bash", INSTALL, *args],
                          capture_output=True, text=True, env=env)


class TestGlobalInstall(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.home = self._td.name
        self.claude_md = os.path.join(self.home, ".claude", "CLAUDE.md")
        self.link = os.path.join(self.home, ".claude", "skills", "tech-writing")

    def tearDown(self):
        self._td.cleanup()

    def read(self, path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_installs_symlink_and_digest_block(self):
        proc = run_install(self.home)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(os.path.islink(self.link))
        self.assertEqual(os.path.realpath(self.link),
                         os.path.realpath(SKILL_DIR))
        content = self.read(self.claude_md)
        self.assertIn(MARK_OPEN, content)
        self.assertIn(MARK_CLOSE, content)
        digest_body = self.read(DIGEST).strip()
        self.assertIn(digest_body, content)

    def test_rerun_is_idempotent(self):
        run_install(self.home)
        first = self.read(self.claude_md)
        proc = run_install(self.home)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        second = self.read(self.claude_md)
        self.assertEqual(first, second)
        self.assertEqual(second.count(MARK_OPEN), 1)
        self.assertEqual(second.count(MARK_CLOSE), 1)

    def test_rerun_refreshes_stale_block_in_place(self):
        run_install(self.home)
        stale = self.read(self.claude_md).replace(
            self.read(DIGEST).strip(), "stale digest body")
        with open(self.claude_md, "w") as f:
            f.write(stale)
        proc = run_install(self.home)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        content = self.read(self.claude_md)
        self.assertNotIn("stale digest body", content)
        self.assertIn(self.read(DIGEST).strip(), content)

    def test_preserves_surrounding_content(self):
        os.makedirs(os.path.dirname(self.claude_md))
        with open(self.claude_md, "w") as f:
            f.write("# My global notes\n\nkeep me\n")
        run_install(self.home)
        with open(self.claude_md, "a") as f:
            f.write("\ntrailing note\n")
        run_install(self.home)
        content = self.read(self.claude_md)
        self.assertIn("keep me", content)
        self.assertIn("trailing note", content)
        self.assertLess(content.index("keep me"), content.index(MARK_OPEN))
        self.assertEqual(content.count(MARK_OPEN), 1)

    def test_links_into_agents_tree_when_present(self):
        agents = os.path.join(self.home, ".agents", "skills")
        os.makedirs(agents)
        proc = run_install(self.home)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        link = os.path.join(agents, "tech-writing")
        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.path.realpath(link), os.path.realpath(SKILL_DIR))

    def test_skips_agents_tree_when_absent(self):
        proc = run_install(self.home)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse(
            os.path.exists(os.path.join(self.home, ".agents")))

    def test_aborts_when_real_directory_occupies_link_path(self):
        os.makedirs(self.link)
        proc = run_install(self.home)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("tech-writing", proc.stderr)

    def test_aborts_on_untraced_digest(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md",
                                         delete=False) as f:
            f.write("# Digest\n\n- A line citing no rule.\n")
            bad = f.name
        try:
            proc = run_install(self.home, digest=bad)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("traceab", proc.stderr.lower())
            self.assertFalse(os.path.exists(self.claude_md))
        finally:
            os.unlink(bad)


class TestRepoInstall(unittest.TestCase):
    def setUp(self):
        self._home = tempfile.TemporaryDirectory()
        self._repo = tempfile.TemporaryDirectory()
        self.home, self.repo = self._home.name, self._repo.name
        self.agents_md = os.path.join(self.repo, "AGENTS.md")

    def tearDown(self):
        self._home.cleanup()
        self._repo.cleanup()

    def read(self, path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_repo_flag_appends_block_to_existing_agents_md(self):
        with open(self.agents_md, "w") as f:
            f.write("# Issues and PRs\n\nexisting guidance\n")
        proc = run_install(self.home, "--repo", self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        content = self.read(self.agents_md)
        self.assertIn("existing guidance", content)
        self.assertIn(MARK_OPEN, content)
        self.assertEqual(content.count(MARK_OPEN), 1)

    def test_repo_flag_creates_agents_md_when_absent(self):
        proc = run_install(self.home, "--repo", self.repo)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(MARK_OPEN, self.read(self.agents_md))

    def test_repo_rerun_refreshes_in_place(self):
        run_install(self.home, "--repo", self.repo)
        first = self.read(self.agents_md)
        run_install(self.home, "--repo", self.repo)
        self.assertEqual(first, self.read(self.agents_md))

    def test_missing_repo_path_aborts(self):
        proc = run_install(self.home, "--repo",
                           os.path.join(self.repo, "nope"))
        self.assertNotEqual(proc.returncode, 0)


class TestShippedDigest(unittest.TestCase):
    def test_digest_exists_and_traces_to_corpus(self):
        self.assertTrue(os.path.exists(DIGEST))
        proc = subprocess.run(
            ["python3", os.path.join(HERE, "prose_checks.py"), "digest"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('"status": "ok"', proc.stdout)

    def test_digest_stays_capped(self):
        with open(DIGEST, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        self.assertLessEqual(len(lines), 18,
                             "digest grew past its deliberate cap")


if __name__ == "__main__":
    unittest.main()
