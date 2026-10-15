// The logic behind the Vitest launcher (vitest_runner.mjs), kept apart
// from the entry point so a unit test can drive it without starting
// Vitest: the argument contract, the coverage options Bazel's environment
// asks for, the lcov rewrite that roots paths at the workspace, and the
// verdict that turns Vitest's state into an exit code.
import path from "node:path";

/**
 * Parses the launcher's arguments: `--package <workspace path of the app>`,
 * an optional `--config <vite config relative to the app>` (a second Vite
 * project of the app; its vite.config.ts otherwise),
 * then the test files, named relative to the app's directory.
 * @param {string[]} args
 * @returns {{ appPackage: string, config: string | undefined, files: string[] }}
 */
export function parseArgs(args) {
  const taken = new Set();
  /**
   * The value after a flag, `undefined` when the flag is absent; a flag
   * with nothing after it is an error, never a silent default.
   * @param {string} name
   * @param {string} value
   */
  const option = (name, value) => {
    const flag = args.indexOf(name);
    if (flag === -1) {
      return undefined;
    }
    const given = args[flag + 1];
    if (given === undefined || given.startsWith("--")) {
      throw new Error(`${name} requires a value: ${name} <${value}>`);
    }
    taken.add(flag);
    taken.add(flag + 1);
    return given;
  };
  const appPackage = option("--package", "workspace path of the app");
  if (appPackage === undefined) {
    throw new Error("--package <workspace path of the app> is required");
  }
  const config = option("--config", "vite config relative to the app");
  const files = args.filter((_, i) => !taken.has(i));
  if (files.length === 0) {
    throw new Error("at least one test file is required");
  }
  return { appPackage, config, files };
}

/**
 * The coverage options for one run. Bazel sets COVERAGE_OUTPUT_FILE and
 * COVERAGE_DIR under `bazel coverage` and nothing otherwise.
 * @param {NodeJS.ProcessEnv} env
 * @returns {{ enabled: false } | { enabled: true, provider: "v8", reporter: [["lcovonly", { file: string }]], reportsDirectory: string, reportOnFailure: true, outputFile: string }}
 */
export function coverageOptions(env) {
  const outputFile = env["COVERAGE_OUTPUT_FILE"];
  const coverageDir = env["COVERAGE_DIR"];
  if (!outputFile || !coverageDir) {
    return { enabled: false };
  }
  return {
    enabled: true,
    provider: "v8",
    reporter: [["lcovonly", { file: "lcov.info" }]],
    reportsDirectory: path.join(coverageDir, "vitest"),
    reportOnFailure: true,
    outputFile,
  };
}

/**
 * Rewrites every SF: line of an lcov report so the path starts at the
 * workspace (typescript/web/app.tsx, not app.tsx), the form the
 * patch-coverage gate compares against the git diff. Vitest names files
 * relative to its root or absolutely; both become workspace-rooted.
 * @param {string} report
 * @param {string} appPackage
 * @param {string} cwd
 * @returns {string}
 */
export function rootReport(report, appPackage, cwd) {
  return report.replace(
    /^SF:(.*)$/gm,
    (/** @type {string} */ _, /** @type {string} */ file) => {
      const relative = path.isAbsolute(file) ? path.relative(cwd, file) : file;
      const posix = relative.split(path.sep).join(path.posix.sep);
      return `SF:${path.posix.join(appPackage, posix)}`;
    },
  );
}

/**
 * Whether the run failed. Vitest's own exit code carries what task state
 * does not: an unhandled error after the tests, or no file matching the
 * filters. A run that matched fewer files than it was asked for is a
 * failure as well, so a renamed test cannot pass by running nothing.
 * @param {{ failedTests: number, fileStates: (string | undefined)[], requestedFiles: number, exitCode: number | string | null | undefined }} run
 * @returns {boolean}
 */
export function hasFailed(run) {
  return (
    run.failedTests > 0 ||
    run.fileStates.some((state) => state === "fail") ||
    run.fileStates.length < run.requestedFiles ||
    (run.exitCode !== undefined && run.exitCode !== null && run.exitCode !== 0)
  );
}
