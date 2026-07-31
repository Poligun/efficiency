# Memory protocol

Load this whenever you're recalling (Step 2) or writing (Step 7) accumulated knowledge.

**Contents:** [Where it lives](#where-it-lives) · [Layout](#layout) · [Entry schema](#entry-schema)
· [Staleness](#staleness) · [Provenance](#provenance-and-the-hallucination-valve)
· [The graveyard](#the-graveyard) · [Templates](#file-templates)

---

## The one rule

> **Memory stores pointers and questions. It never stores evidence.**

An entry tells you where to look and what to ask. A finding's evidence is always code you
quoted from the current tree this session. Every other rule here follows from this one:
it's what makes staleness survivable, what keeps a hallucinated entry from becoming a
hallucinated finding, and what stops the graveyard from suppressing real bugs.

## Where it lives

1. `<repo>/.claude/knowledge/` exists → use it.
2. `~/.claude/projects/<repo-slug>/knowledge/` exists → use it.
3. Neither → ask the user once. Repo means teammates and CI agents benefit and it shows up
   in PR diffs; personal means it never touches the repo but nobody else gets it.

Creating the directory *is* the record of that choice — there's no config file, so the
question never comes back. If both exist, read both (repo first) and write to the repo: a
teammate's committed knowledge outranks local notes, and local notes stay local.

## Layout

```
.claude/knowledge/
├── INDEX.md              L0 · routing table — the only file read unconditionally
├── architecture.md       L1 · high-level map               (repo-index owns)
├── conventions.md        L1 · established patterns + counts (repo-index / deep-code-review)
├── domains/<slug>.md     L2 · intent, lifecycle maps, invariants, taint, absence, questions
├── files/<path>.md       L3 · per-file memos                (repo-index owns)
├── lessons.md            L1 · cross-cutting lessons
└── review/
    └── findings/<slug>.md     open / fixed / wontfix ledger + graveyard
```

Layers link downward so a reader picks their own depth. "Does this diff touch alerting?"
reads L0 only. Hunting a lifecycle bug reads L0 → L2. Needing one function's history reads
L0 → L2 → L3.

`domains/` and `review/findings/` are split because their load conditions differ — domains
load whenever a matching path changes, findings load only before finalizing a finding — and
because findings churn every review. Keeping that churn out of the stable file is what
keeps the memory diff small enough that a human will actually read it.

Budget: `INDEX.md` under 100 lines, no prose. If a domain file passes ~25 claims, split it;
`INDEX.md` carries claim counts so you can notice.

## Entry schema

Every claim is addressable and single-line-greppable, so `rg '^- provenance: user'` finds
all human-confirmed intent across the tree in one command.

````markdown
### INV-<domain>-004 — <one-line statement of the rule>
- kind: invariant          # invariant | mechanism | lifecycle | taint | absence
- provenance: user         # code | test | doc | user
- status: active           # active | needs-recheck | needs-reconfirmation | retired
- anchor: <path>:<line> `<a short durable quote — a type name, signature, or match arm>`
- recorded: <YYYY-MM-DD> @ <sha> (branch <name>)
- verify: `<the command that re-checks this claim against current code>`
- claim: <the rule, stated so a reviewer can tell whether code violates it>
- user-quote: "<the human's own words, verbatim — required for provenance: user>"
- matters-because: <what verdict or severity this changes>
````

> The `user-quote` field is **only** ever a real human's words, copied verbatim from the
> conversation where they said it. Never write a plausible-sounding quote to fill the
> field. A fabricated quote launders your own inference into the highest-trust provenance
> tier the protocol has, and every later review will treat it as settled intent. If you
> don't have the human's words, the claim isn't `provenance: user` — it's an open question.

ID prefixes: `INV` invariant/intent · `MAP` lifecycle or wiring map · `TAINT` trust
boundary · `ABS` absence claim · `FND` confirmed finding · `REF` refuted claim · `Q` open
question.

**Anchor quotes must be durable.** Quote a type name, a function signature, or a match arm
— never a whole statement body. A quote that includes an expression breaks on every
refactor, and spurious BROKEN entries are the main maintenance cost of this system.

## Staleness

Decay is triggered by **change, not time**. Age doesn't correlate with truth — a two-year
invariant in untouched code is fine, a two-week one in a hot file may already be dead — and
time-based expiry deletes exactly the expensive human-confirmed entries you can't rebuild.

Two commands resolve everything you loaded:

```bash
git log --name-only --pretty=format: <oldest-recorded-sha>..HEAD -- <anchor paths> | sort -u
rg -F --line-number "<anchor quote>" <anchor path>
```

| State | Condition | You may |
|---|---|---|
| FRESH | anchor file unchanged since `recorded` | use as a prior; still quote current code in findings |
| DRIFTED | file changed, quote survives | re-read ±40 lines first; the claim is now a hypothesis |
| BROKEN | quote gone | **not cite it at all**; re-derive or drop |
| UNVERIFIABLE | an `ABS-*` claim | never trust the record; re-run `verify_absence` every time |

**BROKEN is handled asymmetrically by provenance.** A `code` or `doc` claim is silently
rewritten or dropped — it was a cheap observation. A `user` claim is **never auto-deleted**:
flip it to `needs-reconfirmation` and surface it as a question. *"Memory from 2026-07-29,
in your words, says firing must be edge-triggered. The code that anchored that claim is
gone. Is the rule still in force?"* Losing hard-won intent costs more than one question.

**Known limits, stated honestly.** A semantic inversion on an unchanged anchor line —
`>=` becomes `>` without touching the quoted token — is undetectable by this protocol;
DRIFTED forcing a re-read is the only mitigation. Absence claims are the weakest entries,
because a negative grep can miss a synonym; widen the grep by one synonym before trusting
one, and cap at MEDIUM any finding resting solely on an absence claim.

## Provenance and the hallucination valve

| Value | Meaning | Anchor required |
|---|---|---|
| `code` | derived from code read this session | yes, a quote |
| `test` | asserted by an existing test | yes, the test name |
| `doc` | from a doc, comment, or commit message | yes — **and marked, because comments lie** |
| `user` | a human said it | yes, a verbatim quote of the human |
| `inferred` | your guess | **may not be written as a claim** |

Crossed with a class axis: an **observation** (mechanism, shape, wiring — verifiable from
code) may be written freely. An **intent** claim (a requirement, a promise, a rule) reaches
`active` only via `user` or `test`. Doc-sourced intent is allowed but permanently carries
`provenance: doc`, and any finding citing it must say *"the contract claims X"* rather than
*"the requirement is X"* — and caps at MEDIUM.

Inference isn't banned, it's redirected:

````markdown
### Q-alerting-002 — Should one trigger's error abort the whole evaluation cycle?
- proposed answer (inferred, unconfirmed): no — per-trigger errors should be isolated
  and logged, with remaining triggers still evaluated.
- would change: severity of FND-alerting-005 (HIGH if isolation is required, MEDIUM as a
  contract mismatch only)
- asked: never
````

Open questions are free to be wrong — they're labelled as questions, cost one line, and
give the next review a ready-made thing to ask. When the human answers, delete the question
and write an `INV` with `provenance: user` and their verbatim words. **That loop is the
entire knowledge-acquisition mechanism**, and it's why this improves across reviews instead
of merely growing.

## The graveyard

The tension is real: recording "we decided X isn't a bug" stops the fifth review
re-litigating it, but blanket suppression hides a genuinely new instance of the same class.

The resolution: **record the reason as a re-checkable predicate, not the symptom.**

````markdown
### REF-alerting-001 — "Growing the state vector without shrinking it misaligns triggers"
- reason_class: unreachable    # by-design | guarded-elsewhere | unreachable | out-of-scope | wrong-model
- scope: this-site-only        # this-site-only (default) | class-wide (requires a human)
- re_raised: 1
- refuted: 2026-07-29 @ b00b1d4
- reasoning: the collection is immutable after construction today — the update path is
  unimplemented, so nothing can reorder or remove elements on a live instance.
- guard_anchor: <path>:<line> `<quote of the code that makes it safe>`
- void_if: the update path is implemented, OR any code sends a config change with a
  reordered collection.
- note: the latent design flaw is recorded separately as FND-<domain>-006. Refuting the
  present-tense bug does not refute the design finding.
````

Three rules make it safe:

1. **A refutation never silences; it front-loads.** Before dropping a matching finding, ask
   whether *all* the refutation's premises hold at this site. If any differ, raise it with
   the delta explicit: *"Similar to REF-001, but that refutation relied on the update
   operation being unimplemented, and this branch implements it."*
2. **The guard anchor is load-bearing.** If its quote goes BROKEN, the refutation is void
   automatically. It expires exactly when its reason does, not on a timer.
3. **Default scope is this-site-only.** A new occurrence at a different anchor is a new
   finding. Widening to `class-wide` needs a human, because "this whole class is fine here"
   is an intent statement.

`reason_class: wrong-model` needs extra care — the *agent* was wrong, so the entry must
state the correct model in one sentence, or the next agent re-derives the same misreading.

`re_raised: 3` is a hygiene signal: the code is genuinely confusing to readers. At that
point propose an inline code comment in the target repo, which helps humans too and lets
the entry retire.

## Boundary against the repo's real docs

| | Audience | Mood | Carries unconfirmed material? |
|---|---|---|---|
| `CLAUDE.md` | an agent *writing* code | imperative | no |
| `docs/` | humans, published | explanatory, decided | no |
| `.claude/knowledge/` | an agent *reviewing* code | interrogative, evidential | **yes, explicitly labelled** |

Operational test: *if you'd be embarrassed to hand it to a new hire as "the truth," it's
review knowledge.* Review knowledge is allowed — required — to carry confidence markers and
unanswered questions. The others aren't.

**Promotion.** When an `INV` becomes `provenance: user` *and* states a durable product rule
rather than a code shape, offer to promote it to `docs/`, leaving a `promoted_to:` pointer
behind. Don't create a `CLAUDE.md` unprompted; once ~5 user-confirmed invariants accumulate,
offer to draft one.

## File templates

**`INDEX.md`**

````markdown
---
schema: knowledge/v1
repo: <name>
updated: <YYYY-MM-DD>
---
# Knowledge index

Load this file always. Load a domain file when a changed path matches its globs. Load a
findings ledger only before finalizing a finding in that domain.

| path globs | domain | claims | last verified |
|---|---|---|---|
| `src/alert/**`, `proto/**/alert/**` | [alerting](domains/alerting.md) | 9 | 2026-07-29 @ b00b1d4 |

Findings: [alerting](review/findings/alerting.md) — 9 open, 0 fixed, 2 refuted

## Repo-wide notes
- [Things true across the whole repo: what the type system already enforces so review
  budget isn't spent there; where team-owned rationale lives; persistence assumptions.]
````

**`domains/<slug>.md`**

````markdown
---
schema: knowledge/v1
domain: <slug>
paths: ["src/alert/**", "proto/**/alert/**"]
updated: <YYYY-MM-DD>
head: <sha>
---
# <Domain>

## Intent
[One paragraph: what this subsystem is for, in the team's terms.]

## Lifecycle maps      ### MAP-<slug>-NNN entries
## Invariants          ### INV-<slug>-NNN entries
## Taint sources       ### TAINT-<slug>-NNN entries
## Absence claims      ### ABS-<slug>-NNN — re-verify every time, never trust the record
## Open questions      ### Q-<slug>-NNN — inferred, unconfirmed, free to be wrong
````

**`review/findings/<slug>.md`** — `## Open`, `## Fixed`, `## Won't fix`, `## Refuted
(graveyard)`. `FND` entries carry severity, angle, status, anchor, `memory-refs`, trace,
and fix clarity.
