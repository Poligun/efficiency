---
name: tech-writing
description: Drafts and reviews human-facing prose (plans, specs, PR descriptions, handoffs, ADRs, READMEs, design docs) in the repo's house voice (complete sentences, subject continuity, no anthropomorphism, no staccato fragments, no question headings, no hype, no assistant-prose tells). Use this skill whenever the user asks to write, draft, or polish a document, wants prose reviewed against the house style, or asks whether a write-up reads well. Trigger on phrases like "write this up", "draft a doc", "draft the PR description", "polish this doc", "review my writing", "review this README", "check this prose", "does this read well", "make this sound less like AI", "house voice", "tighten this up", or any request to produce or evaluate prose for human readers.
---

# Tech writing

You are enforcing one house voice across every model that drafts prose here. The rules live
in the corpus under `references/`; voice.md is the settled ruleset, ratified by ADR 2
(docs/decisions/0002-technical-writing-skill.md in the efficiency repo, not needed at run
time). Do not re-open voice.md's merge decisions, and do not drift the register back
toward mainstream friendly-docs style.

## Pick the mode

Exceptions first: rule questions, running the evals, and installation are ordinary tool
use, not a mode. Otherwise classify by starting point. A request that starts from existing
prose (`review <target>`, "polish this", "tighten this up", a pasted passage, "the doc we
just wrote") is review mode, with `--fix` governing whether findings get applied per the
policy below. A request that starts from intent is write mode. In both modes the audience
is expert readers processing large volumes of text; minimize their cognitive load.

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
a file, and fix what survives adjudication silently; scan hits are candidates here exactly
as in review mode, so a legitimate near miss stays. The two-tier findings protocol below
is for reviewing someone else's prose, not your own draft.

## Review mode

Load voice.md and clarity.md; add structure.md when the target is document-scale (the same
test write mode uses), and consult golden-pairs.md when a candidate sits near a rule
boundary (the same test write mode uses for it). Read the target in full unless its
current content is already in context (a pasted passage, a doc this session just wrote).
Run the deterministic scan first:

```bash
# Replace $SKILL_DIR with the absolute path of the directory this SKILL.md
# lives in before running; the command works from any cwd once you do.
python3 "$SKILL_DIR/scripts/prose_checks.py" scan <targets...>
```

The scan takes file paths only and accepts several at once, so reviewing multiple docs is
one invocation. Write a pasted passage or an in-conversation draft to a scratch file
first; for a passage of only a few sentences, skip the scan and apply the lexical lists
during the read instead. An exit of 1 with JSON on stdout means candidates were found,
which is the normal outcome for any document worth reviewing, not a failed command; any
other outcome (no JSON, a bad path, a usage error) is a real error. The scan emits
rule-tagged candidates, not verdicts: judge each hit against the rule it names before
reporting it, and expect hits that survive judgment, such as a flagged verb whose subject
is a person rather than the software. Then walk the document
top-down by level: document (D rules), paragraph and block (P), sentence (S), word (W).
At the S and W levels, adjudicate the scan's hits rather than re-hunting them, and spend
the manual pass on what the lexical lists cannot catch.

Report in exactly this shape (operationally defined here; the decision is recorded in
ADR 2):

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

Guard the near misses: each rule's section in the corpus (and golden-pairs.md, which owns
the per-rule list) marks what is deliberately permitted, and a near miss takes no finding.

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
