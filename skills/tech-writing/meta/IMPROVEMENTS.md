# Improvements backlog — tech-writing

This file holds recorded-but-deferred improvements, per the layout the review skills use.

- **Write-mode evals (v2).** ADR 2 scopes v1 evals to review mode; issue #7 records the
  deferral here. Write-mode evals need a task battery (draft a PR description, a plan
  section, an ADR paragraph) judged against the corpus, which in turn wants the digest
  (#9) installed so ambient and triggered behavior can be compared.
- **Density thresholds for W2, S4, and P2.** The corpus marks these rules "mechanical
  (detection) plus judgment (the verdict)". If review runs disagree too often on the
  verdicts, ratify numeric thresholds (hits per hundred words, run length) and promote
  the rules to fully mechanical.
- **Scanner subject-awareness.** scripts/prose_checks.py flags anthropomorphic verbs
  lexically, so human subjects ("the integrator asks") produce candidates. If candidate
  noise becomes a problem in practice, add a subject heuristic before the verb match.
