# Observations — digest cost and constraint pressure

This file tracks the ADR 2 watch item: whether the always-on digest's token cost or its
constraint pressure degrades the agent's thinking. Add an entry whenever either effect is
observed, and also when a period of use passes cleanly, so absence of harm is recorded
rather than assumed.

Each entry follows this shape:

## YYYY-MM-DD: short context

- Surface: global CLAUDE.md, or AGENTS.md of a named repo.
- Digest size: approximate token count of the marked block at the time.
- Observation: what happened, with the prompt or task type named (rules ignored under
  load, over-cautious prose, degraded planning, or a clean period with none of these).
- Action: none, tune the digest, or escalate to a tracked issue.

## 2026-08-22: initial install

- Surface: global CLAUDE.md.
- Digest size: roughly 350 tokens (15 content lines).
- Observation: baseline entry at install time; no usage yet.
- Action: none.
