<!-- pm-setup template: section to append to AGENTS.md (or CLAUDE.md).
     Placeholders: {{vocabulary_doc}} {{adr_path}} {{adr_number}}.
     Delete this comment when deploying. -->
# Issues and PRs

Read [{{vocabulary_doc}}]({{vocabulary_doc}}) before filing, labeling or closing an
issue, and before opening a PR. It is the working reference for
[ADR {{adr_number}}]({{adr_path}}); the ADR wins if they disagree. The tracker
operations themselves (commands, linking, queries) are in
[.claude/tracker.md](.claude/tracker.md). The short version — a summary only;
where it and the doc disagree, the doc wins:

- Five slash-named label families: `type/` (epic, task, bug, idea), bare
  `P0`–`P3` (default `P2`), `area/`, `status/`, `resolution/`.
- Open issue: exactly one type, one status, one priority (ideas carry
  none). Closed issue: exactly one `resolution/*` saying why; the native
  close reason is derived from it (`done` → completed, rest → not planned).
- Titles start with the type in brackets: `[Task] component: ...`.
- Status names the next deliberate action (`backlog`, `needs-spec`,
  `needs-tickets`, `in-flight`, `ready`). In progress, in review, blocked
  and done are never labels — assignee, PR, dependency edges and closing
  carry them.
- Tasks are native sub-issues of their epic. Ideas graduate by rewriting
  the same issue into the epic.
- PR titles: `[#N] component: summary`. PR body first line: `Closes #N` or
  `Part of #N`. Trivial fixes exempt. The PR template carries the shape.
- Issues are thin pointers: research, decisions, plans and vocabulary live
  in the repo; link them, do not restate them.
