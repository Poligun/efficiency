# bazel-monorepo: improvement checklist

The first iteration carries the corpus, the templates and the apply
script, verified end to end once. What it does not yet carry, in rough
order of value:

## Next up

- [ ] **A runnable server in the proto feature.** The templates generate
      the code and implement a handler with a unit test, but nothing
      registers the service, builds the runtime or serves health and
      reflection; proto.md PB-7 and rust.md RS-14 describe that shape and
      say so. A `rust/hello/serve/` crate with bind, serve, shutdown and
      an integration test over a real socket would make the two rules
      concrete, at the cost of the tokio, tonic-health and
      tonic-reflection dependencies in the core proto feature.
- [ ] **A service-start handle template.** testing.md TE-4 describes the
      handle that starts a store per test function from a Bazel-fetched
      archive; the package sketches it and ships no code. A generic Rust
      handle over an `http_archive` plus a `tools/<service>` host alias,
      with one worked example against a public database release, would
      make TE-4 applicable on day one.
- [ ] **Evals.** No `evals/` yet. The apply mode has a deterministic
      acceptance test (the end-to-end build); the assess mode has none.
      Two fixtures would do: a small repository that violates a known set
      of rules (expect those IDs in the gap table) and a design note that
      touches three rules (expect the three cited).
- [ ] **An operator-command skeleton.** automation.md AU-3 names the
      nouns-and-verbs shape; a `python/ops/` template with one verb, the
      process seam wired, the permission list split, and a test with the
      recording runner would let a repository start from it.
- [ ] **A CI job example per shape.** gates.md GA-5 describes two shapes
      (per change, scheduled backstop) without a file. A vendor-neutral
      description of each job's steps, in the references, with the one
      cache rule that bit (never persist the repository cache).

## Bigger, later

- [ ] **Container image recipe.** A multi-arch image from a Rust binary
      with no Dockerfile (platform transition, tar layer, image index) is
      generic infrastructure; it was left out to keep the first cut free
      of deployment. Belongs as an optional feature directory.
- [ ] **Version refresh routine for the package itself.** The pins are a
      snapshot. A script that reads the current pins out of a repository
      that applied the package and proposes template bumps would keep the
      snapshot moving without hand edits.
- [ ] **Screenshot tests and the i18n catalog** as optional TypeScript
      features, once a second app has shown the shape generalizes.
- [ ] **Other hosts.** The pinned toolchains cover Linux x86_64, Linux
      arm64 and macOS arm64. Windows is unsupported by the Rust C
      toolchain choice; say what a Windows user should do instead.
