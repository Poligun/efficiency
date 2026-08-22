# Open questions and recorded exclusions — tech-writing

This file records the material deliberately left out of the rule corpus, per
[ADR 2](../../../docs/decisions/0002-technical-writing-skill.md), with the condition under
which each exclusion would be revisited. Provenance for the underlying research is in
[research-notes.md](research-notes.md).

## Excluded from the Google developer documentation style guide

- **"Knowledgeable friend" framing and the general friendliness stance.** Merge M6 drops
  it: the house voice permits conversational register by section intent and bans
  condescension; it does not aim for friendliness. Revisit only if the skill is ever
  pointed at consumer-facing documentation.
- **General pro-contraction stance.** Merge M7 drops it, keeping only the
  negation-contraction clarity note (S15). Revisit if review mode over-flags formal
  phrasing.
- **"Write around jargon" default.** Merge M5 drops it for expert audiences. Revisit if
  the corpus is applied to mixed-expertise audiences.
- **Global-audience short-sentence emphasis.** Merge M2 drops it as staccato pressure,
  keeping only the idiom ban (W6). Revisit if translated output becomes a real audience.
- **The word list wholesale (~500 entries).** The list is Google-product-heavy; only the
  ~dozen generic entries in W7 and the bloated phrases in S10 are adopted. Candidates
  promote to W7 one at a time when review findings justify them.
- **Product-name, HTML/markup, UI-element, and formatting-minutiae rule families.** These
  families are out of scope for prose documents. Revisit per family if the skill starts
  reviewing reference docs or UI copy.

## Excluded from the Technical Writing courses

- **Process-level rules** (read aloud, come back later, ask a peer, adopt a style guide).
  These are writer workflow, not text properties, so they fit neither the D/P/S/W families
  nor review mode. They are candidates for write mode in v2.
- **Illustrations and sample-code units.** These units are out of scope for v1, which
  targets prose.

## Watch items

- **Williams' black-hole passage.** The passage is absent from the extracted chapters, and
  secondary sources disagree on its direction. Do not use it as eval ground truth (issue #7) without
  checking the book's cohesion chapter; its point is independently supported by the
  extracted text and encoded in P1/S5.
- **Question-heading counter-positions** (plainlanguage.gov, Microsoft) are rejected by
  merge M4 and locked in by evals/fixtures/question-headers-consumer-cited.md (eval 3): a
  document citing those traditions still has its question headings flagged. Revisit only if
  the skill is ever pointed at consumer-facing documentation, together with the M6
  exclusion above.
- **Digest cost** (ADR 2 watch item). The open question is whether the always-on digest's
  token cost or constraint pressure degrades agent thinking. Observations land in
  [observations.md](observations.md), created with the digest work (issue #9).
