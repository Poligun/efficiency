// The format test behind ts_library and ts_test: checks that
// each file is exactly what Prettier would produce, through Prettier's API
// rather than its command line. The command line refuses a path that is a
// symbolic link, and every input of a sandboxed test is one; the API takes
// file contents, so the link is followed like any other read. The files
// arrive as workspace-relative paths, which is also how the fix hint prints
// them.
import console from "node:console";
import { readFile } from "node:fs/promises";
import process from "node:process";
import { pathToFileURL } from "node:url";

import { check } from "prettier";

const args = process.argv.slice(2);
const configFlag = args.indexOf("--config");
if (configFlag === -1 || configFlag + 1 >= args.length) {
  console.error(
    "prettier_check: --config <prettier config module> is required",
  );
  process.exit(2);
}
const configPath = args[configFlag + 1] ?? "";
const files = args.filter((_, i) => i !== configFlag && i !== configFlag + 1);
const loaded = /** @type {unknown} */ (
  await import(pathToFileURL(configPath).href)
);
if (typeof loaded !== "object" || loaded === null || !("default" in loaded)) {
  console.error(`prettier_check: ${configPath} has no default export`);
  process.exit(2);
}
const options = /** @type {import("prettier").Options} */ (loaded.default);

const unformatted = [];
for (const file of files) {
  const source = await readFile(file, "utf8");
  const formatted = await check(source, { ...options, filepath: file });
  if (!formatted) {
    unformatted.push(file);
  }
}

if (unformatted.length > 0) {
  console.error("prettier_check: not formatted:");
  for (const file of unformatted) {
    console.error(`  ${file}`);
  }
  console.error(`Fix with: bazel run //:format -- ${unformatted.join(" ")}`);
  process.exit(1);
}
