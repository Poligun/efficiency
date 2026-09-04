# project-manager — design

> Status: **confirmed** (2026-08-20 grilling session). The system-level design
> lives in [pm-setup/meta/design.md](../../pm-setup/meta/design.md); this file
> covers only what is specific to the operations skill.

## What this is

The day-N half of the issue-management package: the skill that keeps a
bootstrapped tracker honest (audit) and answers "what now?" (frontier). It is
the automation the originating repo's ADR parked as "round 3 work" — the two
standing rules (`resolution/done` backfill on auto-closed issues, closing an
epic when its last task closes) are defined in the taxonomy as
*audited-after-the-fact*, so until this skill existed they were manual habits.

## Shape

Two modes over one precondition:

- **Precondition**: `.claude/tracker.md` exists and is read first. Every
  tracker operation is performed the seam file's way. This is what makes the
  skill backend-portable by construction — it is queries and fixes over
  declared invariants, addressed through the fixed operation vocabulary.
- **Audit**: standing rules first (they are expected drift, the happy path's
  cost), then structural invariant checks. Findings as one table; fixes as one
  confirmed batch. A clean audit reports in one line.
- **Frontier**: the read side — urgent, ready (minus blocked), in-flight with
  progress, spec queue, backlog count — ending with exactly one suggested next
  action.

## The authority boundary

The skill proposes and repairs; it never decides. Concretely: it may backfill a
resolution and close a finished epic (both confirmed), because those are
mechanical completions of decisions already made elsewhere. It may not create,
reprioritize, graduate, or flip status — those are the deliberate decisions the
status family exists to record, and they belong to the human (via grilling /
spec flow). The one-suggestion rule at the frontier's end is deliberately a
suggestion, not a triage act.
