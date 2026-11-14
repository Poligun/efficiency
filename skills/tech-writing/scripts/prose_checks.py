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
# also name software ("client", "agent", "caller", "operator", "owner",
# "manager", "they") stay out, so their verbs remain candidates. A listed noun
# clears a verb only as the bare head of the clause's subject: "the reader
# decides" is skipped, "the CSV reader expects" and "authenticates users
# expects" are not.
_HUMAN_SUBJECTS = [
    "i", "you", "we", "he", "she", "someone", "anyone", "everyone", "nobody",
    "people", "person", "persons", "human", "humans", "user", "users",
    "reader", "readers", "team", "teams", "author", "authors", "reviewer",
    "reviewers", "maintainer", "maintainers", "engineer", "engineers",
    "developer", "developers", "writer", "writers", "customer", "customers",
    "integrator", "integrators", "contributor", "contributors",
    "administrator", "administrators", "colleague", "colleagues",
]
# Words allowed between the subject and the verb: modals, auxiliaries,
# negation, and frequency adverbs ("the user can also see").
_SUBJECT_FILLERS = [
    "can", "could", "should", "must", "may", "might", "will", "would", "shall",
    "do", "does", "did", "don't", "doesn't", "didn't", "not", "never", "also",
    "then", "still", "only", "often", "usually", "always", "already", "first",
    "rarely", "has", "have", "had", "to", "need", "needs", "who", "actually",
]
_DETERMINERS = ("the", "a", "an", "each", "every", "any", "some", "this",
                "that", "these", "those", "our", "your", "their", "no")
# Words after which a new clause, and so a new subject, can begin.
_SUBORDINATORS = ("if", "when", "whenever", "unless", "until", "because", "so",
                  "and", "or", "but", "while", "after", "before", "once",
                  "that", "where", "whether", "then", "though", "although")
_CLAUSE_BOUNDARY = (r"(?:^|[.;:!?(]\s*|,\s*|\b(?:"
                    + "|".join(_SUBORDINATORS) + r")\s+)")
_HUMAN_SUBJECT_RE = re.compile(
    _CLAUSE_BOUNDARY
    + r"(?:(?:" + "|".join(_DETERMINERS) + r")\s+)?"
    + r"(?:" + "|".join(_HUMAN_SUBJECTS) + r")"
    + r"(?:\s+(?:" + "|".join(re.escape(w) for w in _SUBJECT_FILLERS) + r")){0,3}"
    + r"\s+$",
    re.IGNORECASE,
)

# S2 reader-address heuristic. A bare stem is an imperative when it opens a
# sentence, a clause after ";" or ":", or a parenthetical, optionally after a
# negation or an adverb ("Don't ask", "then decide").
_IMPERATIVE_PREFIX = r"(?:(?:don't|do not|never|always|also|first|only|then)\s+)?"
_OPENER = r"(?:^|[.!?;:(][\"'*_)\]]*\s*)"
_SENTENCE_OPEN_RE = re.compile(_OPENER + _IMPERATIVE_PREFIX + r"$", re.IGNORECASE)
# ... or follows an introductory clause and its comma ("If unsure, ask").
_INTRODUCERS = ("if", "when", "whenever", "before", "after", "once", "unless",
                "until", "while", "otherwise", "for", "in", "to", "as", "where",
                "during", "with", "without", "since", "because", "on")
_AFTER_INTRO_RE = re.compile(
    _OPENER + r"(?:" + "|".join(_INTRODUCERS) + r")\b[^.!?;:]*,\s*"
    + _IMPERATIVE_PREFIX + r"$",
    re.IGNORECASE,
)
# ... or continues an imperative sentence after "and", "or" or "then" ("Run
# the scan and decide"). The sentence must itself open with an imperative, so
# "Workers poll the queue and expect a lease" stays a candidate.
_COMMON_IMPERATIVES = frozenset((
    "add", "apply", "call", "check", "confirm", "create", "delete", "fix",
    "find", "give", "go", "keep", "leave", "list", "load", "look", "make",
    "mark", "name", "note", "open", "pass", "put", "read", "record", "report",
    "return", "review", "run", "set", "show", "skip", "start", "stop", "take",
    "treat", "try", "turn", "use", "verify", "write",
)) | frozenset(ANTHROPOMORPHIC_STEMS)
_CONNECTIVE_RE = re.compile(r"\b(?:and|or|then)\s+" + _IMPERATIVE_PREFIX + r"$",
                            re.IGNORECASE)
_SENTENCE_START_RE = re.compile(
    _OPENER + _IMPERATIVE_PREFIX + r"([A-Za-z']+)[^.!?;:(]*$", re.IGNORECASE)
# ... or is a wh-infinitive ("what to ask", "whether to decide").
_WH_INFINITIVE_RE = re.compile(
    r"\b(?:what|how|when|where|whether|which|who)\s+to\s+$", re.IGNORECASE)
_BARE_STEMS = frozenset(ANTHROPOMORPHIC_STEMS)

# Markdown block structure, normalized away before the S2 heuristics run: a
# list item, heading, table cell or task box starts a new clause, and a
# blockquote marker on a continuation line is dropped.
_QUOTE_RE = re.compile(r"^\s*(?:>\s?)+")
_ITEM_RE = re.compile(r"^\s*(?:#{1,6}\s+|[-*+]\s+(?:\[[ xX]\]\s+)?|\d+[.)]\s+)")

