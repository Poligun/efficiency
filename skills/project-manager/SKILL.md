---
name: project-manager
description: Audit the issue tracker's invariants (missing resolutions, epics whose tasks all closed, label violations) and report the work frontier (what's ready, blocked, needs spec, urgent). Use when the user asks for a tracker audit, project status, "what should I work on", "what's ready", backlog health, or to clean up issue labels. Requires a repo bootstrapped by /pm-setup.
---

# project-manager

The day-N operations skill for a repo bootstrapped by `/pm-setup`: audit the
tracker's invariants and apply fixes on confirmation, and report the work
frontier. It holds **no triage authority** — it never graduates ideas, sets or
changes priorities, or decides what work means. Those are human calls made
through the grilling → spec flow.

Both modes end in human-facing output. Write its prose in the house voice,
whose rules the installed tech-writing digest carries, and keep the mandated
shapes (the audit table, the report sections) as specified below. Invoke the
tech-writing skill only for prose beyond the routine sections.

## Preconditions

Read `.claude/tracker.md` first — every tracker operation below is performed the
way that file says, never from memory. If it does not exist, stop: this repo is
not bootstrapped; point the user at `/pm-setup`. Read the vocabulary doc the
seam file names for the invariants and label semantics — the **deployed doc and
the repo's adoption ADR are authoritative**: audit what they declare, honoring
any recorded deviations. The checks listed below are the universal core's
default shape, not a second source of truth; where a repo's doc deviates, its
doc wins and this list yields.

## Mode selection

Two modes; run what was asked, default to both (audit, then frontier) when the
request is general ("how's the project", "tracker health").

## Audit

Check every invariant the vocabulary doc declares. For each violation found,
propose the fix; apply only what the user confirms, as one batch. The two
**standing rules** are expected drift, not anomalies — lead with them:

1. **Resolution backfill** — closed-as-completed with no `resolution/*` label
   means `resolution/done`; propose the backfill. Closed-as-not-planned with no
   resolution has no default — ask, per issue.
2. **Epic close** — an open epic whose sub-issues are all closed: propose
   closing it `resolution/done` (per close-with-resolution in the seam file).

Then the structural checks, per issue:

- Open: exactly one `type/*`; exactly one `status/*`; exactly one `P0`–`P3`
  unless `type/idea`; zero `resolution/*`.
- Closed: exactly one `resolution/*`.
- Title prefix (`[Epic]`/`[Task]`/`[Bug]`/`[Idea]`) matches the type label.
- Ideas carrying a priority (they must not, until graduation).
- Tasks whose parent epic is closed but which remain open (orphaned work —
  flag, don't propose; this one needs a human decision).

Present findings as one table: issue, violation, proposed fix. Nothing is
applied without confirmation. If everything passes, say so in one line — a
clean audit is not a report.

## Frontier

The read side: what the tracker says about *now*. Use the seam file's
find-work queries; report as short sections, skipping empty ones:

- **Urgent** — open `P0`/`P1`, any type.
- **Ready** — `status/ready` tasks an agent or human can pick up immediately;
  note blocked ones (dependency edge or `Blocked by:` line) separately.
- **In flight** — epics with `status/in-flight`, each with its sub-issue
  progress (closed/total).
- **Spec queue** — `status/needs-spec` (what to grill next) and
  `status/needs-tickets` (specs awaiting breakdown).
- **Backlog** — count only, plus anything that has sat in `status/backlog`
  unusually long if the tracker's timestamps make that visible.

End with one suggested next action — the single highest-leverage item (an
urgent ready task beats a spec-queue entry beats backlog grooming). A
suggestion, not a triage decision.

## Boundaries

- Never create, reprioritize, or graduate issues.
- Never close anything except the two standing rules above, confirmed.
- Never **transition** a `status/*` label from one lifecycle state to another —
  those are deliberate human decisions made elsewhere. Repairing a label-count
  violation is different: removing the stale extra status a bad graduation
  left stacked (keeping the current one) is repair, goes through the same
  confirmed batch as every fix, and is squarely this skill's job.
- Batch tracker calls where possible; the audit should not take a hundred
  round trips on a fifty-issue tracker. Fetch all issues with labels in one
  query and check locally, always passing an explicit result limit comfortably
  above the repo's issue count — CLI defaults truncate silently, and a
  truncated audit reads as a clean one.
