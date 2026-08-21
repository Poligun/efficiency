---
name: pm-setup
description: Bootstrap a repository with the issue-management setup (label taxonomy, state machines, PR linkage, tracker seam file) so lifecycle skills and /project-manager can operate it. Run once per repo; re-running refreshes the deployed files.
disable-model-invocation: true
---

# pm-setup

Deploy the issue-management system — five label families, hybrid label/native state
machines, resolution-on-close, sub-issue tasks, PR linkage — into the current
repository, and generate the **tracker seam file** (`.claude/tracker.md`) that every
consuming skill reads instead of hardcoding tracker commands.

The taxonomy originates in scarlet's ADR 0015. The templates in
[templates/](templates/) are the canonical master; each deployed repo owns its
generated copies outright — there is **no sync obligation** back to this skill or
between repos. Drift is deliberate: each repo's adoption ADR records *its* answers.

## What is imposed vs. asked

**Imposed (the universal core — never interviewed):**

- `type/` — epic, task, bug, idea. Exactly one per issue, mirrored in the title
  prefix (`[Epic]`, `[Task]`, `[Bug]`, `[Idea]`).
- Priority — bare `P0`–`P3`, default `P2`; exactly one per open non-idea.
- `status/` — backlog, needs-spec, needs-tickets, in-flight, ready. Exactly one per
  open issue. Status names the **next deliberate action**; execution states (in
  progress, in review, blocked, done) stay native to the tracker and are never labels.
- `resolution/` — done, wont-do, obsolete, duplicate, cannot-reproduce. Exactly one
  per closed issue; the native close reason is derived from it.
- The Material palette, the invariants, the state machines, the PR linkage
  conventions, and the "issues are thin pointers" principle.

**Asked (the tiered interview — at most three questions):**

1. **Areas** — the `area/*` labels. Propose a set derived from the repo's actual
   structure (top-level modules, existing docs); the user edits or approves. Zero or
   more per issue; the set grows when a new module cluster appears.
2. **Doc layout** — where do decisions, research, and plans live? Default to the
   scarlet layout (`docs/decisions/`, `docs/research/`, `plans/`, `CONTEXT.md` for
   vocabulary). Create only the directories the answer names; the vocabulary doc's
   pointers use whatever paths the user chose. If the repo already has a doc
   convention, adopt it rather than imposing the default.
