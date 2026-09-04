# Decision log

Skill-specific decisions; the package-level log is in
[pm-setup/meta/decisions.md](../../pm-setup/meta/decisions.md). Confirmed in
the 2026-08-20 grilling session.

## Confirmed

**Audit + frontier, nothing else.** (Q13)
Audit-only was rejected as a weekly chore nobody runs; frontier reporting is
nearly free (it is the seam file's find-work queries) and makes the skill a
daily driver, which is what keeps the audit actually happening. Triage
authority (graduating ideas, setting priorities) was rejected: graduation
already has a home in the grilling → `/to-spec` flow, and priority is exactly
the call an agent shouldn't make unprompted.

**Fixes are batched and confirmed, never applied on sight.**
Even the mechanical standing rules get a confirmation pass — the cost is one
approval on a table, and it keeps the skill safe to run reflexively. The one
exception to *proposing* at all: open tasks under a closed epic are flagged
without a proposed fix, because reopening-vs-closing-vs-reparenting is a real
decision.

**Model-invocable, unlike pm-setup.**
`pm-setup` mutates repo files and tracker config, so it is user-invoked only.
`project-manager` in audit/frontier mode is read-mostly with confirmed writes,
and its trigger phrases ("what should I work on", "tracker health") are
natural conversation — so its description invites model invocation.

**Pulled forward from the originating repo's round 3 into the transferrable
package.** (Q7)
The standing rules explicitly wait on it and it is backend-portable almost by
definition. The originating repo's remaining round-3 automation and its round 2
(Projects v2, milestones) stay local to it.
