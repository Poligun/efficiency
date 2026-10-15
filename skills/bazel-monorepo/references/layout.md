# Layout and naming

Scope: where files live and what they are called, across every language in
the repository. Audience: anyone adding a file or a Bazel package. The
per-language documents (rust.md, python.md, typescript.md) apply these
rules in their own spelling and add nothing that contradicts them.

The layout serves two readers: Bazel, which wants one package per unit
with explicit dependency edges, and a person or agent searching files by
name, who wants every name to mean one thing.

## LA-1. A program owns a directory; its modules are subdirectories

A binary, program or app owns a directory under its language tree:
`rust/<binary>/`, `python/<program>/`, `typescript/<app>/`. Its module
libraries are subdirectories of that directory, one library target each,
each with its own BUILD file. The tree root (`rust/`, `python/`,
`typescript/`) is a plain namespace with an empty BUILD file.

```
rust/
  hello/
    BUILD.bazel        rust_binary "hello"
    main.rs
    app/               rust_library "hello_app"
    greeting/          rust_library "hello_greeting"
```

**Why.** The path says who owns a library. Each module builds and tests
on its own, and Bazel enforces the dependency edges that a module split
inside one crate or package would leave implicit.

**Rejected.** One large crate or package with internal modules: the edges
disappear and the unit of build and test grows to the whole program.
The cost of the chosen layout is more BUILD files; accept it, and do not
merge libraries to reduce file count.

## LA-2. No `src/` directory

Sources sit next to their BUILD file. Bazel never needed `src/`: a root
file can be any file, and a BUILD file belongs beside what it describes.
With one library per module, `src/` would hold one or two files, a
directory level that buys nothing.

## LA-3. The root file is named after its directory

The root of `rust/hello/greeting/` is `greeting.rs`; of
`python/hello/greeting/`, `greeting.py`; of `typescript/web/greeting/`,
`greeting.ts` or `greeting.tsx`. The target keeps its prefixed name
(`hello_greeting`); the directory keeps the short name, because the path
already carries the owner.

No `lib.rs`, `mod.rs`, `__init__.py` or `index.ts`. A file holding a
submodule of the root is prefixed with the root's name
(`greeting_format.rs`). A test file adds `_test` to the file it tests
(`greeting_test.rs`, `greeting_test.py`, `greeting_test.tsx`). A test
helper crate's root is `<module>_testutil.<ext>`.

**Why.** `lib.rs` and `mod.rs` are useless in an editor's file search
because every crate has one, and a tree where every file is `index.ts`
gives up readable grep output. A unique name finds the file directly.

**Rejected.** Naming the root after the full target (`hello_greeting.rs`):
every file then starts with the same prefix and the useful part of the
name comes last. A survey of large Rust repositories found prefixed crate
names to be the norm and prefixed file names not; this layout keeps the
first and drops the second.

## LA-4. No two files under one owner's tree share a name

The uniqueness rule holds per program, not repository-wide. Two programs
may each have a `config/`; editors show the parent directory when two
open files share a name, which is enough across owners. Repository-wide
uniqueness would reintroduce the prefix the moment a second program grew
its own `config/`.

## LA-5. Tests sit beside the code

Unit tests live with the code they cover: inline in Rust until they
outgrow the file, then in `<file>_test.rs`; in `<file>_test.py` and
`<file>_test.ts` from the first test on, because those languages have no
inline test module. A test that needs its own source file in Rust (an
integration suite, or a standalone test over the public API) lives in a
`tests/` subpackage of its crate. Shared test helpers live in a
`testonly` library under `testutil/`.

**Rejected.** A `tests/` directory per program for every test: a second
layout rule to hold, with no benefit that beside-the-code placement lacks.
The Rust `tests/` subpackage exists only because unit tests must compile
with the crate and other tests cannot.

## LA-6. A file splits when it gains a second concern

When a file accumulates a second concern (the tell is a second error type,
or a cluster of functions that only call each other) or its production
code approaches two hundred lines, propose a module split instead of
growing the file. A new module is cheap: a directory, a BUILD file with
two declarations, and an explicit dependency edge.

This is a checkpoint, not a hard limit. An artificial split is worse than
a long file; the rule guards against the default of appending to whichever
file is open.

## LA-7. Shared code moves up, never sideways

If a library is needed by a second program, move it up to `<tree>/<name>/`
and widen its visibility. Do not reach sideways into another program's
subdirectory. Visibility on a module library is
`//<tree>/<owner>:__subpackages__` until the move happens.

## LA-8. Entry points hold no logic

`main.rs`, the program's root `.py` file and `main.tsx` cannot be unit
tested, so they hold no logic: they parse arguments or mount the app,
call into a library, and turn an error into an exit code. Everything else
belongs in a library where a test can reach it.

## LA-9. Protos, tools and docs have their own trees

- `proto/<package path>/` holds the `.proto` files, one directory per
  proto package (proto.md).
- `tools/<language>/` holds the Bazel wrappers and lint wiring for each
  language; programs those wrappers run live inside the language tree
  they serve (`typescript/tools/`, `python/<program>/`), because that is
  where their imports resolve.
- `docs/conventions/` holds these documents; `docs/decisions/` holds the
  numbered decision records, starting with the adoption record.
