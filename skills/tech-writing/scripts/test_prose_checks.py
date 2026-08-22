#!/usr/bin/env python3
"""Tests for prose_checks.py, the deterministic layer of the review-mode evals.

The three checks come from issue #7: the anthropomorphic-verb list (rule S2),
the AI-vocabulary tell list (rule W2), and digest-to-corpus traceability (every
digest line cites at least one corpus rule ID, and every cited ID exists). The
word-level checks are flaggers, not verdicts: they surface candidates for LLM
judgment, so the tests assert hits and non-hits on the golden near-misses, not
semantic correctness.

Run:  python3 test_prose_checks.py            (stdlib only, no pytest needed)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "prose_checks.py")
sys.path.insert(0, HERE)

import prose_checks as pc  # noqa: E402


class TestAnthropomorphicVerbs(unittest.TestCase):
    def hits(self, text):
        return pc.anthropomorphic_verb_hits(text)

    def test_flags_sourced_golden_verbs(self):
        # Seeds from the GP1 inventory: Google, IBM, and Hyperlint verb lists.
        text = (
            "The parser thinks the input is UTF-8.\n"
            "The service remembers the last offset.\n"
            "The compiler complains about the cast.\n"
            "The server refuses stale tokens.\n"
            "The API expects a JSON body.\n"
            "The client assumes port 5432.\n"
            "The proxy speaks PostgreSQL.\n"
        )
        verbs = {h["match"] for h in self.hits(text)}
        for verb in ("thinks", "remembers", "complains", "refuses",
                     "expects", "assumes", "speaks"):
            self.assertIn(verb, verbs)

    def test_reports_line_numbers(self):
        text = "First line is fine.\nThe daemon wants a restart.\n"
        hits = self.hits(text)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["line"], 2)
        self.assertEqual(hits[0]["rule"], "S2")

    def test_near_miss_machine_actions_not_flagged(self):
        # The GP1 counter-fixture: literal machine actions must produce no hits.
        text = (
            "The service reads the config file.\n"
            "The program searches the tree.\n"
            "The client sends a request.\n"
            "A process listens on port 8080.\n"
        )
        self.assertEqual(self.hits(text), [])

    def test_word_boundaries(self):
        # 'rethinks' and 'seesaw' must not match 'thinks'/'sees'.
        self.assertEqual(self.hits("The tool rethinks nothing. A seesaw.\n"), [])

    def test_case_insensitive(self):
        self.assertEqual(len(self.hits("It Thinks in graphs.\n")), 1)

    def test_noun_colliding_past_forms_excluded(self):
        # "thought", "saw", "felt" double as common nouns and are left out.
        text = ("A school of thought holds otherwise.\n"
                "Cut it with a saw. The felt lining tore.\n")
        self.assertEqual(self.hits(text), [])


class TestAiVocabulary(unittest.TestCase):
    def hits(self, text):
        return pc.ai_vocabulary_hits(text)

    def test_flags_w2_tell_list(self):
        text = (
            "Let's delve into the intricate tapestry of caching.\n"
            "This is a testament to the pivotal role of the landscape.\n"
            "It boasts meticulously crafted, crucial features, fostering trust.\n"
        )
        words = {h["match"].lower() for h in self.hits(text)}
        for word in ("delve", "intricate", "tapestry", "testament", "pivotal",
                     "landscape", "boasts", "meticulously", "crucial",
                     "fostering"):
            self.assertIn(word, words)

    def test_inflections_covered(self):
        words = {h["match"].lower()
                 for h in self.hits("She delved in. It underscores the point.\n")}
        self.assertIn("delved", words)
        self.assertIn("underscores", words)

    def test_clean_technical_prose_not_flagged(self):
        text = (
            "The scheduler assigns each job a priority.\n"
            "The jobs are held in a red-black tree, ordered by that priority.\n"
        )
        self.assertEqual(self.hits(text), [])

    def test_rule_tag_is_w2(self):
        hits = self.hits("A tapestry.\n")
        self.assertEqual(hits[0]["rule"], "W2")


class TestRuleIdCollection(unittest.TestCase):
    def test_collects_ids_from_reference_headings(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "voice.md")
            with open(path, "w") as f:
                f.write("### D2: Do not phrase headings as questions\n"
                        "body\n"
                        "### S2: Attribute behavior to the mechanism\n"
                        "## Not a rule heading\n")
            ids = pc.collect_rule_ids([path])
        self.assertEqual(ids, {"D2", "S2"})

    def test_real_corpus_has_41_rules(self):
        refs = pc.default_reference_paths()
        ids = pc.collect_rule_ids(refs)
        self.assertEqual(len(ids), 41)
        self.assertIn("D1", ids)
        self.assertIn("W7", ids)


class TestDigestTraceability(unittest.TestCase):
    def write(self, td, name, content):
        path = os.path.join(td, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_missing_digest_is_skipped(self):
        result = pc.digest_traceability("/nonexistent/digest.md", set())
        self.assertEqual(result["status"], "skipped")

    def test_every_line_cited_and_ids_exist(self):
        with tempfile.TemporaryDirectory() as td:
            digest = self.write(td, "digest.md",
                                "# Digest\n"
                                "\n"
                                "- Write complete sentences. (S1)\n"
                                "- Never anthropomorphize software. (S2, W1)\n")
            result = pc.digest_traceability(digest, {"S1", "S2", "W1"})
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["untraced_lines"], [])
        self.assertEqual(result["unknown_ids"], [])

    def test_untraced_line_fails(self):
        with tempfile.TemporaryDirectory() as td:
            digest = self.write(td, "digest.md",
                                "- Be concise.\n"
                                "- Write complete sentences. (S1)\n")
            result = pc.digest_traceability(digest, {"S1"})
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["untraced_lines"], [1])

    def test_unknown_id_fails(self):
        with tempfile.TemporaryDirectory() as td:
            digest = self.write(td, "digest.md",
                                "- Write complete sentences. (S99)\n")
            result = pc.digest_traceability(digest, {"S1"})
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["unknown_ids"], ["S99"])

    def test_headings_and_blanks_exempt(self):
        with tempfile.TemporaryDirectory() as td:
            digest = self.write(td, "digest.md",
                                "# House voice digest\n\n<!-- marker -->\n"
                                "- Cite rules. (D1)\n")
            result = pc.digest_traceability(digest, {"D1"})
        self.assertEqual(result["status"], "ok")


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        proc = subprocess.run([sys.executable, SCRIPT, *args],
                              capture_output=True, text=True)
        return proc

    def test_scan_reports_findings_as_json_and_exit_1(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "doc.md")
            with open(path, "w") as f:
                f.write("The cache remembers your tapestry.\n")
            proc = self.run_cli("scan", path)
        self.assertEqual(proc.returncode, 1)
        findings = json.loads(proc.stdout)["findings"]
        rules = {f["rule"] for f in findings}
        self.assertEqual(rules, {"S2", "W2"})

    def test_scan_clean_file_exits_0(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "doc.md")
            with open(path, "w") as f:
                f.write("The service reads the config file.\n")
            proc = self.run_cli("scan", path)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["findings"], [])

    def test_digest_subcommand_skips_when_absent(self):
        proc = self.run_cli("digest", "--digest", "/nonexistent/digest.md")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
