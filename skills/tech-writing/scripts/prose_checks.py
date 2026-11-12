#!/usr/bin/env python3
"""Deterministic prose checks for the tech-writing skill (issues #7 and #39).

These checks run beside LLM judging in the review-mode evals:

- anthropomorphic verbs (rule S2): a lexical flagger built from the corpus verb
  table plus the IBM and Hyperlint lists inventoried in meta/research-notes.md.
  A verb whose subject names a person, a role or a team ("the user asks") is
  skipped, and so is a bare verb addressed to the reader ("say so", "ask the
  user", "to decide").
- AI-vocabulary tells (rule W2): the word list from the corpus, with inflections.
- relative time words (rule W8): "today", "currently", "latest" and their kin,
  outside inline code and fenced blocks.
- diagrams (rule P12): a Mermaid block whose preceding line does not end in a
  colon, and a flowchart label that opens with a number, a period and a space.
- digest-to-corpus traceability: every content line of references/digest.md must
  cite at least one corpus rule ID, and every cited ID must exist. The digest
  lands with issue #9, so a missing digest reports "skipped", not "fail".

The word-level checks surface candidates; the corpus marks these rules as
mechanical detection with a judgment verdict, so a hit is a prompt to look, not
a violation by itself.

Usage:
  prose_checks.py scan FILE...        JSON findings; exit 1 if any hit
  prose_checks.py digest [--digest PATH] [--references DIR]
                                      JSON traceability report; exit 1 on fail
"""

from __future__ import annotations

import argparse
import bisect
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

# S2 subject heuristic: nouns that name a person, a role or a team. Words that
# also name software ("client", "agent", "caller", "manager", "they") stay out,
# so their verbs remain candidates.
_HUMAN_SUBJECTS = [
    "i", "you", "we", "he", "she", "someone", "anyone", "everyone", "nobody",
    "people", "person", "persons", "human", "humans", "user", "users",
    "reader", "readers", "team", "teams", "author", "authors", "reviewer",
    "reviewers", "maintainer", "maintainers", "engineer", "engineers",
    "developer", "developers", "operator", "operators", "writer", "writers",
    "owner", "owners", "customer", "customers", "integrator", "integrators",
    "contributor", "contributors", "administrator", "administrators",
    "colleague", "colleagues",
]
# Words allowed between the subject and the verb: modals, auxiliaries,
# negation, and frequency adverbs ("the user can also see").
_SUBJECT_FILLERS = [
    "can", "could", "should", "must", "may", "might", "will", "would", "shall",
    "do", "does", "did", "don't", "doesn't", "didn't", "not", "never", "also",
    "then", "still", "only", "often", "usually", "always", "already", "first",
    "rarely", "has", "have", "had", "to", "need", "needs", "who", "actually",
]
_HUMAN_SUBJECT_RE = re.compile(
    r"\b(?:" + "|".join(_HUMAN_SUBJECTS) + r")"
    r"(?:\s+(?:" + "|".join(re.escape(w) for w in _SUBJECT_FILLERS) + r")){0,3}"
    r"\s+$",
    re.IGNORECASE,
)
# S2 reader-address heuristic: a bare stem opening a sentence, a clause or a
# parenthetical, or following "to", "and", "or" or "then", optionally after a
# negation or an adverb ("Don't ask", "never say", "first decide").
_CLAUSE_OPEN_RE = re.compile(
    r"(?:[.!?;:(][\"'*_)\]]*\s*|\b(?:to|and|or|then)\s+)"
    r"(?:(?:don't|do not|never|always|also|first|only)\s+)?$",
    re.IGNORECASE,
)
_BLOCK_MARKER_RE = re.compile(r"\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+|>\s*)?[*_]*")
_BARE_STEMS = frozenset(ANTHROPOMORPHIC_STEMS)

# Rule W8: relative time words. "now" is left out because S10 prescribes it,
# "new" and "recent" because they are too common to be useful candidates.
_RELATIVE_TIME_RE = re.compile(
    r"\b(today|tonight|tomorrow|yesterday|currently|presently|recently|"
    r"nowadays|soon|latest|upcoming|at present|as of this writing|these days|"
    r"(?:last|this|next) (?:week|month|quarter|year))\b",
    re.IGNORECASE,
)
_FENCE_RE = re.compile(r"^\s*(```|~~~)\s*([\w-]*)")
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
# Rule P12: a flowchart label opening with "1. ": after a node or edge label
# delimiter, optionally inside quotes or a markdown-string backtick.
_LIST_LABEL_RE = re.compile(r"(?:[\[({|]|--)\s*[\"`]*\s*(\d+\.\s)")


