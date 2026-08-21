<!-- pm-setup template. Placeholders: {{adr_link}} {{adr_number}} {{area_rows}}
     {{area_growth_note}} {{doc_research}} {{doc_decisions}} {{doc_plans}}
     {{doc_vocabulary}} {{tracker_href}} {{pr_template_bullet}}
     {{extra_sections}}. Href placeholders are relative to THIS file's deployed
     location so links resolve. {{pr_template_bullet}} is a full list bullet:
     either a link to whatever PR template the repo ended up with, or a
     statement that no template exists and the convention lines above are the
     whole shape. Delete this comment when deploying. -->
# Issues and PRs

The working reference for [ADR {{adr_number}}]({{adr_link}}). If the two disagree,
the ADR wins.

## The short version

- Every issue gets exactly one `type/*` label and a matching title prefix:
  `[Epic]`, `[Task]`, `[Bug]`, `[Idea]`.
- Every open issue gets exactly one `status/*` label, and one priority
  (`P0`–`P3`, default `P2`) unless it is an idea.
- Every closed issue gets exactly one `resolution/*` label saying why.
- Tasks are native sub-issues of their epic. Ideas graduate in place.
- PR bodies start with `Closes #N` or `Part of #N`; PR titles start with
  `[#N]`. Trivial fixes are exempt.
- Issues are thin pointers; research, decisions, plans and vocabulary live
  in the repo.

## Labels

### type — what kind of issue this is

| Label | Description |
| --- | --- |
| `type/epic` | Specced body of work; parent of tasks |
| `type/task` | One self-sufficient slice of work |
| `type/bug` | Something built behaves wrongly |
| `type/idea` | Direction or thought; not yet actionable |

There is no story (every task is a vertical slice already) and no chore (a
chore is a task). Regressions are not tracked separately from bugs.

### priority — how urgent, bare names

| Label | Description |
| --- | --- |
| `P0` | Drop everything; actively broken |
| `P1` | Blocks the current goal; next up |
| `P2` | Normal queue (the default) |
| `P3` | Someday; unscheduled |

Ideas carry no priority; priority arrives at graduation. There is no
severity scale (ADR {{adr_number}}).

### area — which part of the system, zero or more

| Label | Description |
| --- | --- |
{{area_rows}}

{{area_growth_note}}

### status — the next deliberate action, exactly one per open issue

| Label | Description |
| --- | --- |
| `status/backlog` | Captured; no commitment yet |
| `status/needs-spec` | Committed; awaiting a spec or grilling session |
| `status/needs-tickets` | Spec done; awaiting task breakdown |
| `status/in-flight` | Tasks exist; work underway |
| `status/ready` | Body is self-sufficient; pick up and execute |

Status labels flip only by deliberate decision. In progress, in review,
blocked and done are **not** labels — GitHub already expresses them
(assignee and an open branch or PR, open PR, dependency edges, closed) and
maintains them itself. The status label freezes when an issue closes.

### resolution — why it closed, exactly one per closed issue

| Label | Description |
| --- | --- |
| `resolution/done` | The work shipped |
| `resolution/wont-do` | Valid, but we choose not to |
| `resolution/obsolete` | Overtaken by events |
| `resolution/duplicate` | Already tracked elsewhere |
| `resolution/cannot-reproduce` | Could not reproduce (bugs) |

The native close reason is derived, never chosen: `done` closes as
completed, everything else as not planned. GitHub's native duplicate close
reason goes unused — close duplicates as not planned with
`resolution/duplicate` and a comment naming the original. An issue
auto-closed by a merged PR has no resolution label yet; closed-as-completed
with no label means `resolution/done`, and the label is backfilled (by the
merger, or by the `/project-manager` audit).

## Palette

Material Design tokens: one color per family for area, status and
resolution; blue shades per label for type; a heat ramp for priority.
Re-theming is an edit here plus a relabel pass through the tracker (see the
seam file). `type/bug` is the
one deliberate exception to type's blue family: bug-is-red is muscle
memory worth keeping.

| Family | Material token | Hex |
| --- | --- | --- |
| `type/epic` | Blue 700 | `1976D2` |
| `type/task` | Blue 400 | `42A5F5` |
| `type/idea` | Blue 100 | `BBDEFB` |
| `type/bug` | Red 700 | `D32F2F` |
| `P0` | Red 900 | `B71C1C` |
| `P1` | Deep Orange 600 | `F4511E` |
| `P2` | Amber 600 | `FFB300` |
| `P3` | Grey 500 | `9E9E9E` |
| `area/*` | Green 700 | `388E3C` |
| `status/*` | Deep Purple 500 | `673AB7` |
| `resolution/*` | Blue Grey 500 | `607D8B` |

## Invariants

Machine-checkable; the `/project-manager` skill audits them.

- Open issue: exactly one `type/*`, exactly one `status/*`, zero
  `resolution/*`; exactly one of `P0`–`P3` unless `type/idea`.
- Closed issue: exactly one `resolution/*`; status frozen as of closing.
- Title prefix matches the type label.
- An epic's tasks are its native sub-issues; a task has at most one
  parent, and standalone tasks (no epic) are fine. Epics do not nest.

