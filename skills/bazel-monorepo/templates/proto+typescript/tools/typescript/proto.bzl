"""TypeScript from a proto_library.

    load("//tools/typescript:proto.bzl", "ts_proto_library")

    ts_proto_library(
        name = "greeting",
        proto = "//proto/hello/v1:greeting_proto",
        deps = [],
    )

A `ts_proto_library` runs protoc with protoc-gen-es (v2, which generates the
Connect service descriptors alongside the messages) on one proto_library and
yields `<name>` (a js_library carrying the generated `_pb.js` and `_pb.d.ts`
files plus the protobuf runtime) and `<name>_types` (the same library,
under the name the ts_library wrapper looks for in a dependency, since the
generated declarations are its types). `deps` names the ts_proto_library
targets of the protos this one imports, so their generated files travel
with it.

The target must sit under typescript/proto/ in the directory that mirrors
the proto's import path: `//typescript/proto/hello/v1` for
`hello/v1/greeting.proto`. Generated JavaScript imports the
runtime by package name, which Node's resolution finds by walking up to the
nearest node_modules; only the JavaScript tree has one, so the generated
files must live inside it, and the mirrored path is what makes the relative
imports protoc-gen-es writes between generated files come out right. The
rule fails loudly when the package does not mirror the proto. protoc comes
from the proto toolchain the protobuf module registers, as for Rust.
"""

load("@aspect_rules_js//js:defs.bzl", "js_library")
load("@rules_proto//proto:defs.bzl", "ProtoInfo")

_PROTO_TOOLCHAIN_TYPE = "@rules_proto//proto:toolchain_type"
_ROOT = "typescript/proto"
_RUNTIME = "//typescript:node_modules/@bufbuild/protobuf"

# protoc searches its -I paths in the order given and takes the path within
# the directory as the package, so the longest paths come first: a virtual
# import root, then a repository root, then the output root. Adapted from
# protobuf's proto_common, which the rules_ts rule vendors the same way.
def _import_virtual_proto_path(path):
    if path.count("/") > 4:
        return "-I%s" % path
    return None

def _import_repo_proto_path(path):
    path_count = path.count("/")
    if path_count > 2 and path_count <= 4:
        return "-I%s" % path
    return None

def _import_main_output_proto_path(path):
    if path.count("/") <= 2 and path != ".":
        return "-I%s" % path
    return None

def _import_path(info, src):
    """The path protoc knows the source by: its path under the proto root."""
    root = info.proto_source_root
    if root != "." and src.path.startswith(root + "/"):
        return src.path[len(root) + 1:]
    return src.path

def _ts_proto_compile_impl(ctx):
    info = ctx.attr.proto[ProtoInfo]
    outputs = []
    for src in info.direct_sources:
        import_path = _import_path(info, src)
        proto_dir = import_path.rsplit("/", 1)[0] if "/" in import_path else ""
        expected = _ROOT + "/" + proto_dir if proto_dir else _ROOT
        if ctx.label.package != expected:
            fail("%s: a ts_proto_library for %s must be declared in //%s, the package that mirrors the proto's import path" % (ctx.label, import_path, expected))
        stem = src.basename[:-len(".proto")]
        outputs.append(ctx.actions.declare_file(stem + "_pb.js"))
        outputs.append(ctx.actions.declare_file(stem + "_pb.d.ts"))

    args = ctx.actions.args()
    args.add(ctx.executable._protoc_gen_es.path, format = "--plugin=protoc-gen-es=%s")
    args.add("--es_opt=target=js+dts")
    args.add("--es_opt=import_extension=js")
    args.add("--es_opt=keep_empty_files=true")
    args.add(ctx.bin_dir.path + "/" + _ROOT, format = "--es_out=%s")
    args.add_joined(
        "--descriptor_set_in",
        info.transitive_descriptor_sets,
        join_with = ctx.configuration.host_path_separator,
    )
    args.add_all(info.transitive_proto_path, map_each = _import_virtual_proto_path)
    args.add_all(info.transitive_proto_path, map_each = _import_repo_proto_path)
    args.add_all(info.transitive_proto_path, map_each = _import_main_output_proto_path)
    args.add("-I.")
    args.add_all(info.direct_sources)

    ctx.actions.run(
        executable = ctx.toolchains[_PROTO_TOOLCHAIN_TYPE].proto.proto_compiler,
        inputs = depset(info.direct_sources, transitive = [info.transitive_descriptor_sets]),
        outputs = outputs,
        tools = [ctx.executable._protoc_gen_es],
        arguments = [args],
        # The plugin is a js_binary; its launcher needs to know the output
        # tree, and protoc runs it as a subprocess without the rest of the
        # action's environment.
        env = {"BAZEL_BINDIR": ctx.bin_dir.path},
        use_default_shell_env = True,
        mnemonic = "ProtocGenEs",
        progress_message = "Generating TypeScript from %{label}",
    )
    return [DefaultInfo(files = depset(outputs))]

_ts_proto_compile = rule(
    implementation = _ts_proto_compile_impl,
    doc = "Runs protoc with protoc-gen-es on one proto_library; ts_proto_library wraps it.",
    attrs = {
        "proto": attr.label(
            mandatory = True,
            providers = [ProtoInfo],
            doc = "The proto_library to generate from.",
        ),
        "_protoc_gen_es": attr.label(
            default = Label("//typescript/tools:protoc_gen_es"),
            executable = True,
            cfg = "exec",
        ),
    },
    toolchains = [_PROTO_TOOLCHAIN_TYPE],
)

def _ts_proto_library_impl(name, visibility, proto, deps):
    _ts_proto_compile(
        name = name + "_gen",
        proto = proto,
    )
    js_library(
        name = name,
        srcs = [":" + name + "_gen"],
        deps = deps + [_RUNTIME],
        visibility = visibility,
    )
    native.alias(
        name = name + "_types",
        actual = ":" + name,
        visibility = visibility,
    )

ts_proto_library = macro(
    implementation = _ts_proto_library_impl,
    doc = """TypeScript generated from one proto_library, under typescript/proto.

Yields `<name>` (js_library: the generated `_pb.js` and `_pb.d.ts` files with
the protobuf runtime) and `<name>_types` (an alias of it, the name a
ts_library dependency resolves to).""",
    attrs = {
        "proto": attr.label(
            mandatory = True,
            configurable = False,
            doc = "The proto_library to generate from.",
        ),
        "deps": attr.label_list(
            default = [],
            configurable = False,
            doc = "The ts_proto_library targets of the protos this one imports.",
        ),
    },
)
