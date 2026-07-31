# Convention probes

Load this in Step 3 when building the convention ledger, if the repo's language or layout
isn't one you can probe from memory.

The goal is **counts, not impressions**. Every probe should end with a number of
supporting files and a number of counterexamples, because the establishment test is what
separates a convention from a coincidence.

> **Quote your globs.** `grep --include=*.rs` fails outright under zsh — the default shell
> on macOS — with `no matches found`, because zsh expands the glob before grep sees it and
> errors when nothing matches in the current directory. Write `--include="*.rs"`. The same
> applies to any `*` you intend a command rather than the shell to interpret. This bites
> often enough to be worth the line.

## Start with written rules

```bash
ls CLAUDE.md AGENTS.md CONTRIBUTING.md .cursor/rules/ .github/ 2>/dev/null
cat .editorconfig 2>/dev/null
```

A written rule is worth more than any inference — it's `established` by declaration.
Note it, and note anything it delegates to tooling: if the repo says "run the formatter
and the linter before committing", then formatting and lint findings are **out of scope by
the repo's own rule**, and citing them is noise.

## What to probe, in priority order

The new code's *shape* determines which probes matter. A new module means module
structure and visibility; a new handler means error handling and validation; a new data
type means serialization and naming.

**Module structure and re-exports** — how do sibling modules expose their contents?
```bash
grep -rn "^pub mod\|^mod \|^pub use\|^export \|^from \.\|__all__" \
  --include="mod.rs" --include="index.ts" --include="__init__.py" src/ | head -40
```
Look for the *pairing*: private declaration plus explicit re-export is a different
convention from public declaration, and new code usually gets this wrong.

**Visibility defaults** — is the codebase liberal or conservative with public surface?
```bash
grep -rc "pub(crate)\|pub(super)\|internal \|private " src/ | grep -v ':0' | wc -l
```

**Error types** — one shared error type, per-module types, or strings?
```bash
grep -rn "type .*Error\|enum .*Error\|Box<dyn Error\|thiserror\|anyhow" src/ | head -20
```
A new module introducing `type FooError = String` in a repo that uses structured errors
everywhere is a genuine finding, and a common one.

**Test placement and framework** — inline modules, a parallel tree, a `tests/` directory?
```bash
grep -rln "cfg(test)\|describe(\|def test_\|@Test\|func Test" src/ test/ tests/ 2>/dev/null | head -20
```
Count carefully before concluding anything. A repo with two test files does not have a
testing convention, and "add tests" is a project decision rather than a review finding.

**Logging, instrumentation, and naming** — same approach: grep, count, compare.

**Data access** — if the change touches persistence, does it match how the rest of the
repo queries? Raw SQL in a repo that otherwise uses a query builder is a real
inconsistency, and it's the kind that gets copied.

## Language-specific starting points

| Language | Highest-signal probes |
|---|---|
| Rust | `mod.rs` declaration + `pub use` pairing · `pub(super)`/`pub(crate)` usage · error type (`thiserror`/`anyhow`/`Box<dyn Error>`) · `#[cfg(test)]` placement · workspace lints in `Cargo.toml` |
| Go | package layout under `internal/` vs `pkg/` · error wrapping (`fmt.Errorf("%w")` vs `errors.New`) · interface definition site (consumer vs producer) · `_test.go` co-location |
| TypeScript | barrel `index.ts` re-exports · named vs default exports · `type` vs `interface` · error classes vs union returns · test co-location vs `__tests__/` |
| Python | `__init__.py` re-exports · `__all__` · custom exception hierarchy · type-hint coverage · `conftest.py` fixtures |
| Java/Kotlin | package-private vs public defaults · checked vs unchecked exceptions · builder vs constructor · annotation style |
| Proto | leading-dot fully-qualified type refs vs bare · enum prefixing (`FOO_BAR_BAZ`) · field-number blocks · comment style on messages and fields |

## Writing the ledger row

```
| Rule                                    | Support | Counter | Verdict     |
|-----------------------------------------|---------|---------|-------------|
| errors are a shared structured type     | 14      | 1       | established |
| handlers validate before persisting     | 9       | 3       | established | (3:1, note the holdouts)
| module declaration lists alphabetized   | 2       | 1       | mixed       |
| inline test modules beside the code     | 2       | 0       | absent      |
```

The last two rows are where reviewers go wrong.

**Row 4:** two occurrences and *zero* counterexamples still fails, because three is the
floor. Two files agreeing is how a reviewer talks themselves into a rule nobody follows —
and "you didn't write tests like these two files do" is a project decision, not a defect.

**Row 3:** the counts are what demote it. Without them you'd file a plausible finding
against the author for not alphabetizing — a finding the codebase itself contradicts, and
one that costs you credibility on everything else in the report.

**Row 2** is why the ratio rule exists: 9-against-3 is a real pattern with holdouts, and
treating it as `mixed` would make a widely-followed rule unenforceable. Cite it, and
mention the holdouts.
