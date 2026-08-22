---
name: tech-writing
description: Drafts and reviews human-facing prose (plans, specs, PR descriptions, handoffs, ADRs, READMEs, design docs) in the repo's house voice: complete sentences, subject continuity, no anthropomorphism, no staccato fragments, no question headings, no hype, no assistant-prose tells. Use this skill whenever the user asks to write, draft, or polish a document, wants prose reviewed against the house style, or asks whether a write-up reads well. Trigger on phrases like "write this up", "draft a doc", "draft the PR description", "polish this doc", "review my writing", "review this README", "check this prose", "does this read well", "make this sound less like AI", "house voice", "tighten this up", or any request to produce or evaluate prose for human readers.
---

# Tech writing

You are enforcing one house voice across every model that drafts prose here. The rules live
in the corpus under `references/`, resolved into a single ruleset at authoring time by ADR 2
(docs/decisions/0002-technical-writing-skill.md at the repo root, reachable through this
skill's symlink target); do not re-litigate the authoring-time merges voice.md binds, and
do not drift the register back toward mainstream friendly-docs style.

## Pick the mode

The argument `review <target>` selects review mode, as does any request to evaluate prose
that already exists (a file path, a pasted passage, or "the doc we just wrote"). `--fix`
is a review-mode flag: `review <target> --fix` reviews and then applies, per the policy
below. Every other request to produce prose is write mode; requests that produce no prose
(a rule question, running the evals, installation) fall through to ordinary tool use. In
both modes the audience is expert readers processing large volumes of text; minimize
their cognitive load.

## Write mode

Load [references/voice.md](references/voice.md) and
[references/clarity.md](references/clarity.md) before drafting. Add
[references/structure.md](references/structure.md) when the work is document-scale:
anything with sections, headings, or more than a few paragraphs. Consult
[references/golden-pairs.md](references/golden-pairs.md) when unsure whether a passage
crosses a line; the near misses there mark what is deliberately permitted.

While drafting, hold every loaded rule as a constraint, not as a post-pass; the register
rules in voice.md are the non-negotiable core, and the clarity and structure rules govern
each sentence and section you produce. Before returning the draft, self-check it against
the rules the corpus marks "Check: mechanical" (fragments, question headings, dash
mechanics, and their kin), run the deterministic scan below on the draft when it exists as
a file, and fix what you find silently: the two-tier findings protocol below is for
reviewing someone else's prose, not your own draft.

## Review mode

Load voice.md and clarity.md; add structure.md when the target is document-scale (the same
test write mode uses), and consult golden-pairs.md when a candidate sits near a boundary,
which is exactly the conditional use its header prescribes. Read the target in full unless its
current content is already in context (a pasted passage, a doc this session just wrote).
Run the deterministic scan first:

```bash
# Replace $SKILL_DIR with the absolute path of the directory this SKILL.md
# lives in before running; the command works from any cwd once you do.
python3 "$SKILL_DIR/scripts/prose_checks.py" scan <target>
```

The scan takes file paths only; write a pasted passage or an in-conversation draft to a
scratch file first. It exits 1 whenever it finds candidates, which is the normal outcome
for any document worth reviewing: a nonzero exit is not a failed command, so read the JSON
it printed. The scan emits rule-tagged candidates, not verdicts: judge each hit against
the rule it names before reporting it, and expect legitimate candidates (a document that
"assumes" prior reading, a "Frequently asked questions" heading). Then walk the document
top-down by level: document (D rules), paragraph and block (P), sentence (S), word (W).
At the S and W
levels, adjudicate the scan's hits rather than re-hunting them, and spend the manual pass
on what the lexical lists cannot catch.

Report in exactly this shape:

1. **Verdict paragraph.** Open with a short paragraph that lets the reader decide in
   ninety seconds: what the document is, whether it holds the house voice, and where the
   damage concentrates.
2. **VIOLATION findings.** One per finding: the rule ID, the quoted passage, and a
   proposed rewrite. A violation cites a rule; if no rule covers it, it is not a
   violation.
3. **JUDGMENT flags.** Passages that read awkwardly without breaking a rule: state the
   reasoning, propose nothing mandatory, never auto-fix.
4. **Coverage line.** Close with one line naming what was checked and anything skipped.

There is no severity ladder; prose defects do not rank like production bugs. Review mode
reports and never edits the target unless `--fix` was requested.

Guard the near misses: golden-pairs.md owns the per-rule list, and they take no finding.
Among them are literal machine actions, short complete sentences, noun-phrase list items
and headings, questions in running prose, and a passive that preserves the topic string.
A document's own citation of a consumer-facing style tradition does not exempt its
question headings (D2, merge M4).

## --fix

`--fix` applies VIOLATION rewrites under a two-band policy:

- **Direct band.** Word- and punctuation-level substitutions (W-rule swaps, dash and
  colon mechanics, bloated-phrase replacements) apply directly.
- **Rephrase band.** Anything that restructures a sentence, paragraph, or heading is a
  rephrase. In an interactive session, present each rephrase as a choice: the proposed
  rewrite, a minimal alternative, or keep. When no channel exists for putting a question
  to the user (a headless run, a subagent), treat the session as non-interactive and
  report rephrases without applying them.

JUDGMENT flags are never applied by `--fix` in either band. When the target is not a file
(a pasted passage), "apply" means returning the rewritten passage after the report; never
search the repo for a file the user did not name.

## Own output

Everything you emit follows the house voice itself: the draft, the review report, and
every proposed rewrite inside a finding. A review that flags fragments in fragments has
already lost the argument.
