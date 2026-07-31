# False positives

Pass the relevant section to **finders and verifiers alike**. A finding that's never
raised costs nothing to verify, and the finder is the cheaper place to stop it.

These aren't arbitrary. Each one is a thing reviewers reliably report that wastes the
author's time — either because it's factually not a defect, because CI already catches it,
or because it's an opinion wearing a defect's clothes.

## API design — wire contracts and public code surface

- **Additive changes called "breaking."** A new field, message, method, or optional
  parameter doesn't break anyone.
- **`reserved N` called a breaking change in itself.** It's the correct ritual for
  removing a field. The finding, if any, is the *removal* and who it breaks — never the
  keyword. Reporting the reservation makes it look like the author did the wrong thing by
  doing the right thing.
- **Field-number reuse warnings where no number was reused.** Check before claiming.
- **"Should be an enum, not a bool"** where the field has exactly two states today and no
  third appears anywhere in the diff. Speculative generality is its own cost.
- **Missing pagination** on an operation returning a bounded singleton or an
  acknowledgment.
- **Missing API versioning** on an unpublished internal service with no external consumer
  you could actually find.
- **Builder-pattern advocacy** for a struct with three or fewer fields.
- **A field or operation explicitly marked unimplemented in the contract itself.** That's
  disclosure, and disclosure is the correct behavior. It *is* a finding when the disclosure
  lives only in the implementation while the contract promises the behavior — the
  asymmetry is the whole point, so read both sides before deciding.
- **Empty response messages** flagged as a defect. Standard, and forward-compatible.
- **Naming inconsistency with a type the branch didn't introduce or touch.** Pre-existing
  inconsistency isn't this author's to fix.
- **"This should be async / should return a Result / should take a reference"** where the
  surrounding codebase consistently does otherwise. Consistency beats your preference.

## Business logic

- **Anything a compiler, type-checker, linter, or formatter catches.** CI runs those. If
  the repo documents a lint step (a `.cursor/rules`, a CONTRIBUTING section, a pre-commit
  config), citing a rule it already automates is pure noise.
- **Pre-existing bugs on lines the branch didn't touch** — *unless* the branch newly makes
  them reachable, which is a real finding and has to be argued as such, naming the new
  path.
- **`unwrap` / `!` / `as` / force-unwrap flagged** where the value is provably non-null
  within a few lines above.
- **"Race condition"** claims with no second holder identified. Name the other task,
  thread, or request that touches the state, or don't report it.
- **Dependency bumps flagged as bugs** without naming a specific breaking change from that
  dependency's release notes. (A version that *doesn't exist* is a different and real
  finding — the build can't resolve.)
- **`TODO` comments flagged as incomplete work** when the surrounding operation already
  returns a not-implemented error. That's consistent, not contradictory.
- **Missing input validation on a field the contract explicitly documents as
  unvalidated.** Report the *consequence* of that documented choice if it's dangerous —
  that's a real finding — but don't report the absence as an oversight.
- **Error messages, log levels, and observability gaps** unless a failure is genuinely
  invisible to anyone who could act on it.

## Conventions

- **Any "convention" with fewer than 3 supporting occurrences.** That's a coincidence, not
  a pattern.
- **Any rule the ledger marked `mixed`.** The repo is inconsistent; the author picking a
  side isn't a defect. It can be a note about the inconsistency, addressed to the team.
- **Anything a formatter owns** — import order, line width, trailing commas, alignment,
  whitespace.
- **"Missing tests" where the repo has no established testing convention.** Two test
  modules across an entire tree is not a convention, and demanding tests a codebase
  doesn't have is a project decision, not a review finding.
- **Deviations inside generated files.**
- **A convention inferred from exactly one neighboring file.**
- **Naming preferences with no in-repo counterpart** — "I'd have called this
  `AlertService`" is not reviewable.
- **Convention findings on files the branch only edited** rather than created.

## The general test

Before reporting anything, ask: *could I have written this finding without reading the
code?*

If yes, it's a category, not a finding, and it belongs in a style guide rather than a
review. The findings worth writing are the ones that required someone to actually trace
what happens.
