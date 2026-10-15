---
name: new-module
description: Scaffold a new module library (Rust, Python or TypeScript) in its own package, wired through the repo's wrappers the way the conventions require. Use whenever adding a module, crate, py_library or ts_library to this repo.
argument-hint: "[language] [owner] [module]"
---

Scaffold a module library. `$ARGUMENTS` holds three words: the language
(`rust`, `python` or `typescript`), the owning program (the binary, program
or app, for example `hello`) and the module name (for example `store`). Ask
if any is missing.

Below, O is the owner and M the module. The rules are in
`docs/conventions/<language>.md` and `docs/conventions/layout.md`; if this
file and those disagree, the conventions win.

## Steps

1. Create the directory `<tree>/O/M/`, where `<tree>` is `rust`, `python`
   or `typescript`, and the root file named after the directory:
   `M.rs`, `M.py`, or `M.ts` (`M.tsx` for a React component). Start it
   with a doc comment saying what the module is for. For Rust, end it with
   an inline test module; for Python and TypeScript, add `M_test.py` or
   `M_test.ts` beside it, with at least one test.

2. Create `<tree>/O/M/BUILD.bazel` with exactly two declarations, loaded
   from the repo's wrappers, never from the rulesets directly:

   Rust:

   ```python
   load("//tools/rust:defs.bzl", "rust_library", "rust_test")

   rust_library(
       name = "O_M",
       srcs = glob(["*.rs"]),
       crate_root = "M.rs",
       visibility = ["//rust/O:__subpackages__"],
       deps = [],
   )

   rust_test(
       name = "O_M_test",
       crate = ":O_M",
   )
   ```

   Python:

   ```python
   load("//tools/python:defs.bzl", "py_library", "py_test")

   py_library(
       name = "O_M",
       srcs = ["M.py"],
       visibility = ["//python/O:__subpackages__"],
       deps = [],
   )

   py_test(
       name = "O_M_test",
       srcs = ["M_test.py"],
       deps = [":O_M"],
   )
   ```

   TypeScript (`tsconfig` and `config` name the app root's targets):

   ```python
   load("//tools/typescript:defs.bzl", "ts_library", "ts_test")

   ts_library(
       name = "M",
       srcs = ["M.ts"],
       tsconfig = "//typescript/O:tsconfig",
       visibility = ["//typescript/O:__subpackages__"],
       deps = [],
   )

   ts_test(
       name = "M_test",
       srcs = ["M_test.ts"],
       config = "//typescript/O:vite_config",
       tsconfig = "//typescript/O:tsconfig",
       deps = [":M", "//typescript:node_modules/vitest"],
   )
   ```

   The wrappers declare the lint, format and type-check targets; never
   write one by hand.

3. Wire the new library into its consumers with buildozer, not text edits:

   ```
   bazel run @buildozer -- 'add deps //<tree>/O/M:O_M' //<tree>/O:O
   ```

   For Python, also add `O` to `known-first-party` in `pyproject.toml` if
   the program is new.

4. `bazel run //:buildifier`

5. `bazel build //... && bazel test //...` must pass before the work is done.

## Variations

- A test helper library goes in `<tree>/O/M/testutil/` with root
  `M_testutil.<ext>` (Rust) or `testutil.<ext>` (Python, TypeScript), the
  name `O_M_testutil`, and `testonly = True`.
- A Rust test with its own source file (an integration suite, or a
  standalone test over the public API) goes in `rust/O/M/tests/`, its own
  package, as a `rust_test` with `srcs` and the crate under test in `deps`
  by full label; `size`, `tags` and `args` sit with it.

## Rules that are easy to get wrong

- Rust `rust_test` uses `crate = ":O_M"`, never `deps = [":O_M"]`. With
  `deps` the test binary passes while running nothing. The wrapper refuses
  a test with both or neither of `crate` and `srcs`.
- `glob(["*.rs"])`, never recursive. Subdirectories are their own Bazel
  packages, and the wrappers cannot glob for you.
- The root file is named after the directory, while the target keeps the
  `O_M` name. No `lib.rs`, no `mod.rs`, no `__init__.py`, no `index.ts`,
  no `src/`. No two files under one owner's tree may share a name.
- Keep visibility at `//<tree>/O:__subpackages__`. If a second owner needs
  the library later, move it up to `<tree>/<name>/` instead of reaching
  sideways.
