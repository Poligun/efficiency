<!-- pm-setup template. Placeholders: {{number}} {{date}} {{repo}} {{area_list}}
     {{doc_layout}} {{vocabulary_doc}} {{deviations}} {{migration_note}}.
     Delete this comment when deploying. -->
# {{number}}. Issue management: adopting the pm-setup taxonomy

Status: accepted
Date: {{date}}

## Context

This repo adopts the issue-management system deployed by the `pm-setup` skill:
five label families (`type/*`, bare `P0`–`P3`, `area/*`, `status/*`,
`resolution/*`), a hybrid state machine where labels carry only deliberate
decisions and GitHub's native signals carry execution states, one closed state
with a `resolution/*` saying why, tasks as native sub-issues of epics, and PR
linkage by body keyword with `[#N]` title prefixes.

The taxonomy originates in scarlet's ADR 0015, where the rationale for each
piece is argued in full (why no severity scale, why kanban states are not
labels, why the native close reasons are derived). This ADR records what *this*
repo answered during bootstrap; the deployed copy of the vocabulary lives in
[{{vocabulary_doc}}]({{vocabulary_doc}}) and is owned by this repo — there is no
sync obligation to the template or to other repos that adopted it.

## Decisions

### This repo's answers

- **Areas**: {{area_list}}
- **Doc layout**: {{doc_layout}}

### Deviations from the template

{{deviations}}

### Migration

{{migration_note}}

## Consequences

- [{{vocabulary_doc}}]({{vocabulary_doc}}) is the operative reference; AGENTS.md
  points at it, so every agent session loads the vocabulary.
- `.claude/tracker.md` is the seam consuming skills read to operate the
  tracker; spec/ticket skills follow its "For lifecycle skills" section instead
  of their generic defaults.
- The invariants are machine-checkable; `/project-manager` audits them and
  backfills the two standing rules (resolution on auto-closed issues, closing
  an epic when its last task closes).
