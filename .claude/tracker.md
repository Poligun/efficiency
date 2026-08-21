# Tracker

How to operate this repository's issue tracker. Any skill that files, labels,
links, queries or closes issues reads this file first and follows it — never a
hardcoded notion of the tracker. The vocabulary itself (label semantics, state
machines, invariants) lives in [docs/issues.md](docs/issues.md); this
file is about *how to perform the operations*.

## Identity

- Backend: GitHub (`gh` CLI)
- Repository: `Poligun/efficiency`
- Vocabulary doc: [docs/issues.md](docs/issues.md)
- Areas: `area/review`, `area/pm`, `area/evals`, `area/docs`

## Vocabulary mapping

GitHub has no native issue types, priorities, workflow states or resolutions, so
all four families are labels:

| Concept | Carried by |
| --- | --- |
| Type (epic/task/bug/idea) | `type/*` label + title prefix `[Epic]`/`[Task]`/`[Bug]`/`[Idea]` |
| Priority | bare `P0`–`P3` label |
| Status (deliberate) | `status/*` label |
| Status (execution) | native: assignee+branch, open PR, dependency edge, closed |
| Resolution | `resolution/*` label; native close reason derived from it |
| Epic→task | native sub-issues |

## Operations

### create-issue

```sh
gh issue create --title "[<Type>] <title>" --body-file <f> \
  --label "type/<t>" --label "status/<s>" [--label "P<n>"] [--label "area/<a>"...]
```

Every open issue: exactly one `type/*`, exactly one `status/*`, exactly one
`P0`–`P3` unless it is an idea, zero or more `area/*`.

### rewrite-issue

Idea graduation rewrites the same issue in place — one URL carries the history:

```sh
gh issue edit <n> --body-file <spec> --title "[Epic] <title>" \
  --remove-label type/idea --add-label type/epic,status/needs-tickets,P<n>
```

Keep the original idea as a concise section of the new body. Create new issues
only when one idea splits into several epics; then close the idea
`resolution/done` with links to its children.

### transition-status

```sh
gh issue edit <n> --remove-label "status/<old>" --add-label "status/<new>"
```

Status flips only on a deliberate decision (committing, spec done, tickets cut,
clarified). Never flip status as a side effect of work — the native signals
already carry in-progress/in-review/blocked/done.

### close-with-resolution

```sh
gh issue edit <n> --add-label "resolution/<r>"
gh issue close <n> --reason <completed|"not planned">   # derived: done → completed, else not planned
```

Leave the `status/*` label in place — it freezes as history. Duplicates: use
`--reason "not planned"` plus `resolution/duplicate` and a comment naming the
original (the native duplicate reason goes unused). An issue auto-closed by a
merged PR is missing its resolution — backfill `resolution/done` (whoever
merges, or the `/project-manager` audit).

### link-parent

Tasks are native sub-issues of their epic. `gh` has no subcommand for this; use
the GraphQL API:

```sh
# issue node IDs:
gh api graphql -f query='{repository(owner:"<owner>",name:"<name>"){issue(number:<n>){id}}}'
# link child to parent:
gh api graphql -f query='mutation{addSubIssue(input:{issueId:"<parent-id>",subIssueId:"<child-id>"}){issue{number}}}'
```

A task has at most one parent; standalone tasks are fine; epics do not nest.
Closing the last sub-issue does NOT close the epic — whoever closes the last
task also closes the epic with `resolution/done` (audited by
`/project-manager`).

### link-blocker

A native dependency edge where available (issue sidebar "Relationships"), or a
`Blocked by: #N` line at the top of the body. Blocked is not a status label.

### find-work

```sh
gh issue list -l status/ready                 # pick up and execute now
gh issue list -l status/needs-spec            # the grilling/spec queue
gh issue list -l status/backlog               # captured, not committed
gh issue list --search 'label:P0,P1'          # urgent (comma is OR; -l is AND)
gh issue list -l type/epic -l status/in-flight
```

Audit queries (closed-without-resolution and invariant checks) are in the
vocabulary doc's "Useful queries" section.

### pr-linkage

- PR title: `[#N] component: summary`.
- PR body first line: `Closes #N` (only on the PR that finishes the issue —
  any Development link closes on merge) or `Part of #N` (plain mention, never
  sidebar-linked) for partial work.
- Trivial fixes (typo, comment, formatting) are exempt.
- Shape: `.github/PULL_REQUEST_TEMPLATE.md`.

## Transition constraints

None. GitHub imposes no required fields on any transition. (On a backend with
per-project workflows, this section lists each transition and the fields it
demands, discovered from the live project — e.g. "In Progress → Done requires
`resolution` and `story points`".)

## Pass-through fields

None. (On a corp backend this section lists fields that exist outside the core
taxonomy — sprint, story points, due date — and when they are demanded. Skills
prompt for them at the moments this section says they are required; the core
taxonomy never absorbs them.)

## For lifecycle skills

Instructions for any spec/ticket skill (e.g. `/to-spec`, `/to-tickets`),
**overriding their generic defaults** — in particular, do NOT use a
`ready-for-agent` label here:

- Publishing a spec: rewrite the target issue in place per **rewrite-issue**
  (`type/epic`, `status/needs-tickets`, a priority). New epic with no prior
  idea: **create-issue** with the same labels.
- Publishing tickets: one **create-issue** per ticket with `[Task]`,
  `type/task`, `status/ready`, a priority, then **link-parent** to the epic;
  finally **transition-status** the epic to `status/in-flight`.
- Blocking edges between tickets: **link-blocker**.
- Issues stay thin pointers: research → `docs/research/`, decisions →
  `docs/decisions/`, plans → `plans/`; link, don't restate.
