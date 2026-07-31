# efficiency

Agent skills for code review and repo knowledge.

## Skills

| Skill | What it does |
|---|---|
| [deep-code-review](skills/deep-code-review/) | Reviews a branch for **API design**, **business-logic correctness**, and **repo conventions** — the judgment calls compilers and linters can't make. Gates each aspect on whether the branch actually touches it, fans out to specialized agents, then arbitrates the findings first-hand. [How it works →](skills/deep-code-review/README.md) |
| [business-logic-review](skills/business-logic-review/) | Deep logic-bug hunting with ten named analytical angles, plus a memory protocol that accumulates domain intent in the reviewed repo so later reviews recall it instead of inventing it. Runs standalone or as a delegate of `deep-code-review`. |
| [repo-index](skills/repo-index/) | Builds the shared knowledge base other skills read: architecture map, established conventions, domain routing. Minimal for now — see its `meta/IMPROVEMENTS.md` for where it's headed. |

All three read and write one [shared knowledge base](skills/deep-code-review/README.md#the-shared-knowledge-base),
stored either in the reviewed repo (committed, shared with teammates) or in your personal
space — the skill asks once and remembers by where it put the files.

## Install

Skills are directories. Symlink or copy the ones you want into `~/.claude/skills/`:

```bash
ln -s "$PWD/skills/deep-code-review"      ~/.claude/skills/
ln -s "$PWD/skills/business-logic-review" ~/.claude/skills/
ln -s "$PWD/skills/repo-index"            ~/.claude/skills/
```

`deep-code-review` delegates to `business-logic-review` by relative path, so install both
to get the full pipeline. It degrades gracefully if you don't.

## Layout

```
skills/<name>/
├── SKILL.md      the skill itself — what the agent loads
├── README.md     human-facing explainer (deep-code-review only)
├── agents/       role files loaded into subagent prompts
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
