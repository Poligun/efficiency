# Testing

Scope: what a test may depend on, where it lives, and how a test that
needs a real service gets one. Audience: anyone writing or reviewing a
test in any language. Prerequisites: layout.md; the per-language
documents hold the target shapes.

## TE-1. Unit tests live with the code and run in the wildcard gate

Every library has its tests beside it (layout.md LA-5), and
`bazel test //...` runs all of them. A test that cannot run in the
wildcard gate is the exception that needs a reason: a `manual` tag, or a
`target_compatible_with` constraint that names the hosts it can run on.

## TE-2. Tests do not touch the environment or the filesystem

Write the code so the sources of external state are arguments. A loader
that reads a file and the environment keeps its layering logic in a
private function that takes its sources as parameters; tests call that
function with an in-memory document and an explicit variable map.

**Why.** It avoids runfiles paths for test data, and it avoids mutating
the process environment, which races because Rust runs tests as threads
in one process. The same shape makes Python tests independent of the
machine they run on.

The one allowance is a scratch directory (`TEST_TMPDIR`, pytest's
`tmp_path`) for code whose job is writing files, where the write is the
behavior under test.

## TE-3. Different behavior earns a seam; different data does not

A test that needs different *behavior* from a dependency (a clock that
stands still, a process runner that records instead of spawning) gets a
seam: a small trait or a callable the production code is handed. A test
that needs different *data* does not; it gets the producing end of the
real type (the publisher side of a channel, a builder) and feeds the data
through it. No mocking framework patches internals.

Shared helpers (the fixed clock, the recording runner) live in a
`testonly` library under `testutil/`, so a production target cannot
depend on them; Bazel refuses the edge.

## TE-4. A test that needs a service starts its own

A test that needs a database, a queue or another server starts its own
instance: `MODULE.bazel` pins the service's release archive with the
publisher's checksum for each supported host, a `tools/<service>` package
selects the host's archive, and a handle in the testutil library starts
the server on free loopback ports with its data under the scratch
directory, waits for readiness, hands out endpoints, streams the server's
output into the test's undeclared outputs, and stops the server when the
handle drops. One instance per test function; no shared dev stack, no
container, no `--test-threads=1`, no `exclusive` tag, no table-clearing
helper.

Rules the handle holds:

- The handle exists from the moment the server is spawned, so a panic
  anywhere after that still stops it, and it removes its directory on
  drop. The handle must outlive every connection taken from it.
- Stop through the server's own stop command where one exists; a kill
  is the last resort, because some servers leak system resources when
  killed.
- Listen on TCP, not a Unix socket: a sandbox's scratch path can exceed
  the socket path limit on macOS.
- The readiness probe fails fast when the child exits, is bounded per
  attempt, and verifies it reached its own server (by asking the server
  for a setting only this instance has). An exit before readiness or a
  foreign answer counts as a lost port race and retries on fresh ports,
  a bounded number of times, with the last reason in the final failure.

A store-backed test declares `target_compatible_with` from the service
package's host rule, so on a host with no pinned archive
`bazel test //...` skips it with Bazel's incompatible-target note instead
of failing analysis. Adding a host means an archive in `MODULE.bazel`, a
`config_setting` and a branch in each alias.

**Why.** A shared dev stack cannot be reset by a test when it also serves
a local run, and the coverage gate cannot see suites that run only when
someone started the stack. Fresh instances cost well under a second for
a store that can initialize once per process into a template each test
copies, and a second or two otherwise.

**Rejected.** Containers: the fallback if a service could not run from an
archive; both services tried could. A suite-wide server: a Rust test
binary has no global teardown.

**Applies when.** The repository has a test that needs a real service.
Until then this rule is the design to reach for, not a target to build.

## TE-5. Coverage is measured per change, at 95 percent

Every test target writes lcov under `bazel coverage` (rules_rust does,
rules_py's pytest entry point does, the Vitest launcher does), the
`.bazelrc` filter instruments only the first-party trees, and the
patch-coverage gate (gates.md GA-3) judges the lines a change touched.
Untestable wiring concentrates in the entry points, which is the shape a
file-level exclusion can handle if one is ever earned.

## TE-6. A test asserts on the plan, not on the world

For code that runs other programs, the test asserts on the exact argument
lists the code planned, through the recording runner, and never spawns
the real tool. For code that talks to a service, the test uses the
instance it started (TE-4) and asserts on observable state, never on log
text.