## State machines

States in `status/` are labels; states marked *(native)* are GitHub
signals, not labels. Every close carries a resolution. The diagrams show
the common close paths; abandonment may close from **any** non-terminal
state with the same resolutions.

### Idea

```mermaid
stateDiagram-v2
    [*] --> backlog : captured
    backlog --> needs_spec : committed
    needs_spec --> Epic : graduates in place (spec written)
    needs_spec --> Closed : done — split into several epics
    backlog --> Closed : wont-do / obsolete / duplicate
    needs_spec --> Closed : wont-do / obsolete / duplicate
    Closed --> [*]
```

Graduation rewrites the same issue: the spec becomes the body, the
original idea survives as a concise section, `type/idea` becomes
`type/epic`. A new issue is created only when one idea splits into several
epics; the idea then closes `resolution/done` linking its children.

### Epic

```mermaid
stateDiagram-v2
    [*] --> needs_spec : committed without a spec
    [*] --> needs_tickets : a spec skill publishes the spec
    needs_spec --> needs_tickets : spec written
    needs_tickets --> in_flight : a ticket skill creates sub-issue tasks
    in_flight --> Closed : done — closed by whoever closes the last task
    needs_spec --> Closed : wont-do / obsolete
    needs_tickets --> Closed : wont-do / obsolete
    in_flight --> Closed : wont-do / obsolete
    Closed --> [*]
```

GitHub advances the epic's progress bar as sub-issues close but never
closes the parent. Closing the epic with `resolution/done` when its last
task closes is a standing rule — done by whoever closes that task, audited
by `/project-manager` — the same shape as the `resolution/done` backfill.

### Task

```mermaid
stateDiagram-v2
    [*] --> ready : ticket skill, or filed self-sufficient
    ready --> in_progress : assignee + branch (native)
    in_progress --> in_review : PR open (native)
    in_review --> Closed : done — PR merges
    ready --> needs_spec : turned out underspecified
    needs_spec --> ready : clarified
    ready --> Closed : wont-do / obsolete / duplicate
    needs_spec --> Closed : wont-do / obsolete
    Closed --> [*]
```

A blocked task is a native dependency edge (or a `Blocked by` line in the
body), visible on the issue — not a status. `ready` covers every kind of
work: coding, writing and research, operational chores. The body says
which.

### Bug

```mermaid
stateDiagram-v2
    [*] --> backlog : reported
    backlog --> ready : confirmed and prioritized
    backlog --> needs_spec : fix needs design
    needs_spec --> ready : approach settled
    ready --> in_progress : assignee + branch (native)
    in_progress --> in_review : PR open (native)
    in_review --> Closed : done — fix merges
    backlog --> Closed : wont-do / obsolete / duplicate / cannot-reproduce
    ready --> Closed : wont-do / obsolete / duplicate / cannot-reproduce
    needs_spec --> Closed : wont-do / obsolete / cannot-reproduce
    Closed --> [*]
```

## Lifecycle and the skills

| Step | Who | What it stamps |
| --- | --- | --- |
| Capture an idea | anyone | `[Idea]`, `type/idea`, `status/backlog` |
| Commit to it | you | `status/needs-spec` (the grilling queue) |
| Spec it | grilling / a spec skill | body rewritten in place, `type/epic`, `status/needs-tickets`, priority |
| Break it down | a ticket skill | sub-issue tasks with `[Task]`, `type/task`, `status/ready`, priority; epic flips to `status/in-flight` |
| Do the work | anyone | native signals; PR per the conventions below |
| Close | merge / decision | resolution label; native reason derived |

The tracker seam file (`.claude/tracker.md`) tells spec/ticket skills exactly what
to stamp; its instructions override any skill's generic defaults.

Artifacts produced on the way — research notes, ADRs, plans, glossary
entries — land in `{{doc_research}}`, `{{doc_decisions}}`, `{{doc_plans}}` and
`{{doc_vocabulary}}`; the issue links to them instead of restating them.

## PR conventions

- Title: `[#N] component: summary`.
- Body first line: `Closes #N` (creates the Development link; the issue
  closes when the PR merges) or `Part of #N` for partial work. `Part of`
  is a plain mention, not a link — GitHub's only linking keywords are
  close/fix/resolve, and any Development link (keyword or sidebar) closes
  the issue on merge. So never sidebar-link a partial PR; only the PR that
  finishes the issue gets `Closes #N` or a manual link.
- Trivial fixes (typo, comment, formatting) may skip both.
{{pr_template_bullet}}

## Useful queries

The concrete commands live in the tracker seam file
([.claude/tracker.md]({{tracker_href}}), find-work section) — this doc stays
backend-neutral. The queries that matter, whatever the backend:

- What to grill next (`status/needs-spec`), what awaits breakdown
  (`status/needs-tickets`), what's ready to pick up (`status/ready`), what's
  captured but uncommitted (`status/backlog`).
- What actually matters now (open `P0`/`P1`); epics with work underway.
- What we decided against (closed `resolution/wont-do`).
- Audit: closed issues carrying no `resolution/*` (the backfill queue).
{{extra_sections}}