3. **PR template** — never imposed. If discovery found one (any location GitHub
   reads), propose a consolidation: keep the repo's own sections and add only the
   linkage header (the `Closes #N` first line and its comment) at the top; show
   the merged result and deploy it only on approval — declining leaves the file
   untouched. If the repo has none, ask whether to create one from the template.
   Either way the vocabulary doc's PR-conventions section adapts: its
   `{{pr_template_bullet}}` links whatever template ends up existing, or states
   that no template exists and the convention lines are the whole shape (the seam
   file's `{{pr_template_note}}` says the same). The linkage conventions
   themselves are part of the imposed core — only the template *file* is
   optional.

Any deviation the user requests beyond these two questions is fine — record it in the
generated adoption ADR under its own heading. The ADR is the record of what this repo
answered differently.

## Procedure

### 1. Detect the backend

Look for evidence of the tracker in this order: a GitHub remote (`git remote -v` +
`gh repo view`), a Jira/Linear MCP server or CLI in the environment, an explicit user
statement. **Round 1 implements GitHub only.** For any other backend, stop and tell
the user: the seam design supports it (see
[templates/tracker.github.md](templates/tracker.github.md) for the shape a backend
file must fill), but the adapter does not exist yet. Do not improvise one.

### 2. Discover existing state

Collect before asking anything:

- `gh label list` — existing labels, stock or custom.
- `gh issue list --state all --limit 200` — existing issues needing migration.
- A PR template in any location GitHub reads: `.github/PULL_REQUEST_TEMPLATE.md`,
  `PULL_REQUEST_TEMPLATE.md` at the root, `docs/PULL_REQUEST_TEMPLATE.md` (each
  case-insensitively), or the multi-template `.github/PULL_REQUEST_TEMPLATE/`
  directory.
- Presence of `AGENTS.md` (or `CLAUDE.md`), existing `docs/` layout, existing ADR
  numbering (next free number).
- Installed lifecycle skills: look for `to-spec` and `to-tickets` in
  `~/.claude/skills/`, `.agents/skills/`, `~/.agents/skills/`, `.claude/skills/`.

### 3. Run the interview

The questions above, in one round, with proposals pre-filled from discovery.

### 4. Deploy

Generate each file from its template, substituting the interview answers. Templates
use `{{placeholder}}` markers; fill them, never leave one behind. Placeholders
ending in `_href` take paths **relative to the generated file's own location**
(so links resolve when rendered); their display twins take the repo-root path —
e.g. `docs/issues.md` displays as-is but links as `../docs/issues.md` from
`.claude/tracker.md` and `../issues.md` from `docs/decisions/`.

| Deploy | From | Notes |
| --- | --- | --- |
| Labels | palette table in [templates/issues.md](templates/issues.md) | `gh label create` for all families; skip ones that already exist with the right color |
| `docs/issues.md` | [templates/issues.md](templates/issues.md) | the vocabulary doc, path per doc-layout answer |
| Adoption ADR | [templates/adr-issue-management.md](templates/adr-issue-management.md) | next free ADR number; records interview answers + deviations |
| PR template | [templates/PULL_REQUEST_TEMPLATE.md](templates/PULL_REQUEST_TEMPLATE.md) | per the PR-template answer: consolidate with the existing one (its sections kept, linkage header added), create anew, or skip entirely |
| `AGENTS.md` section | [templates/agents-md-section.md](templates/agents-md-section.md) | append to existing AGENTS.md (or CLAUDE.md if that is the repo's convention); create AGENTS.md if neither exists |
| `.claude/tracker.md` | [templates/tracker.github.md](templates/tracker.github.md) | the seam file — see below |

The seam file is **generated by discovery, not stamped**: fill in the repo identity,
the area set, the doc paths, and any repo-specific constraints found in step 2. On
backends with per-project workflows (Jira), this is where discovered transition
requirements and pass-through fields land — the GitHub template shows the sections.

### 5. Clean up superseded labels

Delete stock labels that the taxonomy supersedes, after showing the user the list:
`bug`, `enhancement` (→ `type/*`), `documentation` (→ `area/docs` or the repo's
equivalent), `wontfix`, `duplicate`, `invalid` (→ resolutions), `good first issue`,
`help wanted`, `question` (meaningless where agents file through the CLI). A custom
pre-existing label is never deleted without asking; if it maps onto the taxonomy,
propose the mapping in the migration pass.

### 6. Migrate existing issues (guided, never automatic)

If discovery found issues: propose, per issue, a `type/*`, a `status/*`, a priority
(open, non-idea), a `resolution/*` (closed), and a title prefix. Present the whole
table, let the user edit, then batch-apply with `gh`. Type and status are judgment
calls — never apply without approval. Zero issues → skip.

### 7. Check lifecycle skills

The system expects spec/ticket skills (the known-good pair is `to-spec` +
`to-tickets`, installable via `npx skills install` or the user's preferred channel).
They are **not** part of this package and are never vendored or modified: they learn
this repo's vocabulary through the "For lifecycle skills" section of
`.claude/tracker.md` and the AGENTS.md pointer, which override their generic defaults
(e.g. the `ready-for-agent` label). If they are not installed, tell the user where
the gap is and move on — nothing else blocks on them.

### 8. Verify

- Every label family present with the palette colors; superseded labels gone.
- Every generated file free of `{{` markers.
- Every relative link in every generated file resolves to an existing file,
  checked **from that file's own directory** — marker absence alone cannot
  catch a dead link left by a wrong `_href` value.
- AGENTS.md points at the vocabulary doc.
- Report what was deployed, what was skipped, and any deviation recorded in the ADR.

## Re-running

Re-running against an already-bootstrapped repo is a refresh: regenerate the files
from current templates, show the diff against the deployed copies, and let the user
pick per file. Never silently overwrite a deployed copy — the repo owns it.