# Rule W8: relative time words. "now" is left out because S10 prescribes it,
# "new" and "recent" because they are too common to be useful candidates, and
# "as soon as" because it names a condition, not a time.
_RELATIVE_TIME_RE = re.compile(
    r"\b(today|tonight|tomorrow|yesterday|currently|presently|recently|"
    r"nowadays|(?<!\bas )soon(?! as\b)|latest|upcoming|at present|"
    r"as of this writing|these days|(?:last|this|next)\s+(?:week|month|quarter|year))\b",
    re.IGNORECASE,
)
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1).)+?\1")
# Rule P12: a flowchart label opening with a list marker ("1. ", "1) "): after
# a node shape opener, an edge-label pipe, or an edge-text opener ("--", "==",
# "-."), optionally inside quotes or a markdown-string backtick.
_LIST_LABEL_RE = re.compile(
    r"(?:\w(?:\[|\(|\{|>)+[/\\]?|\||(?:^|\s)(?:--|==|-\.)(?=\s))"
    r"\s*[\"`]*\s*(\d+[.)]\s)")


def _hit(lineno: int, match: str, line: str, rule: str, **extra) -> dict:
    return {"line": lineno, "match": match, "excerpt": line.strip(),
            "rule": rule, **extra}


def _scan(text: str, pattern: re.Pattern, rule: str) -> list[dict]:
    hits = []
    for lineno, line in enumerate(text.split("\n"), start=1):
        for m in pattern.finditer(line):
            hits.append(_hit(lineno, m.group(1), line, rule))
    return hits


def _context(text: str, start: int) -> str:
    """The current paragraph up to `start`, flattened to one line. Block
    starts (list items, headings, table cells) become sentence boundaries and
    blockquote markers are dropped, so the S2 heuristics read clause structure
    instead of Markdown layout."""
    para_start = text.rfind("\n\n", 0, start)
    para = text[para_start + 2 if para_start >= 0 else 0:start]
    parts = []
    raw_lines = para.split("\n")
    for i, line in enumerate(raw_lines):
        line = _QUOTE_RE.sub("", line.rstrip("\r"))
        if not line.strip():
            # The partial line before the verb is empty when the verb opens a
            # wrapped line; only a whitespace-only line inside is a break.
            if i < len(raw_lines) - 1:
                parts.append(".")
            continue
        m = _ITEM_RE.match(line)
        if m:
            # A heading is a whole block: the line after it opens a new clause.
            tail = " ." if line.lstrip().startswith("#") else ""
            line = ". " + line[m.end():] + tail
        elif i == 0 or line.lstrip().startswith("|"):
            line = ". " + line.lstrip()
        parts.append(line.replace("|", " . "))
    flat = re.sub(r"\s+", " ", " ".join(parts)).replace("’", "'")
    flat = re.sub(r"[*_\[\]]", "", flat)
    # The verb's own preceding whitespace (a space or a line break) stays.
    return flat.rstrip() + " " if para[-1:].isspace() else flat


def _is_reader_addressed(context: str) -> bool:
    if (_SENTENCE_OPEN_RE.search(context) or _AFTER_INTRO_RE.search(context)
            or _WH_INFINITIVE_RE.search(context)):
        return True
    if _CONNECTIVE_RE.search(context):
        m = _SENTENCE_START_RE.search(context)
        return bool(m) and m.group(1).lower() in _COMMON_IMPERATIVES
    return False


def anthropomorphic_verb_hits(text: str) -> list[dict]:
    line_starts = [0] + [m.end() for m in re.finditer(r"\n", text)]
    lines = text.split("\n")
    hits = []
    for m in _VERB_RE.finditer(text):
        word = m.group(1)
        context = _context(text, m.start())
        if _HUMAN_SUBJECT_RE.search(context):
            continue
        if word.lower() in _BARE_STEMS and _is_reader_addressed(context):
            continue
        idx = bisect.bisect_right(line_starts, m.start()) - 1
        hits.append(_hit(idx + 1, word, lines[idx], "S2"))
    return hits


def ai_vocabulary_hits(text: str) -> list[dict]:
    return _scan(text, _VOCAB_RE, "W2")


def _fenced_lines(lines: list[str]):
    """Yield (index, line, fence) for every line. fence is None outside code,
    "" inside a fence, and the info string (or "-" when empty) on an opening
    fence line. A fence closes only on a bare run of the same character at
    least as long as the opener, as in CommonMark."""
    opener = None
    for i, line in enumerate(lines):
        m = _FENCE_RE.match(line.rstrip("\r"))
        if opener is None:
            if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
                opener = m.group(1)
                yield i, line, m.group(2).strip() or "-"
            else:
                yield i, line, None
        else:
            if (m and m.group(1)[0] == opener[0]
                    and len(m.group(1)) >= len(opener) and not m.group(2).strip()):
                opener = None
            yield i, line, ""


def relative_time_hits(text: str) -> list[dict]:
    hits = []
    for i, line, fence in _fenced_lines(text.split("\n")):
        if fence is not None:
            continue
        masked = _INLINE_CODE_RE.sub(lambda c: " " * len(c.group(0)), line)
        for m in _RELATIVE_TIME_RE.finditer(masked):
            hits.append(_hit(i + 1, line[m.start(1):m.end(1)], line, "W8"))
    return hits


def diagram_hits(text: str) -> list[dict]:
    hits = []
    lines = text.split("\n")
    in_mermaid = False
    for i, line, fence in _fenced_lines(lines):
        if fence is None:
            in_mermaid = False
        elif fence:
            in_mermaid = fence.lower().strip("{}") == "mermaid"
            if in_mermaid:
                prev = next((p for p in reversed(lines[:i]) if p.strip()), "")
                if not prev.rstrip().rstrip("*_").endswith(":"):
                    hits.append(_hit(i + 1, "mermaid", line, "P12",
                                     note="no colon sentence introduces the diagram"))
        elif in_mermaid:
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
