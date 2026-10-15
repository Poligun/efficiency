// The Vitest launcher behind ts_test. Bazel starts it in the
// app's directory (the package that owns vite.config.ts) with the test
// files of one target as filters, so each ts_test runs exactly its own
// files under the app's configuration. The logic lives in vitest_run.mjs
// and has its own test; this file only wires it to Vitest and the
// process, which is why it is the one file the coverage report leaves out.
//
// Under `bazel coverage` Vitest collects V8 coverage for the files the
// tests load and writes an lcov report, rewritten here so every path is
// rooted at the workspace and placed where Bazel's merger reads it.
// rules_js leaves a report the test wrote itself alone.
import console from "node:console";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

import { startVitest } from "vitest/node";

import {
  coverageOptions,
  hasFailed,
  parseArgs,
  rootReport,
} from "./vitest_run.mjs";

let parsed;
try {
  parsed = parseArgs(process.argv.slice(2));
} catch (error) {
  console.error(
    `vitest_runner: ${error instanceof Error ? error.message : String(error)}`,
  );
  process.exit(2);
}

const coverage = coverageOptions(process.env);
const vitest = await startVitest(parsed.files, {
  run: true,
  watch: false,
  coverage,
  ...(parsed.config === undefined ? {} : { config: parsed.config }),
});
await vitest.close();

const run = {
  failedTests: vitest.state.getCountOfFailedTests(),
  fileStates: vitest.state.getFiles().map((file) => file.result?.state),
  requestedFiles: parsed.files.length,
  exitCode: process.exitCode,
};
const failed = hasFailed(run);
if (failed && run.failedTests === 0) {
  // Nothing in the report says why, so say it here: Vitest's own exit
  // code, a file that did not pass, or a filter that matched nothing.
  console.error(
    `vitest_runner: failing without a failed test: ${JSON.stringify(run)}`,
  );
}

if (coverage.enabled) {
  const report = await readFile(
    path.join(coverage.reportsDirectory, "lcov.info"),
    "utf8",
  );
  await writeFile(
    coverage.outputFile,
    rootReport(report, parsed.appPackage, process.cwd()),
  );
}

process.exit(failed ? 1 : 0);
