# Review: `chore/bump-deps` (gatekeeper)

**Verdict: don't merge as-is.** The diff is 7 lines across `Cargo.toml` / `Cargo.lock` and reads like routine housekeeping, but one of those lines (`reqwest 0.12.4 → 0.13.0`) is a breaking `0.x` bump that swaps the crate's entire TLS backend, and the lockfile in this branch is hand-edited fiction that doesn't survive a CI-style build.

The whole diff:

```
serde   1.0.203 → 1.0.210
tokio   1.38.0  → 1.41.1
reqwest 0.12.4  → 0.13.0     <-- breaking
tracing 0.1.40  → 0.1.41
```

No source files changed.

---

## Blockers

### 1. `reqwest 0.13` silently replaces the TLS stack (native-tls → rustls + aws-lc-rs)

This is the finding that matters, and it is invisible in the diff. The `default-tls` feature was redefined between the two versions:

```toml
# reqwest 0.12.28
default-tls = ["dep:hyper-tls", "dep:native-tls-crate", "__tls", "dep:tokio-native-tls"]

# reqwest 0.13.4
default-tls = ["rustls"]
```

`default` still contains `default-tls` in both, so nothing in `Cargo.toml` signals the change — you just get a different cryptography library. I confirmed the resolved trees differ exactly as expected:

| | main (reqwest 0.12) | branch (reqwest 0.13) |
|---|---|---|
| TLS | `hyper-tls`, `native-tls`, `tokio-native-tls`, `security-framework` | `hyper-rustls`, `rustls 0.23`, `tokio-rustls`, `rustls-platform-verifier` |
| Crypto provider | system (SecureTransport / OpenSSL / schannel) | `aws-lc-rs` + `aws-lc-sys` (vendored C/asm) |
| Packages in tree | 178 | 191 |

Why this is a merge blocker for *this* service specifically: `gatekeeper` reads an `upstream_url` from config (`src/config.rs:6`) and exists to talk to it. Certificate verification is its core behavior, and rustls is materially stricter than native-tls — it rejects SHA-1 signatures, certificates with no SAN (CN-only), and various legacy/corporate-MITM chains that OpenSSL and macOS SecureTransport accept. If any upstream or egress proxy in your environment presents such a certificate, this bump turns a working deployment into TLS handshake failures at runtime, not at build time.

Two side effects that also need a decision:

- **New build-toolchain requirement.** `aws-lc-sys` compiles vendored C and assembly. Its build-dependencies are `cc`, `cmake`, `fs_extra`, `dunce` (plus optional `bindgen`), and all of these are new to the branch's lock — main's tree has only `cc`. Any build image without `cmake` and a C compiler (and `nasm` on Windows) will fail to build this branch. There is no Dockerfile or CI config in the repo, so I couldn't verify your builders have them.
- **New license surface.** `aws-lc-sys 0.41.0` declares `ISC AND (Apache-2.0 OR ISC) AND Apache-2.0 AND MIT AND BSD-3-Clause AND (Apache-2.0 OR ISC OR MIT) AND (Apache-2.0 OR ISC OR MIT-0)`. If you run license scanning or have an approved-dependency list, this needs to clear it before merge.

**Options:** either (a) adopt rustls deliberately, after testing a real handshake against production upstreams, or (b) keep the current behavior explicitly:

```toml
reqwest = { version = "0.13", default-features = false, features = ["native-tls", "charset", "http2", "system-proxy"] }
```

(`native-tls` is still an available opt-in feature in 0.13 — I verified it exists.)

### 2. MSRV jumps from 1.64 to ~1.86

`reqwest`'s own declared `rust-version` goes `1.64.0` → `1.85.0`. Pulling the full branch tree, the effective floor is higher still: `rustls-platform-verifier 0.7.0` needs 1.85, and `idna_adapter` / the `icu_*` crates (reached via `url` → `idna`, on every host target) need 1.86.

There is no `rust-toolchain.toml` and no `.github/` in this repo, so I can't tell what your CI and release builds pin. If anything is below 1.86, this branch does not compile there. Confirm before merging, and consider committing a `rust-toolchain.toml` so this is checked rather than discovered.

### 3. `Cargo.lock` is not a real lockfile, and this branch hand-edited it

A standard CI invocation fails immediately:

```
$ cargo check --locked
error: cannot update the lock file ... because --locked was passed to prevent this
```

The committed lock has 3 package entries, no checksums, and no root package. When cargo is allowed to resolve, it discards it entirely — `Locking 190 packages to latest compatible versions` — and lands on **reqwest 0.13.4, serde 1.0.229, tokio 1.53.1**, none of which are the versions the lock claims. So the branch does not pin what it says it pins.

