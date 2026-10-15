# Protocol buffers and gRPC

Scope: where `.proto` files live, how code is generated from them in each
language, and the contract style a new API follows. Audience: anyone
adding a proto package, an RPC or a generated-code consumer.
Prerequisites: layout.md, bazel.md, and rust.md or typescript.md for the
consuming language.

## PB-1. Protos live in `proto/`, at their package path

```
proto/
  hello/
    v1/
      BUILD.bazel      proto_library, and the Rust codegen targets
      greeting.proto   package hello.v1
```

Protos are language-neutral contracts, so they do not live under a
language tree. The directory below `proto/` matches the proto package, and
`strip_import_prefix = "/proto"` makes the import path match too: another
proto writes `import "hello/v1/greeting.proto";`, the same string every
language ecosystem uses. Packages are versioned (`v1`) from the first
file.

## PB-2. Code is generated at build time and never checked in

The `.proto` file is the only source of truth. Each language's codegen
target runs protoc on every build; protoc itself arrives prebuilt through
the protobuf module. Generated targets are exempt from the wrapper rule
(bazel.md BZ-4): they use the codegen rules directly and get no lint or
format target, because lint targets exist to catch mistakes in code we
write. Generated Rust provides no `CrateInfo`, so even the whole-tree
aspects skip it.

## PB-3. Rust codegen sits beside the `proto_library`, on the repository's own toolchain

`rust_prost_library` (from rules_rust_prost) runs protoc with the prost
and tonic plugins. The generated crate is named after the `proto_library`
target: `greeting_proto` yields `greeting_proto::hello::v1::...`. The
prost toolchain is the repository's own, in `tools/prost/BUILD.bazel`,
pointing at `@crates`, and is registered in `MODULE.bazel` so it outranks
the default.

**Why.** rules_rust_prost's default toolchain is wired to its own internal
crate repositories. Code generated against it uses a different instance
of the tonic crate than the handlers do, and the two sets of types do not
unify; the symptom is baffling trait-mismatch errors on correct-looking
code.

**The tonic set.** tonic, prost, prost-types, protoc-gen-prost and
protoc-gen-tonic move together, to the versions rules_rust's prost
toolchain supports; the protoc plugins generate code for one specific
tonic API. Do not bump one of them alone. As of this writing the set is
tonic 0.12 and prost 0.13, because tonic 0.14 moved the prost codec into
a separate crate that `rust_prost_toolchain` does not yet support; the
trigger for moving is a rules_rust release that does (dependencies.md).

**Well-known types** map to `prost-types`: the toolchain sets
`compile_well_known_types = False`, so a `google.protobuf.Timestamp` field
is `::prost_types::Timestamp` and `SystemTime::into()` fills it. The
`prost-types` crate keeps its default features, which carry those
conversions. Two dead ends: with WKT compilation left on, the well-known
types become generated crates with no conversion impls; and an
`extern_path` option cannot fix that, because the aspect's per-type paths
win by exact match and passing the same key is a duplicate-path error.

**Reflection** is served from a `proto_descriptor_set` (from the protobuf
module's `bazel/proto_descriptor_set.bzl`; rules_proto's copy is
unmaintained) embedded with `include_bytes!` through a `rustc_env` entry
that `$(execpath ...)` expands to an absolute path. A gRPC client can then
discover the API without proto files on hand.

## PB-4. TypeScript codegen lives under `typescript/proto/`, mirroring the import path

`ts_proto_library` (`tools/typescript/proto.bzl`) runs protoc with
protoc-gen-es on one `proto_library` and yields a `js_library` of the
generated `_pb.js` and `_pb.d.ts` files plus the protobuf runtime, and
the `_types` alias a `ts_library` dependency resolves to. The target sits
in the package that mirrors the proto's import path:
`//typescript/proto/hello/v1:greeting` for `hello/v1/greeting.proto`; the
rule fails a target declared anywhere else. App code imports generated
code by relative path (`../../proto/hello/v1/greeting_pb.js`).

**Why.** Generated JavaScript imports its runtime by package name, and
every tool in the JavaScript toolchain finds a package by walking up to
the nearest `node_modules`. The only one is the Bazel-built store under
`typescript/`, so code generated beside the `proto_library` could import
nothing. The mirrored path is what makes the relative imports the plugin
writes between generated files come out right.

## PB-5. Generated types stop at the edge

Internal code speaks the domain's own model types. Conversions between
wire types and model types are free functions in the edge crate or
package (the orphan rule forbids `From` impls between two foreign types),
and the generated target's visibility narrows to the edge package once a
consumer exists.

## PB-6. Contract style

- Optional enum fields carry the proto3 `optional` keyword, so
  optionality shows in the schema and absence is the only way to omit
  them. The zero `UNSPECIFIED` value is never valid on the wire: typed
  accessors collapse unrecognized values to zero, so zero must stay the
  "unset or unparsable" bucket, and a server rejects it in required and
  optional fields alike.
- A state machine in a response is a `oneof` of per-state messages, not
  a state enum beside fields that only apply sometimes. Fields live with
  the state they belong to, and an unset `oneof` tells an old client it
  is seeing a state added later.
- Time ranges use a shared interval type (start inclusive, end exclusive)
  from a common types package rather than two bare timestamps.
- A naming wart to expect in Rust: prost cannot strip an enum prefix when
  the value name continues with a digit, so `KIND_1_MIN` generates
  `Kind::Kind1Min`. Acceptable; only the edge sees it.
- A new RPC on an existing service touches the proto file and the service
  implementation. A new proto package is a new directory under `proto/`
  with the same targets.

## PB-7. The runtime and shutdown are explicit

The serve loop runs on a runtime the app crate builds (rust.md RS-14):
bind first, then serve with the signal handlers installed and in-flight
requests drained on shutdown. A health service and reflection are served
beside the API, each switchable off in the configuration.

**Applies when.** The repository serves the API. The bootstrap templates
stop at the codegen and a handler with a unit test; they ship no server
binary, so this rule describes the shape the first server takes, not a
target that exists on day one.