def _hit(lineno: int, match: str, line: str, rule: str, **extra) -> dict:
    return {"line": lineno, "match": match, "excerpt": line.strip(),
            "rule": rule, **extra}


def _scan(text: str, pattern: re.Pattern, rule: str) -> list[dict]:
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in pattern.finditer(line):
            hits.append(_hit(lineno, m.group(1), line, rule))
    return hits


def _has_human_subject(text: str, start: int) -> bool:
    before = re.sub(r"\s+", " ", text[max(0, start - 120):start])
    return bool(_HUMAN_SUBJECT_RE.search(before))


def _opens_clause(text: str, start: int) -> bool:
    """True when the word at `start` opens a sentence, clause or parenthetical,
    or follows a connective, across the line wrapping of a Markdown paragraph."""
    line_start = text.rfind("\n", 0, start) + 1
    inline = text[line_start:start]
    if _BLOCK_MARKER_RE.fullmatch(inline):
        if inline.strip() or line_start == 0:
            return True
        prev_end = line_start - 1
        prev_start = text.rfind("\n", 0, prev_end) + 1
        prev = text[prev_start:prev_end]
        if not prev.strip():
            return True
        inline = prev.rstrip() + " "
    return bool(_CLAUSE_OPEN_RE.search(inline))


def anthropomorphic_verb_hits(text: str) -> list[dict]:
    line_starts = [0] + [m.end() for m in re.finditer(r"\n", text)]
    lines = text.split("\n")
    hits = []
    for m in _VERB_RE.finditer(text):
        word = m.group(1)
        if _has_human_subject(text, m.start()):
            continue
        if word.lower() in _BARE_STEMS and _opens_clause(text, m.start()):
            continue
        idx = bisect.bisect_right(line_starts, m.start()) - 1
        hits.append(_hit(idx + 1, word, lines[idx], "S2"))
    return hits


def ai_vocabulary_hits(text: str) -> list[dict]:
    return _scan(text, _VOCAB_RE, "W2")


def relative_time_hits(text: str) -> list[dict]:
    hits = []
    fence = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        fm = _FENCE_RE.match(line)
        if fm:
            if fence is None:
                fence = fm.group(1)
            elif fm.group(1) == fence:
                fence = None
            continue
        if fence is not None:
            continue
        masked = _INLINE_CODE_RE.sub(lambda c: " " * len(c.group(0)), line)
        for m in _RELATIVE_TIME_RE.finditer(masked):
            hits.append(_hit(lineno, m.group(1), line, "W8"))
    return hits


def diagram_hits(text: str) -> list[dict]:
    hits = []
    lines = text.splitlines()
    fence = None
    in_mermaid = False
    for i, line in enumerate(lines):
        fm = _FENCE_RE.match(line)
        if fm and fence is None:
            fence = fm.group(1)
            in_mermaid = fm.group(2).lower() == "mermaid"
            if in_mermaid:
                prev = next((p for p in reversed(lines[:i]) if p.strip()), "")
                if not prev.rstrip().endswith(":"):
                    hits.append(_hit(i + 1, "mermaid", line, "P12",
                                     note="no colon sentence introduces the diagram"))
            continue
        if fm and fm.group(1) == fence:
            fence, in_mermaid = None, False
            continue
        if in_mermaid:
            for m in _LIST_LABEL_RE.finditer(line):
                hits.append(_hit(i + 1, m.group(1).strip(), line, "P12",
                                 note="label opens with a list marker"))
    return hits


def all_hits(text: str) -> list[dict]:
    hits = (anthropomorphic_verb_hits(text) + ai_vocabulary_hits(text)
            + relative_time_hits(text) + diagram_hits(text))
    return sorted(hits, key=lambda h: h["line"])


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

    scan_p = sub.add_parser("scan", help="flag S2, W2, W8 and P12 candidates in files")
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
            for hit in all_hits(text):
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