Three pieces of evidence that the lock was edited by hand rather than produced by `cargo update`:

- The branch bumps `tracing 0.1.40 → 0.1.41` in `Cargo.toml`, but `tracing` has no entry in `Cargo.lock` at all and no tracing line changed.
- Replacing the entire TLS stack (hyper-tls → hyper-rustls, plus aws-lc-sys/cmake/rustls) changed **zero** transitive entries. A genuine relock would have touched dozens.
- Only the three version strings that also appear in `Cargo.toml` were edited — exactly the pattern of a find-and-replace.

This is pre-existing (main fails `--locked` too), so it isn't a regression. But this is a dependency PR, and a dependency PR whose lockfile is decorative gives false confidence about exactly the thing it's supposed to control. Fix it here: run a real `cargo update -p …` and commit the actual output.

---

## Should fix

### 4. `reqwest` is declared but never used

`grep` across `src/` finds zero references to `reqwest`. The only external crates the code actually touches are `tokio` (`src/main.rs:3`), `tracing` (`src/main.rs:7`), `tracing_subscriber` (`src/main.rs:5`), `serde` (`src/config.rs:1`) and `toml` (`src/config.rs:12`).

So this branch takes on a breaking major bump, a new vendored crypto stack, a C build-toolchain requirement, an MSRV jump and a new license surface — for a dependency no code calls yet. The cheapest correct move is to drop `reqwest` from `Cargo.toml` until the proxy path is written, and adopt 0.13 deliberately at that point with the TLS decision made consciously.

If you keep it, note one API change for whoever wires it up: **0.13 adds a `form` feature that did not exist in 0.12**, and it's not in `default`. Code calling `RequestBuilder::form()` will not compile without `features = ["form"]`. `json` remains opt-in as before.

### 5. The crate doesn't compile — on this branch or on main

```
error[E0433]: cannot find module or crate `tracing_subscriber`  --> src/main.rs:5:5
error[E0433]: cannot find module or crate `toml`                --> src/config.rs:12:12
```

Both are used in source but missing from `[dependencies]`. This is pre-existing rather than introduced here, so it's not a reason to block the *diff* — but it does mean nobody built this branch before proposing the merge, which is worth knowing given findings 1–3. Add:

```toml
toml = "0.9"
tracing-subscriber = "0.3"
```

---

## Low risk — no action needed

`serde 1.0.203 → 1.0.210`, `tokio 1.38.0 → 1.41.1`, and `tracing 0.1.40 → 0.1.41` are all semver-compatible bumps within a stable `1.x` line. No API breakage, nothing to review. These are the only three changes in the diff that are actually routine.

---

## Suggested path to merge

1. Split the PR. Land serde / tokio / tracing on their own — that part is trivially safe.
2. Handle `reqwest 0.13` separately: either drop the unused dep, or make the native-tls-vs-rustls call explicitly and test a real handshake against your actual upstreams.
3. Regenerate `Cargo.lock` with a real `cargo update` and commit the genuine output; add `--locked` to CI so a hand-edited lock can never merge again.
4. Confirm the build toolchain is ≥ 1.86 and has `cmake` + a C compiler if you go the rustls route; commit a `rust-toolchain.toml`.
5. Add the two missing dependencies so the crate builds at all.

---

## How I verified this

Everything above was checked against real resolution, not from memory. The fixture repo was left untouched — all builds ran against copies in a scratch directory.

- `git diff main...chore/bump-deps` — full diff is `Cargo.toml` + `Cargo.lock` only.
- `cargo metadata` / `cargo tree -e normal` on both main and the branch, to diff the resolved TLS stacks and package counts.
- `cargo check --locked` on both branches, to show the lockfile is unusable.
- `cargo check` on the branch, producing the two E0433 errors.
- Read `[features]` and `rust-version` directly from the vendored `reqwest-0.12.28` and `reqwest-0.13.4` sources in the local registry cache, plus `aws-lc-sys-0.41.0`'s license and build-dependencies.

Files referenced: `/Users/yuhanzhao/GitHub/efficiency/skills/deep-code-review-workspace/fixtures/dep-bump-repo/Cargo.toml`, `/Users/yuhanzhao/GitHub/efficiency/skills/deep-code-review-workspace/fixtures/dep-bump-repo/Cargo.lock`, `/Users/yuhanzhao/GitHub/efficiency/skills/deep-code-review-workspace/fixtures/dep-bump-repo/src/main.rs`, `/Users/yuhanzhao/GitHub/efficiency/skills/deep-code-review-workspace/fixtures/dep-bump-repo/src/config.rs`.
