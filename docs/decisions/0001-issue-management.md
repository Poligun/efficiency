# 1. Issue management: adopting the pm-setup taxonomy

Status: accepted
Date: 2026-08-20

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
[docs/issues.md](../issues.md) and is owned by this repo — there is no sync
obligation to the template or to other repos that adopted it.

This was the inaugural `pm-setup` run: the repo that houses the skill is its
first consumer, and this bootstrap doubled as the skill's acceptance test.

## Decisions

### This repo's answers

- **Areas**: `area/review` (deep-code-review, business-logic-review,
  review-loop), `area/pm` (pm-setup, project-manager), `area/evals`
  (benchmarks, eval fixtures, workspace infra), `area/docs` (meta docs,
  README, repo knowledge).
- **Doc layout**: the scarlet default — `docs/decisions/` for ADRs,
  `docs/research/` for research notes, `plans/` for implementation plans,
  `CONTEXT.md` for vocabulary. All were created by this bootstrap; the
  per-skill `meta/` directories continue to hold skill-local design records,
  with the new directories owning only cross-skill material.
- **PR template**: created new at `.github/PULL_REQUEST_TEMPLATE.md` — the
  repo had none. (Filed before the interview gained its PR-template question;
  kept deliberately, as this repo's PRs already use it.)

### Deviations from the template

None.

### Migration

No-op: the repo had zero issues at bootstrap. The nine stock GitHub labels
were deleted; no custom labels existed.

## Consequences

- [docs/issues.md](../issues.md) is the operative reference; AGENTS.md points
  at it, so every agent session loads the vocabulary.
- `.claude/tracker.md` is the seam consuming skills read to operate the
  tracker; spec/ticket skills follow its "For lifecycle skills" section instead
  of their generic defaults.
- The invariants are machine-checkable; `/project-manager` audits them and
  backfills the two standing rules (resolution on auto-closed issues, closing
  an epic when its last task closes).
