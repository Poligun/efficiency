# TypeScript

Scope: how TypeScript is laid out, built, checked and tested, so that a
reader of `typescript/` needs the same map as a reader of `rust/`.
Audience: anyone adding or changing TypeScript or JavaScript.
Prerequisites: layout.md, bazel.md. The stack is React with strict
TypeScript, Vite, type-aware ESLint, Prettier, Vitest and knip, under
Bazel through rules_js and rules_ts.

## TS-1. The layout mirrors the other trees

```
typescript/
  package.json, pnpm-lock.yaml, pnpm-workspace.yaml   one dependency set for the tree
  tsconfig.base.json     the compiler settings every app extends
  tsconfig.json          names no files; options for tools that run at the root
  eslint.config.js, prettier.config.js, knip.jsonc
  tools/                 programs the Bazel wrappers run: the Vitest launcher, the format check
  proto/                 ts_proto_library targets mirroring proto/, generated code only
  web/                   one app per directory
    BUILD.bazel, tsconfig.json, vite.config.ts, index.html, main.tsx
    app.tsx, app_test.tsx, vitest_setup.ts
    <screen>/            a subpackage per screen, each with its own BUILD file
```

- One `ts_library` per directory, each with its own BUILD file. No
  `src/`. An app's root directory holds `index.html`, the entry point,
  the Vite config and the tsconfig every deeper package names.
- `main.tsx` mounts the app and holds nothing else.
- Tests are `<file>_test.ts` and `<file>_test.tsx` beside the code, one
  `ts_test` per package. No two files under one app's tree share a name.
- Programs the wrappers run live in `typescript/tools/`, inside the tree:
  Node resolves a script's imports by walking up from the script's own
  directory, and `//typescript:node_modules` is the only place packages
  are linked. The Starlark wrappers stay in `tools/typescript/`.

## TS-2. The wrappers declare every check beside the code

```python
load("//tools/typescript:defs.bzl", "ts_library", "ts_test")

ts_library(
    name = "greeting",
    srcs = ["greeting.tsx"],
    tsconfig = "//typescript/web:tsconfig",
    visibility = ["//typescript/web:__subpackages__"],
    deps = ["//typescript:node_modules/react"],
)

ts_test(
    name = "greeting_test",
    srcs = ["greeting_test.tsx"],
    config = "//typescript/web:vite_config",
    tsconfig = "//typescript/web:tsconfig",
    deps = [":greeting", "//typescript:node_modules/vitest"],
)
```

- `ts_library` yields `<name>` (a `js_library` carrying the sources),
  `<name>_types` (a `ts_project` that type-checks and emits declarations),
  `<name>_eslint_test` and `<name>_format_test`.
- `ts_test` yields `<name>` (the Vitest run) plus the same three over the
  test files.
- `vite_app(name, srcs, deps, config)` yields `<name>` (the production
  build, a `dist/` directory) and `<name>_dev` (the dev server).

`tsconfig` is required: a symbolic macro may depend only on what its
caller hands it or what its own package sees, and an app's `ts_config` is
neither by default. `deps` names `ts_library` targets and
`//typescript:node_modules/<package>` labels, nothing else. A library
written in JavaScript (the programs under `typescript/tools/`) is a
`ts_library` with `allow_js` under a tsconfig with `allowJs` and
`checkJs`: the compiler checks it through its JSDoc types and emits its
declarations.

## TS-3. The type check emits declarations and fails the build

`<name>_types` runs `tsc` with `declaration` and `emitDeclarationOnly`. A
type error fails `bazel build //...`, as clippy does for Rust. The `.d.ts`
files are how one library's check sees another's exports: under Bazel a
check sees only its own sources and its dependencies' outputs, so a
dependency on a `ts_library` becomes a dependency on its `_types`. Vite
and Vitest transpile from the sources and never read the declarations.
Type checking runs per package, so a change in a leaf re-checks only
what depends on it.

**Rejected.** A no-emit check per package (cannot see dependencies'
sources under Bazel); one check per app (loses per-package granularity
and re-checks the whole app on every change).

## TS-4. One compiler, pinned exactly

Every entry in `package.json` is an exact version (`--save-exact`), so a
bump is a visible diff. rules_ts mirrors the TypeScript version from
`package.json`; Node and pnpm are pinned in `MODULE.bazel` and must exist
in the rulesets' mirrored tables, or the bump needs an integrity value.
Nothing is installed on the machine:

    bazel run -- @pnpm//:pnpm --dir $PWD/typescript add --save-dev --save-exact <package>@<version>
    bazel run -- @pnpm//:pnpm --dir $PWD/typescript install --lockfile-only

