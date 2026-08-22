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
- **Sidecar-to-frontmatter sync.** agents/openai.yaml hand-restates a compressed form of
  SKILL.md's description with no check tying them together, unlike the digest's
  traceability. If the description is retuned and the sidecar drifts, add a deterministic
  check (or generate the sidecar) rather than syncing by hand again.
- **Consult-path eval coverage.** Evals 1-3 withhold golden-pairs.md as the ground-truth
  holdout, so the suite never tests whether consulting it at a boundary changes a
  verdict. A v2 eval with a non-fixture document would close that gap; extending
  skills/check_contamination.py to the tech-writing fixtures would mechanically catch
  answer-key leaks into SKILL.md.
