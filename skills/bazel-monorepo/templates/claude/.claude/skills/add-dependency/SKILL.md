---
name: add-dependency
description: Add a third-party dependency (a Rust crate, a Python package or an npm package) the way this repo expects, through the pinned manifests and lockfiles. Use whenever a new external dependency is needed.
argument-hint: "[rust|python|typescript] [package] [version]"
---

Add a third-party dependency. `$ARGUMENTS` holds the language, the package
name and the version. Ask if the package or version is missing. The rules
are in `docs/conventions/dependencies.md`; a runtime dependency is a
visible decision, so the change that adds one says why the standard
library or an existing dependency did not suffice.

## Rust

1. Add a `crate.spec` entry to `MODULE.bazel`, keeping the entries sorted
   by package name:

   ```python
   crate.spec(
       features = ["some-feature"],   # only if needed
       package = "the-package",
       version = "X.Y",
   )
   ```

   There is no `Cargo.toml`. `MODULE.bazel.lock` is the lockfile; the next
   build updates it, and it is committed with `MODULE.bazel`.

2. Reference the crate as `@crates//the-package`, not `@crates//:the-package`:

   ```
   bazel run @buildozer -- 'add deps @crates//the-package' //rust/<owner>/<module>:<crate>
   ```

3. Prefer `default_features = False` plus an explicit feature list when
   the crate pulls in more than needed. A proc-macro crate that arrives
   through a feature (such as a `derive` feature) goes in plain `deps`;
   `proc_macro_deps` is only for crates that are themselves proc macros and
   are depended on directly.

## Python

1. Add `"the-package==X.Y.Z"` to `dependencies` in `pyproject.toml`, with
   a comment naming what it is for. A package without inline types brings
   its `types-*` stub package along as a second pinned entry.
2. `bazel run @uv -- lock` regenerates `uv.lock`; commit both files.
3. Reference it as `@pypi//the_package` (underscores) in the library's
   `deps`; the stub package too, so the mypy test sees it.

## TypeScript

1. Install through Bazel's pnpm, exact version, never a machine install:

   ```
   bazel run -- @pnpm//:pnpm --dir $PWD/typescript add --save-dev --save-exact the-package@X.Y.Z
   ```

   This updates `typescript/package.json` and `typescript/pnpm-lock.yaml`;
   commit both.
2. Reference it as `//typescript:node_modules/the-package` in the
   library's `deps`. A package only a Bazel target consumes is named in
   `knip.jsonc`'s `ignoreDependencies`.

## Then

`bazel build //... && bazel test //...` must pass. A member of a pinned set
(docs/conventions/dependencies.md names them) moves with its set or not at
all.
