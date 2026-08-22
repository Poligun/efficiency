# Glossary — tech-writing

Vocabulary defined by [ADR 2](../../../docs/decisions/0002-technical-writing-skill.md). Terms
promote to `CONTEXT.md` only when a second skill uses them.

**house voice** — The merged register this skill enforces: complete sentences with subject
continuity, mostly objective, no anthropomorphism, no staccato fragments, no rhetorical-question
headers, no coined hype terms; written for expert readers who process large volumes of text.
Conversational register is permitted — and for some paragraphs or sections ideal — when the
section's intent calls for it; what is banned is condescension: register implying the reader
cannot comprehend longer or more formal phrasing. Produced by resolving Google-course rules and
house tone rules into one ruleset at authoring time.

**condescension test** — The filter applied to conversational passages: does the phrasing talk
down, simplify vocabulary the audience demonstrably has, or over-explain what an expert reader
already knows? Conversationality itself is not a violation; failing this test is.

**rule corpus** — The distilled ruleset in `references/`: imperative rules organized by level
(document / paragraph / sentence / word), each with a source tag and, where teaching value is
high, a golden pair.

**write mode** — The skill path that guides an agent while drafting a document.

**review mode** — The skill path that reads an existing document and emits findings; `--fix`
applies proposed rewrites.

**digest** — The ~15-line always-on extract of non-negotiable tone rules, placed in ambient
context (global CLAUDE.md, per-repo AGENTS.md) so enforcement does not depend on the skill
triggering. A compiled artifact: master copy at `references/digest.md`, every line traceable to
corpus rule IDs, regenerated when the corpus changes. Installable to other repos and machines.

**rephrase** — A `--fix` rewrite that restructures a sentence, paragraph, or heading rather than
substituting flagged words or punctuation. Rephrases are offered as choices in interactive
sessions and reported without applying in non-interactive ones.

**golden pair** — A bad passage and its known-good rewrite, illustrating one rule. The golden
set doubles as review-mode eval fixtures and in-corpus teaching examples.

**mechanical check** — A review check decidable near-deterministically (passive voice,
"there is/are", stacked headings, bloated-phrase blocklist, acronym protocol).

**judgment check** — A review check requiring editorial judgment (audience fit, paragraph unity,
whether a subordinate clause aids clarity). Findings from these are flagged, not enforced.

**source map** — The per-rule provenance tag linking a distilled rule back to its Google course
unit, dev-docs style-guide page, or marking it house-original.

**structural wiring** — Enforcement by having doc-producing skills (plans, specs, PR
descriptions, handoffs) invoke this skill explicitly, rather than relying on trigger phrases.
