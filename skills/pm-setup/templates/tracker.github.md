<!-- pm-setup template: the tracker seam file, GitHub backend.
     Placeholders: {{repo}} {{vocabulary_doc}} {{vocabulary_doc_href}}
     {{area_list}} {{doc_decisions}} {{doc_research}} {{doc_plans}}
     {{pr_template_note}} — the last is one sentence naming the repo's PR
     template path, or stating there is none.
     {{vocabulary_doc}} is the repo-root path (display); {{vocabulary_doc_href}}
     is the same file relative to THIS file's location (.claude/), so links
     resolve — e.g. docs/issues.md displays as-is but links as
     ../docs/issues.md. Delete this comment when deploying.

     Contract for any backend implementation of this file: keep the section
     headings and operation names EXACTLY as they are here — consuming skills
     address operations by name. Only the implementations (the commands, the
     mapping table, the constraints) change per backend. A backend with
     per-project workflows (Jira) fills "Transition constraints" and
     "Pass-through fields" from live discovery of the actual project. -->
# Tracker

How to operate this repository's issue tracker. Any skill that files, labels,
links, queries or closes issues reads this file first and follows it — never a
hardcoded notion of the tracker. The vocabulary itself (label semantics, state
machines, invariants) lives in [{{vocabulary_doc}}]({{vocabulary_doc_href}});
this file is about *how to perform the operations*.

## Identity

- Backend: GitHub (`gh` CLI)
- Repository: `{{repo}}`
- Vocabulary doc: [{{vocabulary_doc}}]({{vocabulary_doc_href}})
- Areas: {{area_list}}

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
  --remove-label type/idea --remove-label "status/<old>" \
  --add-label type/epic,status/needs-tickets,P<n>
```

`status/<old>` is whatever status the idea carried (usually
`status/needs-spec`) — removing it keeps the exactly-one-status invariant;
graduation swaps both the type and the status, never stacks them. Keep the
original idea as a concise section of the new body. Create new issues only
when one idea splits into several epics; then close the idea `resolution/done`
with links to its children.

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
the GraphQL API. Write:

```sh
# issue node IDs:
gh api graphql -f query='{repository(owner:"<owner>",name:"<name>"){issue(number:<n>){id}}}'
# link child to parent:
gh api graphql -f query='mutation{addSubIssue(input:{issueId:"<parent-id>",subIssueId:"<child-id>"}){issue{number}}}'
```

Read (an epic's progress and its task list):

```sh
gh api graphql -f query='{repository(owner:"<owner>",name:"<name>"){issue(number:<n>){subIssuesSummary{total completed}}}}'
gh api graphql -f query='{repository(owner:"<owner>",name:"<name>"){issue(number:<n>){subIssues(first:100){nodes{number title state}}}}}'
```

A task has at most one parent; standalone tasks are fine; epics do not nest.
Closing the last sub-issue does NOT close the epic — whoever closes the last
task also closes the epic with `resolution/done` (audited by
`/project-manager`).

### link-blocker

Write: a `Blocked by: #N` line at the top of the issue body (the sidebar
"Relationships" edge works too, but the body line is the form every consumer
can read). Read: `gh issue view <n> --json body` and look for the
`Blocked by:` line — treat the body line as the machine-readable source of
truth for blockedness. Blocked is not a status label.

### find-work

`gh issue list` defaults to 30 results and truncates silently — **always pass
`-L` comfortably above the repo's issue count** (200 here; raise it as the
tracker grows).

```sh
gh issue list -L 200 -l status/ready                 # pick up and execute now
gh issue list -L 200 -l status/needs-spec            # the grilling/spec queue
gh issue list -L 200 -l status/needs-tickets         # specs awaiting breakdown
gh issue list -L 200 -l status/backlog               # captured, not committed
gh issue list -L 200 --search 'label:P0,P1'          # urgent (comma is OR; -l is AND)
gh issue list -L 200 -l type/epic -l status/in-flight
gh issue list -L 200 -s closed -l resolution/wont-do # what we decided against
```

Audit queries:

```sh
# closed issues missing a resolution (the backfill queue):
gh issue list -L 500 --search 'is:closed is:issue -label:resolution/done -label:resolution/wont-do -label:resolution/obsolete -label:resolution/duplicate -label:resolution/cannot-reproduce'
# full invariant audit: fetch everything once, check locally:
gh issue list -s all -L 500 --json number,title,state,stateReason,labels
```

### pr-linkage

The conventions themselves (title prefix, first-line linkage, trivial-fix
exemption) live in the vocabulary doc's "PR conventions" section — one source.
The GitHub mechanics behind them: only the close/fix/resolve keywords create a
closing Development link, and **any** Development link (keyword or sidebar)
closes the issue on merge — so never sidebar-link a partial PR; `Part of #N`
stays a plain mention. {{pr_template_note}}

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
- Issues stay thin pointers: research → `{{doc_research}}`, decisions →
  `{{doc_decisions}}`, plans → `{{doc_plans}}`; link, don't restate.
