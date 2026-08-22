#!/usr/bin/env python3
"""Deterministic prose checks for the tech-writing skill (issue #7).

Three checks run beside LLM judging in the review-mode evals:

- anthropomorphic verbs (rule S2): a lexical flagger built from the corpus verb
  table plus the IBM and Hyperlint lists inventoried in meta/research-notes.md.
- AI-vocabulary tells (rule W2): the word list from the corpus, with inflections.
- digest-to-corpus traceability: every content line of references/digest.md must
  cite at least one corpus rule ID, and every cited ID must exist. The digest
  lands with issue #9, so a missing digest reports "skipped", not "fail".

The word-level checks surface candidates; the corpus marks both rules as
mechanical detection with a judgment verdict, so a hit is a prompt to look, not
a violation by itself.

Usage:
  prose_checks.py scan FILE...        JSON findings; exit 1 if any hit
  prose_checks.py digest [--digest PATH] [--references DIR]
                                      JSON traceability report; exit 1 on fail
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)

# Rule S2 seeds: corpus substitution table, IBM verb blocklist (ask, decide,
# expect, say, see, think, want), Hyperlint Vale rule (remembers, thinks,
# refuses, assumes). Stems cover third-person -s and common inflections.
ANTHROPOMORPHIC_STEMS = [
    "think", "believe", "remember", "complain", "refuse", "want", "expect",
    "ask", "know", "assume", "decide", "say", "see", "speak", "wish",
    "hope", "care", "forget", "realize", "feel",
]

# Rule W2: the assistant-vocabulary tell list, with inflections.
AI_VOCABULARY = [
    "delve", "delves", "delved", "delving",
    "tapestry", "tapestries",
    "testament",
    "underscore", "underscores", "underscored", "underscoring",
    "pivotal",
    "landscape", "landscapes",
    "intricate", "intricately",
    "foster", "fosters", "fostered", "fostering",
    "boast", "boasts", "boasted", "boasting",
    "meticulous", "meticulously",
    "crucial", "crucially",
]

_VERB_INFLECTIONS = {
    # Past forms that double as common nouns (thought, saw, felt) are left out:
    # a candidates list that fires on "school of thought" buries the real hits.
    "say": ["says", "said", "saying"],
    "see": ["sees", "seeing"],
    "speak": ["speaks", "spoke", "speaking"],
    "know": ["knows", "knew", "knowing"],
    "forget": ["forgets", "forgot", "forgetting"],
    "realize": ["realizes", "realized", "realizing"],
    "feel": ["feels", "feeling"],
    "decide": ["decides", "decided", "deciding"],
    "believe": ["believes", "believed", "believing"],
    "assume": ["assumes", "assumed", "assuming"],
    "refuse": ["refuses", "refused", "refusing"],
    "care": ["cares", "cared", "caring"],
    "hope": ["hopes", "hoped", "hoping"],
    "wish": ["wishes", "wished", "wishing"],
    "complain": ["complains", "complained", "complaining"],
    "remember": ["remembers", "remembered", "remembering"],
    "think": ["thinks", "thinking"],
    "want": ["wants", "wanted", "wanting"],
    "expect": ["expects", "expected", "expecting"],
    "ask": ["asks", "asked", "asking"],
}


def _verb_forms():
    forms = []
    for stem in ANTHROPOMORPHIC_STEMS:
        forms.append(stem)
        forms.extend(_VERB_INFLECTIONS.get(stem, [stem + "s"]))
    return forms


_VERB_RE = re.compile(
    r"\b(" + "|".join(sorted(set(_verb_forms()), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_VOCAB_RE = re.compile(
    r"\b(" + "|".join(sorted(set(AI_VOCABULARY), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_RULE_HEADING_RE = re.compile(r"^### ([DPSW]\d+):", re.MULTILINE)
_RULE_ID_RE = re.compile(r"\b([DPSW]\d+)\b")


def _scan(text: str, pattern: re.Pattern, rule: str) -> list[dict]:
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in pattern.finditer(line):
            hits.append({
                "line": lineno,
                "match": m.group(1),
                "excerpt": line.strip(),
                "rule": rule,
            })
    return hits


def anthropomorphic_verb_hits(text: str) -> list[dict]:
    return _scan(text, _VERB_RE, "S2")


def ai_vocabulary_hits(text: str) -> list[dict]:
    return _scan(text, _VOCAB_RE, "W2")


def default_reference_paths() -> list[str]:
    ref_dir = os.path.join(SKILL_DIR, "references")
    names = ("voice.md", "clarity.md", "structure.md")
    return [os.path.join(ref_dir, n) for n in names]


def collect_rule_ids(reference_paths) -> set[str]:
    ids: set[str] = set()
    for path in reference_paths:
        with open(path, encoding="utf-8") as f:
            ids.update(_RULE_HEADING_RE.findall(f.read()))
    return ids


def digest_traceability(digest_path: str, rule_ids: set[str]) -> dict:
    if not os.path.exists(digest_path):
        return {"status": "skipped",
                "reason": f"no digest at {digest_path} (lands with issue #9)"}
    untraced, unknown = [], []
    with open(digest_path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("<!--"):
                continue
            cited = _RULE_ID_RE.findall(line)
            if not cited:
                untraced.append(lineno)
            unknown.extend(i for i in cited if i not in rule_ids)
    status = "ok" if not untraced and not unknown else "fail"
    return {"status": status,
            "untraced_lines": untraced,
            "unknown_ids": sorted(set(unknown))}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    scan_p = sub.add_parser("scan", help="flag S2/W2 candidates in files")
    scan_p.add_argument("files", nargs="+")

    digest_p = sub.add_parser("digest", help="check digest-to-corpus traceability")
    digest_p.add_argument("--digest",
                          default=os.path.join(SKILL_DIR, "references", "digest.md"))
    digest_p.add_argument("--references", default=None,
                          help="directory holding voice/clarity/structure .md")

    args = parser.parse_args(argv)

    if args.command == "scan":
        findings = []
        for path in args.files:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for hit in anthropomorphic_verb_hits(text) + ai_vocabulary_hits(text):
                findings.append({"file": path, **hit})
        print(json.dumps({"findings": findings}, indent=2))
        return 1 if findings else 0

    if args.references:
        refs = [os.path.join(args.references, n)
                for n in ("voice.md", "clarity.md", "structure.md")]
    else:
        refs = default_reference_paths()
    rule_ids = collect_rule_ids(refs)
    result = digest_traceability(args.digest, rule_ids)
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