`pnpm-workspace.yaml` carries pnpm's settings: `allowBuilds` is empty, so
no package runs an install script, and `peerDependencyRules` names each
deliberate peer exception with the condition for dropping it.

Two pins are couplings to watch (dependencies.md): TypeScript stays on
the last JavaScript-based 6.x line until typescript-eslint supports the
native 7 compiler, because type-aware lint is the point; and Vite stays
on 7 while Vite 8's bundler fails under the Bazel sandbox.

## TS-5. Strictness lives in the base tsconfig and the ESLint config, once

`tsconfig.base.json` turns on `strict`, `noUncheckedIndexedAccess`,
`exactOptionalPropertyTypes`, `noPropertyAccessFromIndexSignature`,
`noImplicitOverride`, `noFallthroughCasesInSwitch`, `verbatimModuleSyntax`
and `isolatedModules`; an app's `tsconfig.json` extends it and adds only
its file list. `eslint.config.js` runs typescript-eslint's
`strictTypeChecked` and `stylisticTypeChecked` presets with the project
service, React hooks, accessibility, import ordering and cycle detection,
and Prettier's config last. Every rule is an error; an `eslint-disable`
comment carries a description, and an unused one is itself an error.
Default exports are forbidden except in tool configuration files.
Prettier runs on its defaults.

Three things the lint sandbox needs that a plain checkout provides for
free, each declared in `//typescript:eslint_config` or its data:
`package.json` beside the sources (the import plugin walks up to it),
`chalk` as a direct dependency (the report formatter resolves it from
ESLint's directory) and the typescript-eslint parser as a direct
dependency (the import plugin resolves it by name).

**Rejected.** Biome: faster, but without the type-aware rules.

## TS-6. Tests run under Vitest, one target per package, with coverage

`ts_test` runs Vitest through `//typescript/tools:vitest_runner` in the
app's directory with the target's files as filters, so each target runs
exactly its own files under the app's `vite.config.ts` (jsdom, Testing
Library). Under `bazel coverage` the launcher turns on the V8 provider,
writes lcov and rewrites every path to start at the workspace, which is
what the patch-coverage gate compares against the diff. The launcher
fails a run that matched fewer files than it was asked for, so a renamed
test cannot pass by running nothing. The format test is Prettier through
its API, because Prettier's command line refuses a path that is a
symbolic link and every sandboxed input is one. `vitest_setup.ts`
registers Testing Library's cleanup after every test, which Testing
Library does on its own only when it finds a global `afterEach`.

## TS-7. Vite builds and serves

`vite_app` runs `vite build` as a Bazel action whose output is `dist/`,
and `bazel run //typescript/<app>:app_dev` starts the Vite dev server,
which syncs the target's files into a scratch tree and serves them with
fast refresh. The dev server binds localhost with `strictPort`, so a busy
port fails loudly rather than moving the app to an origin a server's
allowlist would refuse. A plain `bazel run` serves the files as they were
when it started; rerun it after editing, or run under `ibazel`.

## TS-8. Editors and on-demand tools read the store through one link

`tools/setup.sh` links `typescript/node_modules` to the Bazel-built store
(`bazel-bin/typescript/node_modules`), gitignored and Bazel-ignored, so an
editor's TypeScript service and ESLint extension resolve packages and
`bazel run //typescript:knip` reads the tree. knip finds exports nothing
imports and dependencies nothing uses; it runs on demand rather than as a
test because over a test's runfiles it resolves no import. Packages only
Bazel targets consume are named in `knip.jsonc`'s `ignoreDependencies`.

## TS-9. Every string a screen shows is a message

When an app grows user-facing copy, each string is declared beside its
screen through an internationalization library with an explicit id and a
description, extracted into a committed catalog that a test keeps in step
with the sources, and formatted through `Intl` for dates, numbers and
plurals. Copy is written for the person using the screen: what happened
and what to do, never a class name, a status code or a command.

**Applies when.** The app shows copy to people. A tool or an internal
page may skip the catalog; it may not put literals in JSX once a catalog
exists.

## TS-10. The gates are the same commands as for every language

- `bazel build //...` type-checks every library and builds the app.
- `bazel test //...` fails on an ESLint finding, an unformatted file, a
  failing Vitest test and a type error in a test file.
- `bazel run //:format -- <file>` formats TypeScript, JavaScript, JSON,
  CSS and HTML through Prettier. `bazel build --config=eslint //...` lints
  the whole tree at once.
- `bazel run //:coverage_gate` counts TypeScript lines like the others.
