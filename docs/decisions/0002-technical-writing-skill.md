# 2. Technical writing skill: one skill, one merged voice

Status: accepted (amended, see Amendments)
Date: 2026-08-21

Decided in a grilling session (three rounds, two research passes). Work tracked under epic #5;
research provenance in
[skills/tech-writing/meta/research-notes.md](../../skills/tech-writing/meta/research-notes.md).

## Context

Agent-generated prose for human readers — plans, specs, PR descriptions, handoffs, ADRs — drifts
with the model that produced it. Some models emit the short-sentence, line-spamming register that
treats the reader as having no attention span; others anthropomorphize components or coin analogies
that force a professional reader to load extra objects into working memory. Google's Technical
Writing courses One and Two set a strong baseline for clarity and structure, but they were written
for human writers and say almost nothing about tone; they never anticipated agentic output
over-compressing below their notion of a "short sentence."

The repo already has the machinery this skill needs: skills developed under `skills/<name>/` and
symlinked into `~/.claude/skills`, a canonical layout (`SKILL.md`, `references/`, `evals/`,
`meta/`), rule-ID and findings conventions in the review skills, and cross-harness interface
sidecars (`agents/openai.yaml`).

## Decisions

**One skill, two modes, named `tech-writing`.** A single skill at `skills/tech-writing/` routes
to a write mode (guides drafting) and a review mode (reads an existing doc, reports findings).
Both share one rule corpus in `references/`, split by concern: `voice.md` (register and house
tone rules), `clarity.md` (sentence and word level), `structure.md` (document, paragraph, lists,
headings), and `golden-pairs.md` (bad/good fixtures). Rules carry level-family IDs — `D`
document, `P` paragraph, `S` sentence, `W` word — each with a source tag (`[TW1/words]`,
`[devstyle/anthropomorphism]`, `[house]`, `[Williams]`). Split into separate skills only if
description-based triggering proves unreliable.

**Distill, keep provenance.** The working surface is a distilled house ruleset — imperative rules
organized by level (document / paragraph / sentence / word) — not a mirror of the courses. Each
rule carries a source tag mapping it to the Google unit it came from (or marking it house-original)
so drift is auditable. Google course content is CC BY 4.0; the corpus carries the prescribed
"modifications based on" attribution with a link to https://developers.google.com/tech-writing.

