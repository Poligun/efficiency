# Decision log

Why pm-setup is shaped the way it is. Convention: the **rejections** are the
valuable half. All confirmed in the 2026-08-20 grilling session (Q-numbers
refer to it).

## Confirmed

**Efficiency bootstraps itself via the skill, not by hand.** (Q1)
A second manual install (after scarlet) teaches nothing and creates a divergent
copy; the inaugural run against this repo is the acceptance test. Rejected:
hand-applying the taxonomy first and extracting the skill later.

**Three-part set: setup + project-manager + unmodified upstream lifecycle
skills.** (Q2, Q12, Q15)
Deployment and operation split on cadence. `/to-spec`/`/to-tickets` are
`npx skills install` artifacts — users grab them from their preferred channel;
we neither vendor nor fork them. They already contain the integration hook in
their own text ("the vocabulary should have been provided to you", "unless
instructed otherwise"), so the seam file's "For lifecycle skills" section plus
the AGENTS.md pointer is sufficient and deterministic. Rejected: one monolithic
skill; forking the upstream skills into this repo (maintenance burden, no gain);
relying passively on AGENTS.md alone without explicit stamping instructions.

**Templates are the master; deployed copies are owned; no sync.** (Q3)
Keeping N repos in lockstep with a master is a maintenance treadmill for a
stable taxonomy. Scarlet's `issues.md` regenerates once to prove round-tripping,
then it too is just an owned copy. Rejected: scarlet-as-canonical with the
skill vendoring snapshots; any ongoing sync obligation.

**Skills live in this repo, symlinked into `~/.claude/skills/`.** (Q4)
Matches deep-code-review / business-logic-review / repo-index. Plugin packaging
is the eventual corp-transfer vehicle but belongs with round 2, once the seam
has a second backend to justify it. Rejected: personal-only skills (invisible,
unversioned); plugin-first (premature).

**Tiered interview: impose the core, ask areas + doc layout only.** (Q5, Q10)
Full interview defeats "easily transferrable"; zero interview breaks on repos
with existing doc conventions. One doc-layout question keeps the "issues are
thin pointers" tenet intact — stripping doc references when a repo lacks the
dirs would quietly delete the principle the pointers serve. Deviations land in
the generated ADR, not in more questions.

**Seam now, GitHub only; fixed operation names.** (Q6, Q9)
The indirection is nearly free at design time (it's prose — what skills are
made of) and painful to retrofit once several repos have `gh` incantations
baked into skills. Fixed names are what make consuming skills writable against
any backend; free-form "the file explains the tracker, skills figure it out"
was rejected as unimplementable. Jira's per-project variability (workflows,
required fields, sprints/points/due-dates) is handled structurally — discovery
-generated seam file, per-transition constraint declarations, pass-through
fields — but no Jira adapter ships until a live instance exists to test
against. Rejected: hardcoding `gh` and refactoring later; building the Jira
adapter blind.

**PR template asked, consolidated, never imposed.** (2026-08-21, post-review)
An existing template is the repo's own convention: consolidation keeps its
sections and adds only the linkage header, deployed on approval; declining
leaves it untouched. Absent one, the bootstrap asks whether to create it — a
repo may legitimately run PRs without a template, and the vocabulary doc and
seam file adapt to either answer via `{{pr_template_bullet}}` /
`{{pr_template_note}}`. The linkage conventions themselves stay imposed core —
only the file is optional. Rejected: unconditional creation (the original
deploy-table shape) and the hardcoded `../.github/…` href that assumed both
the template's existence and the vocabulary doc's depth.

**Stock labels deleted, existing issues migrated guided-only.** (Q11)
Deletion of the nine stock labels was validated on scarlet. Type/status calls
on existing issues are judgment — propose per issue, batch-apply on approval,
never automatic. Rejected: touch-nothing (leaves two vocabularies live);
full-auto migration.

**project-manager = audit + frontier, no triage.** (Q7, Q13)
Pulled forward from scarlet's round 3 because the standing rules (resolution
backfill, epic close) explicitly wait on it, and it is backend-portable almost
by definition (queries + fixes over invariants). Frontier reporting makes it a
daily driver. Triage authority rejected: graduation already has a home in the
grilling → spec flow, and priority is exactly the call an agent shouldn't make
unprompted. Projects v2 (scarlet #56) rejected from the package: GitHub
-specific furniture.

**Design-stage treatment: meta/ + SKILL.md, evals deferred.** (Q14)
Same stage as review-loop. Honest deferral: evaluating a bootstrap skill needs
fixture repos; evaluating the auditor needs a tracker with seeded violations —
both are real projects, tracked in open-questions.md.
