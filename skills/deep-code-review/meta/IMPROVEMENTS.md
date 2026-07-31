# deep-code-review — improvement checklist

Ideas, deferrals, and things noticed during iteration 1. Add to this freely; it's cheaper
than remembering.

## Deliberate iteration-1 cuts

- [ ] **Language-specific review passes.** Iteration 1 is language-agnostic on purpose.
      Rust-, Go-, and TypeScript-specific angles would catch a lot more, but they belong in
      a separate layer that composes with the agnostic one rather than replacing it.
- [ ] **`deep` shape sharding.** Currently a stub. Above ~2000 code lines the design says
      shard A1/A2/A3 by directory, but nothing exercises it yet and it's untested.
- [ ] **Promoting memory entries to `docs/`.** The skill offers; it doesn't implement.
- [ ] **A5 surface-consistency agent** is specified in the dispatch table but shares a role
      file with the convention scout. It should probably have its own.

## Improvements to test next iteration

- [ ] **Reuse a fresh `conventions.md` to skip the Step 3 grep pass.** The first real
      payoff from `repo-index` — turns a per-review cost into a per-repo one. Needs a
      freshness definition that's actually trustworthy.
- [ ] **Measure whether A1 and A2 (wire + code API) are worth being separate agents.**
      They corroborate often, which is signal, but it's two Opus calls. Try merging and
      compare finding counts and quality.
- [ ] **Feed verifier REFUTED verdicts back into the false-positive list.** If the same
      class of finding gets refuted across several runs, that's an exclusion the list is
      missing — and harvesting it automatically beats hand-maintaining the list.
- [ ] **Track which angle produced each finding** through to the report, so per-angle yield
      is measurable across iterations. Cheap to add, and it's what would let angles be cut
      on evidence rather than intuition.
- [ ] **A "what did the deleted code do" pass.** For every removed line, name the invariant
      it enforced and find where the new code re-establishes it. Currently only mentioned
      as an edge case for pure refactors; it deserves to be a first-class angle.

## Open design question from iteration 1 — is gating *too* aggressive?

On the dependency-bump fixture the skill stopped early: 29.8k tokens, 123s, zero
subagents. The baseline, with no skill and no stopping rule, spent 47.4k tokens and 731s
— and found substantially more: `reqwest 0.13` silently swaps the default TLS backend
from native-tls to rustls+aws-lc-rs (a runtime certificate-verification change and a new
C build dependency), the MSRV jumps 1.64 → ~1.86, and the committed lockfile is
hand-edited such that `cargo check --locked` fails outright.

So the skill is ~1.6× cheaper and ~6× faster, and it missed real risk.

The design's premise is that a dependency bump contains no *reviewable code*, which is
true — but it quietly assumed that means there's nothing worth reviewing, which is false.
Supply-chain and build-contract risk is real review surface and the current aspect model
has no home for it.

- [ ] **Add a `dependency` aspect** rather than treating dep-only branches as an early
      stop. It would activate on `dep_major_bump` or a lockfile-only change, and dispatch
      one cheap agent whose whole job is: what changed in the bumped crates' default
      features, does the MSRV move, does the lock resolve. That keeps gating's cost win
      while closing the gap the baseline exposed.
- [ ] Related: the skill should probably run `cargo check --locked` (or the ecosystem
      equivalent) when a lockfile changes. The baseline found the broken lock by building;
      the skill never tried.

## The severity rubric has no row for latent defects

Raised by the eval-4 agent, and it's right. On the eval branch roughly a third of the
feature surface is defective *in code that ships* but masked by an unimplemented stub — the
generated expressions are wrong, but nothing reaches them yet. These defects ship no wrong
behavior today and are certain to the moment the stub lands.

The rubric's severity ladder is defined by impact-now, so different reviewers would rank
these anywhere from LOW ("nothing is broken") to HIGH ("this is baked into the generated
output"). The agent handled it by reporting real severity with a "latent until X lands"
marker, which is a reasonable invention, but the rubric should say so rather than leaving
it to be reinvented.

- [ ] **Add a `latent` marker orthogonal to severity**, the way `fix_clarity` is
      orthogonal. Severity states impact when reached; `latent: <what unblocks it>` states
      that it isn't reached yet. That keeps severity meaning one thing and stops the
      "is it CRITICAL or LOW" argument from being a coin flip.

## From iteration-1 eval run-notes

- [ ] **`dep_major_bump` notes don't name their source manifest.** The signal is attached
      to `files[].signals` while the human-readable version pair lands in top-level `notes`.
      Trivial to correlate with 2 files; painful with a 40-crate wave across several
      manifests. Prefix the note with the path. *(eval-3)*
- [ ] **Step 1 doesn't say whether Step 2 still applies after an early stop.** The eval-3
      agent read the diff anyway because it was 14 lines and it needed the version numbers —
      correct, but it had to reason it out. For a large docs-only stop, re-reading
      everything is waste. Add half a sentence: "skim enough to report the bumps, then
      stop." *(eval-3)*

## Things noticed while building

- [ ] `scope_detect.py` has no tests. It's the one component with a right answer, so it's
      the one component that should have them. A fixture repo per classification rule would
      pay for itself the first time a regex gets edited.
- [ ] The `api_surface_touched` regex is indentation-sensitive (≤4 columns), which will
      miss exported items inside heavily-nested modules and match some things it shouldn't
      in languages with different indentation norms. Works for now; revisit if it produces
      noise.
- [ ] Untracked files are read whole and treated as all-additions. Correct, but it means a
      large new file dominates `code_lines` and can push the shape up. Watch for it.
- [ ] The report cap (~15) and the verifier cap (12) were picked by judgment, not measured.
      Worth checking whether either binds in practice and whether the cut order is right.
- [ ] No handling yet for a review spanning multiple repos (a monorepo with independent
      packages, or a change that spans a backend and its generated client).

## Bigger directions

- [ ] **Post-merge outcome tracking.** Which findings did the author actually act on? That
      signal is the only real measure of whether this is useful, and it's recoverable from
      the PR after the fact.
- [ ] **A "review the review" pass** — an agent that reads the finished report and asks
      what a senior engineer would say is missing. Cheap, and the completeness critic
      pattern tends to find real gaps.
- [ ] **Severity calibration against history.** If the repo's git history shows which past
      changes caused incidents, severity could be grounded in that rather than in judgment.
