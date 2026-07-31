---
name: repo-index
description: Builds and refreshes an AI-readable knowledge base for a repository — a high-level architecture map, the conventions the codebase actually follows (with counts), and a routing index that lets later agents load only what they need. Use this skill when the user wants to index or document a repo for agents, asks to bootstrap repo knowledge, wants an architecture overview written down, asks "what are this repo's conventions", or wants to make a codebase easier for agents to work in. Trigger on phrases like "index this repo", "document the architecture", "build repo knowledge", "map out this codebase", "what conventions does this repo follow", or when a review skill reports that no knowledge base exists yet.
---

# Repo Index

You're writing down what an agent would otherwise have to rediscover on every task: how
this repo is laid out, what patterns it actually follows, and where the domains are.

## What you're doing and why

Every agent that touches an unfamiliar repo spends its first several tool calls building
the same mental model — and then throws it away. This skill writes that model to disk in a
form later agents can load selectively.

Two constraints shape everything below, and they're the difference between a knowledge
base that helps and one that misleads:

**Write only what you verified.** A confidently wrong architecture summary is worse than
none, because the next agent trusts it instead of looking. Every claim carries an anchor
and a command to re-check it.

**Layer it so recall is cheap.** An agent asking "does this diff touch the payments
domain?" should read thirty lines, not three thousand. The index routes; the detail waits
until someone needs it.

This iteration is deliberately small — one shallow pass, no per-file memos, no incremental
mode. What matters now is that the *contract* is right, because the contract is what's
expensive to change once other skills read it. See `meta/IMPROVEMENTS.md` for where this
is headed.

## Step 1: Decide where knowledge lives

1. `<repo>/.claude/knowledge/` exists → use it.
2. `~/.claude/projects/<repo-slug>/knowledge/` exists → use it.
3. Neither → ask once: in the repo (committed, teammates and CI agents benefit, appears in
   PR diffs) or in personal space (private, nobody else gets it).

Creating the directory *is* the record of the choice, so the question never recurs.

## Step 2: Map the architecture

```bash
git ls-files | awk -F/ '{print $1"/"$2}' | sort | uniq -c | sort -rn | head -30
ls CLAUDE.md AGENTS.md README.md CONTRIBUTING.md docs/ 2>/dev/null
```

Read the README and any existing docs first — the team's own words beat your inference,
and where they exist you should cite them rather than paraphrase.

Then trace **one** representative path end to end: an entry point through to persistence
or output. One traced path teaches more about a codebase's real shape than ten summarized
directories, because it shows you which layers actually exist versus which are just
directory names.

Write `architecture.md`: entry points, the major subsystems and what each owns, the data
stores, the external dependencies, and how a request or job flows through. Anchor each
claim to a file. Keep it under 150 lines — this is a map, not a tour.

## Step 3: Establish conventions

Same method `deep-code-review` uses, applied repo-wide instead of to one diff. Probe for
patterns, **count** them, and apply the establishment test:

> ≥3 supporting occurrences and ≤1 counterexample → `established`.
> Ratio under 3:1 → `mixed`. Fewer than 3 → `absent`.

`../deep-code-review/references/convention-probes.md` has the probe recipes per language.
Write the ledger to `conventions.md` with the counts intact — the counts are the point.
A rule without them is an assertion, and the next agent can't tell a real convention from
one you inferred off two files.

Record `mixed` rules explicitly rather than dropping them. "The repo is inconsistent about
this" is useful knowledge; it tells a later reviewer not to file a finding.

## Step 4: Route the domains

Group the tree into domains — coherent areas of behavior, usually a few directories that
change together. Check `git log` for which paths co-occur in commits if the boundaries
aren't obvious.

Write `INDEX.md`: a table mapping path globs to domain slugs, with claim counts and a
last-verified marker. Under 100 lines, no prose. This is the only file later agents read
unconditionally, so every line in it costs something on every future task.

Seed a `domains/<slug>.md` per domain with the intent paragraph and nothing else. Leave
the invariants, lifecycle maps, and taint sources empty — `business-logic-review` fills
those in as it confirms them, with provenance. Speculatively filling them here would put
unverified intent into a file whose whole value is that its contents were verified.

## Step 5: Show the diff and confirm

```bash
git status --short .claude/knowledge/
git diff --stat .claude/knowledge/
```

Show what you're about to write and wait. If this is going in the repo, it lands in a PR
that a human reviews — better that they see it here first.

## Schema

Every claim follows the same entry schema as the review skills, so a claim written here
decays under the same freshness check:

```markdown
- kind: <invariant|mechanism|lifecycle|convention>
- provenance: code | doc          # this skill may not write `user` or `inferred` claims
- anchor: path/to/file.rs:88 `a short durable quote`
- recorded: <YYYY-MM-DD> @ <sha>
- verify: `<the command that re-checks this>`
- claim: <the statement>
```

Full details in `../business-logic-review/references/memory-protocol.md`. Two things this
skill specifically may not do: write `user`-provenance claims (it hasn't talked to anyone)
or `inferred` claims (which are never written as claims at all — they go to open
questions).

## Edge cases

- **Knowledge base already exists** — refresh rather than overwrite. Re-run the freshness
  check, update what drifted, and leave entries other skills wrote alone.
- **Huge repo** — index the top two or three domains by commit frequency, say which ones
  you skipped, and stop. Partial and honest beats complete and stale.
- **Monorepo** — one knowledge base at the root, domains per package. Don't scatter them.
- **The repo already has good docs** — cite and link them from `architecture.md` rather
  than duplicating. Duplicated docs drift, and then the reader has two answers.
- **No clear domain boundaries** — say so, use one `core` domain, and let review skills
  split it as they learn where the seams actually are.
