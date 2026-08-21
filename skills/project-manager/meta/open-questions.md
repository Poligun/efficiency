# Open questions

- **Eval fixtures.** Shared with pm-setup's eval question: a tracker seeded
  with known violations and a known frontier. Undecided whether that is a
  scratch GitHub repo (real, slow, rate-limited) or recorded `gh` output
  (fast, but drifts from the live API).
- **Staleness signals.** The frontier's "sat in backlog unusually long" check
  depends on what timestamps the backend exposes cheaply; GitHub gives
  createdAt/updatedAt per issue, but "unusually long" has no defined
  threshold. Left to judgment per run until a threshold earns its keep.
- **Reporting surface.** Round 2's Slack question (see pm-setup
  open-questions) most likely lands here: frontier output posted to a channel
  on a schedule. Untouched until the corp round.
- **Scheduled runs.** The audit is a natural cron/loop candidate
  (`/loop` or a scheduled agent). Deliberately not wired up yet — the
  confirmation-batch design assumes an interactive user; an unattended mode
  would need an apply-safe subset (probably just the two standing rules).
