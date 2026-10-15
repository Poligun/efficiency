#!/usr/bin/env python3
"""Tests for apply.py, build_index.py and scrub_check.py.

The contract: the renderer resolves nested and negated conditions and
substitutes only the known placeholders; feature directories apply only
when every feature in their name is selected; an apply into an empty
directory writes every file with no marker left behind and refuses to
overwrite without --force; the convention documents are filtered by
feature; the rule index is current; and the package is free of forbidden
terms.

Run:  python3 test_apply.py   (stdlib only)
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import apply  # noqa: E402
import build_index  # noqa: E402
import scrub_check  # noqa: E402

VALUES = {"name": "demo", "ENV_PREFIX": "DEMO", "main_branch": "main", "date": "2026-01-01"}


class RenderTest(unittest.TestCase):
    def test_keeps_a_block_whose_features_are_selected(self) -> None:
        text = "a\n{{#if rust}}\nb\n{{/if}}\nc\n"
        self.assertEqual(apply.render(text, {"rust"}, VALUES), "a\nb\nc\n")
        self.assertEqual(apply.render(text, set(), VALUES), "a\nc\n")

    def test_requires_every_feature_in_a_compound_condition(self) -> None:
        text = "{{#if proto rust}}\nx\n{{/if}}\n"
        self.assertEqual(apply.render(text, {"proto", "rust"}, VALUES), "x\n")
        self.assertEqual(apply.render(text, {"proto"}, VALUES), "")

    def test_negation_and_nesting(self) -> None:
        text = "{{#if !rust}}\nno-rust\n{{#if typescript}}\nts\n{{/if}}\n{{/if}}\n"
        self.assertEqual(apply.render(text, {"typescript"}, VALUES), "no-rust\nts\n")
        self.assertEqual(apply.render(text, {"rust", "typescript"}, VALUES), "")
        self.assertEqual(apply.render(text, set(), VALUES), "no-rust\n")

    def test_substitutes_known_placeholders_and_leaves_others(self) -> None:
        text = "{{name}} {{ENV_PREFIX}} {{languages}}"
        self.assertEqual(apply.render(text, set(), VALUES), "demo DEMO {{languages}}")

    def test_rejects_unbalanced_blocks_and_unknown_features(self) -> None:
        with self.assertRaises(apply.ApplyError):
            apply.render("{{#if rust}}\n", set(), VALUES)
        with self.assertRaises(apply.ApplyError):
            apply.render("{{/if}}\n", set(), VALUES)
        with self.assertRaises(apply.ApplyError):
            apply.render("{{#if cobol}}\n{{/if}}\n", set(), VALUES)


class PlanTest(unittest.TestCase):
    def test_core_alone_excludes_language_directories(self) -> None:
        dirs = apply.feature_dirs(set())
        self.assertEqual(dirs, ["core"])

    def test_compound_directory_needs_both_features(self) -> None:
        self.assertNotIn("proto+rust", apply.feature_dirs({"proto"}))
        self.assertIn("proto+rust", apply.feature_dirs({"proto", "rust"}))
        self.assertEqual(apply.feature_dirs({"proto", "rust"})[0], "core")

    def test_conventions_follow_features(self) -> None:
        self.assertNotIn("rust.md", apply.conventions(set()))
        self.assertIn("rust.md", apply.conventions({"rust"}))
        self.assertIn("layout.md", apply.conventions(set()))


class ApplyTest(unittest.TestCase):
    def test_full_apply_leaves_no_markers_and_refuses_overwrite(self) -> None:
        selected = set(apply.FEATURES)
        with tempfile.TemporaryDirectory() as target:
            actions = apply.apply(target, selected, VALUES, force=False, dry_run=False)
            self.assertTrue(all(action.startswith("write") for action in actions))
            written = []
            for root, _, names in os.walk(target):
                for name in names:
                    written.append(os.path.join(root, name))
            self.assertGreater(len(written), 80)
            for path in written:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    body = handle.read()
                self.assertNotIn("{{#if", body, path)
                self.assertNotIn("{{/if}}", body, path)
                self.assertNotIn("{{name}}", body, path)
            self.assertTrue(os.access(os.path.join(target, "githooks", "pre-push"), os.X_OK))
            self.assertTrue(os.path.exists(os.path.join(target, "docs", "conventions", "rust.md")))
            with self.assertRaises(apply.ApplyError):
                apply.apply(target, selected, VALUES, force=False, dry_run=False)
            again = apply.apply(target, selected, VALUES, force=True, dry_run=False)
            self.assertTrue(all(action.startswith("replace") for action in again))

    def test_core_only_apply_has_no_language_trees(self) -> None:
        with tempfile.TemporaryDirectory() as target:
            apply.apply(target, set(), VALUES, force=False, dry_run=False)
            self.assertFalse(os.path.exists(os.path.join(target, "rust")))
            self.assertFalse(os.path.exists(os.path.join(target, "typescript")))
            self.assertFalse(os.path.exists(os.path.join(target, "docs", "conventions", "rust.md")))
            with open(os.path.join(target, "BUILD.bazel"), encoding="utf-8") as handle:
                self.assertNotIn("rustfmt", handle.read())
            with open(os.path.join(target, ".bazelrc"), encoding="utf-8") as handle:
                self.assertIn("instrumentation_filter=//python[/:]\n", handle.read())
            with open(os.path.join(target, "uv.lock"), encoding="utf-8") as handle:
                self.assertIn('name = "demo"', handle.read())

    def test_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as target:
            apply.apply(target, set(), VALUES, force=False, dry_run=True)
            self.assertEqual(os.listdir(target), [])


class PreflightTest(unittest.TestCase):
    def test_collision_leaves_the_target_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as target:
            with open(os.path.join(target, "AGENTS.md"), "w", encoding="utf-8") as handle:
                handle.write("mine\n")
            with self.assertRaises(apply.ApplyError) as refused:
                apply.apply(target, set(), VALUES, force=False, dry_run=False)
            self.assertIn("AGENTS.md", str(refused.exception))
            self.assertEqual(os.listdir(target), ["AGENTS.md"])

    def test_main_branch_is_validated(self) -> None:
        with self.assertRaises(SystemExit):
            apply.parse_args(["--target", "t", "--name", "n", "--env-prefix", "N", "--main-branch", 'a"b'])
        args = apply.parse_args(["--target", "t", "--name", "n", "--env-prefix", "N", "--main-branch", "release/1.0"])
        self.assertEqual(args.main_branch, "release/1.0")


class ScrubTest(unittest.TestCase):
    def test_explicit_missing_list_is_an_error(self) -> None:
        with self.assertRaises(scrub_check.MissingTerms):
            scrub_check.terms_file("/nonexistent/terms.txt")
        with self.assertRaises(scrub_check.MissingTerms):
            scrub_check.terms_file(None, "/nonexistent/terms.txt")

    def test_home_paths_of_every_shape_are_caught(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            # Built from parts so this file's own source does not carry a path
            # the check would flag.
            lines = [
                "a " + "/".join(["", "home", "dev42", "x"]),
                "b " + "/".join(["", "Users", "j.doe-x", "y"]),
                "c " + "\\".join(["C:", "Users", "dev", "z"]),
                "d " + "/".join(["", "home", ""]),
            ]
            with open(os.path.join(root, "note.md"), "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines) + "\n")
            hits = scrub_check.scan(root, [])
            self.assertEqual([hit[1] for hit in hits], [1, 2, 3])

    def test_private_terms_are_found_in_any_file_including_the_checker(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "x.md"), "w", encoding="utf-8") as handle:
                handle.write("the Zebraquux project\n")
            self.assertEqual([hit[2] for hit in scrub_check.scan(root, ["zebraquux"])], ["Zebraquux"])
        own = os.path.basename(scrub_check.__file__)
        self.assertTrue(
            any(hit[0] == own for hit in scrub_check.scan(os.path.dirname(scrub_check.__file__), ["absolute home path"])),
        )


class IndexTest(unittest.TestCase):
    def test_slugs_match_a_markdown_renderer(self) -> None:
        self.assertEqual(build_index.slug("BZ-4. Language rules are loaded from the repository's wrappers"),
                         "bz-4-language-rules-are-loaded-from-the-repositorys-wrappers")
        self.assertEqual(build_index.slug("AG-1. `AGENTS.md` is the one rules file"), "ag-1-agentsmd-is-the-one-rules-file")
        self.assertEqual(build_index.slug("GA-1. `bazel build //...` and `bazel test //...` are the gate"),
                         "ga-1-bazel-build--and-bazel-test--are-the-gate")


class PackageTest(unittest.TestCase):
    def test_rule_index_is_current(self) -> None:
        with open(build_index.INDEX, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), build_index.render())

    def test_package_is_scrubbed(self) -> None:
        terms = scrub_check.load_terms(scrub_check.terms_file(None))
        self.assertEqual(scrub_check.scan(scrub_check.PACKAGE, terms), [])


if __name__ == "__main__":
    unittest.main()
