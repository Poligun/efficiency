# efficiency

Agent skills for code review, repo knowledge, project management, and technical writing.

## Skills

| Skill | What it does |
|---|---|
| [deep-code-review](skills/deep-code-review/) | Reviews a branch for **API design**, **business-logic correctness**, and **repo conventions** — the judgment calls compilers and linters can't make. Gates each aspect on whether the branch actually touches it, fans out to specialized agents, then arbitrates the findings first-hand. [How it works →](skills/deep-code-review/README.md) |
| [business-logic-review](skills/business-logic-review/) | Deep logic-bug hunting with ten named analytical angles, plus a memory protocol that accumulates domain intent in the reviewed repo so later reviews recall it instead of inventing it. Runs standalone or as a delegate of `deep-code-review`. |
| [repo-index](skills/repo-index/) | Builds the shared knowledge base other skills read: architecture map, established conventions, domain routing. Minimal for now — see its `meta/IMPROVEMENTS.md` for where it's headed. |
| [pm-setup](skills/pm-setup/) | Bootstraps a repository with the issue-management system: five label families, hybrid label/native state machines, resolution-on-close, PR linkage, and the tracker seam file (`.claude/tracker.md`) that other skills read instead of hardcoding tracker commands. Run once per repo; re-running refreshes the deployed files. |
| [project-manager](skills/project-manager/) | The day-N half of the pm pair: audits the tracker's invariants, proposes label repairs for confirmation, and reports the work frontier (what's urgent, ready, in flight, and queued for spec). |
| [tech-writing](skills/tech-writing/) | Drafts and reviews human-facing prose in one house voice, regardless of which model produces it. The most involved skill here; the next section explains its setup. |

The three review-and-knowledge skills read and write one [shared knowledge base](skills/deep-code-review/README.md#the-shared-knowledge-base),
stored either in the reviewed repo (committed, shared with teammates) or in your personal
space — the skill asks once and remembers by where it put the files.

## The house voice

`tech-writing` exists because agent prose drifts with the model that produced it: one
model emits staccato fragment chains, another anthropomorphizes components, a third coins
hype terms and forced analogies. The skill pins every model to one voice, decided once at
authoring time and enforced everywhere.
[ADR 2](docs/decisions/0002-technical-writing-skill.md) records the design.

The rule corpus lives in [references/](skills/tech-writing/references/), split by concern:
`voice.md` carries register and tone (no anthropomorphism, no fragments, no question
headings, no hype, no assistant-prose tells, subject continuity), `clarity.md` the
sentence and word level, `structure.md` documents, paragraphs, lists, and headings, and
`golden-pairs.md` the bad/good pairs that double as eval fixtures and teaching examples.
Every rule carries a level-family ID (`D` document, `P` paragraph, `S` sentence, `W`
word) and a source tag: the rules distill Google's Technical Writing courses, a narrow
subset of the Google developer documentation style guide, Williams' cohesion principles,
and house-original rules into a single merged ruleset. The seven merge decisions (M1-M7
in `voice.md`) are binding; no runtime precedence logic exists to re-litigate them.

Enforcement is layered, so the voice holds even when the skill never triggers:

- **Ambient digest.** [references/digest.md](skills/tech-writing/references/digest.md)
  compresses the non-negotiables to about fifteen lines, each tracing to corpus rule IDs.
  The installer writes it into a marked block in global `~/.claude/CLAUDE.md` (and into a
  repo's AGENTS.md with `--repo`), so every session holds the core rules.
- **Two modes.** Write mode guides drafting against the corpus. Review mode
  (`review <target>`) reports findings in two tiers, VIOLATION (rule ID, quoted passage,
  proposed rewrite) and JUDGMENT (flagged with reasoning, never auto-fixed), with a
  verdict paragraph first, a coverage line last, and no severity ladder. `--fix` applies
  word-level rewrites directly and offers anything that restructures a sentence as a
  choice.
- **Deterministic checks.** `scripts/prose_checks.py` flags anthropomorphic-verb and
  AI-vocabulary candidates and verifies that every digest line traces to a corpus rule;
  the eval suite in `evals/` runs it beside LLM judging.
- **Structural wiring.** The doc-producing skills in this repo (the two reviews, the pm
  pair, repo-index) each carry a one-sentence wire holding their reports to the house
  voice.

The skill installs through its own idempotent script rather than a manual symlink,
because it also places the digest and links the cross-harness tree:

```bash
skills/tech-writing/scripts/install.sh            # symlink + global digest
skills/tech-writing/scripts/install.sh --repo .   # also this repo's AGENTS.md
```

Re-running refreshes the digest block in place; setting up a new machine is clone plus
run.

## Install

Skills are directories. Symlink or copy the ones you want into `~/.claude/skills/`:

```bash
ln -s "$PWD/skills/deep-code-review"      ~/.claude/skills/
ln -s "$PWD/skills/business-logic-review" ~/.claude/skills/
ln -s "$PWD/skills/repo-index"            ~/.claude/skills/
ln -s "$PWD/skills/pm-setup"              ~/.claude/skills/
ln -s "$PWD/skills/project-manager"       ~/.claude/skills/
```

`deep-code-review` delegates to `business-logic-review` by relative path, so install both
to get the full pipeline. It degrades gracefully if you don't. `tech-writing` is the
exception: install it with its script (previous section), which a manual symlink would
only half-install by skipping the ambient digest.

## Layout

```
skills/<name>/
├── SKILL.md      the skill itself — what the agent loads
├── README.md     human-facing explainer (deep-code-review only)
├── agents/       role files loaded into subagent prompts, and cross-harness
│                 interface sidecars (openai.yaml)
├── references/   loaded on demand, annotated with when to load them
├── scripts/      deterministic work that shouldn't cost model tokens
├── evals/        test prompts + assertions
└── meta/         the skill's own source: design rationale, decision log,
                  improvement checklist, eval ground truth, iteration history
```

`meta/` is the part worth knowing about. `SKILL.md` is a compiled artifact — terse,
imperative, written for an agent mid-task. `meta/` holds the reasoning behind it,
including what was rejected and why, so the next iteration improves the skill instead of
re-deriving it.