**One merged voice, resolved at authoring time.** No runtime precedence logic between Google's
rules and the house tone rules. Every tension (e.g. Google's "short sentences" vs. the house ban
on fragments; Google's em-dash digressions vs. the house staccato ban) is resolved once, during
authoring, into a single rule. Rationale: runtime precedence invites each model to rationalize
either way — exactly the cross-model inconsistency the skill exists to kill.

**Enforcement is layered: ambient digest plus structural wiring.** A short always-on digest
(~15 lines of non-negotiable tone rules) provides ambient enforcement, because a model
mid-plan does not think "I am doing technical writing." The digest is a compiled extract of the
corpus: its master copy lives at `references/digest.md`, every digest line traces to corpus rule
IDs, and it is regenerated when the corpus changes — a digest line with no corresponding corpus
rule is an eval failure. Ambient contexts (global `~/.claude/CLAUDE.md`, per-repo AGENTS.md)
carry only a pointer to the digest plus the digest body, ending with a pointer to the full skill.
The digest must be installable: portable to other repos and other machines, not hand-copied.
Structural wiring covers this repo's own doc-producing skills only; third-party skill trees are
reached ambiently by the digest, and forking them is a per-skill future decision. Open watch
item: measure whether the digest's token cost or its constraint pressure degrades the agent's
thinking; record observations in `meta/`.

**Review mode emits findings, not silent rewrites.** The report opens with a verdict paragraph
(the reader decides in ninety seconds), then findings in two tiers: VIOLATION (cites the rule ID,
quotes the passage, proposes a rewrite) and JUDGMENT (reads awkwardly; flagged with reasoning,
never auto-fixed), plus a coverage line. No severity ladder — prose defects do not rank like
production bugs. `--fix` applies VIOLATION rewrites under a two-band policy: word- and
punctuation-level substitutions apply directly; anything that restructures a sentence, paragraph,
or heading is a rephrase — presented as a choice in interactive sessions (proposed rewrite,
minimal alternative, keep) and reported without applying in non-interactive ones.

**Installation is scripted, idempotent, and skill-local — for now.** `scripts/install.sh` inside
the skill symlinks it into `~/.claude/skills`, writes the digest into a marked block in global
`~/.claude/CLAUDE.md`, and with `--repo <path>` appends the same marked block to a repo's
AGENTS.md for harnesses that read it; re-running refreshes blocks in place. New machine setup is
clone-plus-run. This deviates from the repo's manual-symlink convention deliberately: marked-block
editing of ambient context files is exactly the deterministic work `scripts/` exists for. A
tracked idea issue holds the future refactor to a general mechanism (e.g. a repo-level installer).

**Corpus is harness-portable.** Rules and examples are plain markdown with no Claude-Code-specific
mechanics; harness specifics live only in the thin `SKILL.md` entry and per-harness sidecars
(`agents/openai.yaml`).

**Golden set doubles as fixtures and teaching examples.** Bad/good passage pairs — one or more
per house rule — serve as review-mode eval fixtures and as the in-corpus examples. Sourced
examples (Google exercises, published critiques of LLM style, Williams) preferred over
constructed ones. v1 evals cover review mode only: golden pairs plus near-miss distractors that
must NOT be flagged (appropriate machine actions like "the service reads the config file"; short
but complete sentences; questions in running prose; noun-phrase headings such as "Frequently
asked questions"). A document's citation of a competing tradition (plainlanguage.gov, Microsoft)
is not an exemption: headings phrased as questions are still flagged. Deterministic
checks (anthropomorphic-verb list, AI-vocabulary list, digest-to-corpus traceability) run beside
LLM judging. Write-mode evals are a recorded v2 item.

**Conversational is permitted; condescension is not.** Conversational register is legitimate, and
for some paragraphs or sections ideal, when the section's intent calls for it. The violation is
condescension: phrasing that treats the reader as unable to comprehend longer or more formal
phrasing — talking down, simplifying vocabulary the audience demonstrably has, over-explaining
what an expert already knows. Rules target condescension markers, not conversationality itself.

**Google developer documentation style guide: narrow subset, adopted in v1.** Research showed the
feared register conflict is two sentences of framing on one page; the guide's operational tone
content is restrictions the house voice shares, and its anthropomorphism page states the house
rule nearly verbatim. v1 adopts ~15–20 rules from 9 pages (anthropomorphism, excessive claims,
the tone page's avoidance list, present tense, second person with third-person-for-software,
conditions before instructions, em-dash mechanics, heading rules, jargon mechanics recalibrated
for expert readers, ~a dozen word-list generics). Explicitly excluded to protect the house voice:
the "knowledgeable friend" framing, the wholesale word list, "write around jargon" as a default,
and the global-audience short-sentence emphasis. Exclusions recorded in `meta/open-questions.md`.
Each mined rule is filtered for condescension pressure (see previous decision).

## Consequences

- The skill lives at `skills/tech-writing/` in this repo, tracked as epic #5 with sub-tasks
  #6–#10 (corpus distillation, golden set and evals, two-mode SKILL.md, digest and install,
  sidecars and wiring) under the new `area/writing` label; the install-mechanism refactor is
  idea #11. The PR chain carries `[#5]` linkage.
- The house tone rules are the primary tone layer; Google supplies clarity and structure. Future
  contributors must not "fix" the corpus back toward mainstream friendly-docs register.
- The digest becomes ambient context for every session in scope; its size is a standing cost and
  is deliberately capped.
- Attribution obligations (CC BY 4.0) travel with the corpus if it is ever extracted from this repo.

## Amendments

- 2026-08-22 (issue #7): the eval-distractor list originally named question headings endorsed
  by other traditions as must-not-flag, contradicting the house question-heading ban the corpus
  carries as merge M4 and rule D2 (references/voice.md). The list now names the true near
  misses (prose questions, noun-phrase headings), and the citing-a-competing-tradition case is
  encoded as a temptation fixture the reviewer must still flag.
