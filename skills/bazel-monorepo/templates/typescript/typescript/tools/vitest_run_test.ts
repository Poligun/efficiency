import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  coverageOptions,
  hasFailed,
  parseArgs,
  rootReport,
} from "./vitest_run.mjs";

describe("parseArgs", () => {
  it("separates the package from the files", () => {
    expect(
      parseArgs([
        "--package",
        "typescript/web",
        "app_test.tsx",
        "greeting/greeting_test.tsx",
      ]),
    ).toEqual({
      appPackage: "typescript/web",
      config: undefined,
      files: ["app_test.tsx", "greeting/greeting_test.tsx"],
    });
  });

  it("refuses a config flag without a value", () => {
    expect(() =>
      parseArgs(["--package", "typescript/web", "a_test.tsx", "--config"]),
    ).toThrow("--config requires a value");
  });

  it("requires the package flag with a value", () => {
    expect(() => parseArgs(["app_test.tsx"])).toThrow("--package");
    expect(() => parseArgs(["app_test.tsx", "--package"])).toThrow("--package");
  });

  it("requires at least one file", () => {
    expect(() => parseArgs(["--package", "typescript/web"])).toThrow(
      "test file",
    );
  });
});

describe("coverageOptions", () => {
  it("is off unless Bazel asks for coverage", () => {
    expect(coverageOptions({})).toEqual({ enabled: false });
    expect(coverageOptions({ COVERAGE_DIR: "/cov" })).toEqual({
      enabled: false,
    });
  });

  it("writes lcov under the coverage directory", () => {
    const options = coverageOptions({
      COVERAGE_DIR: "/cov",
      COVERAGE_OUTPUT_FILE: "/cov/out.dat",
    });
    expect(options).toMatchObject({
      enabled: true,
      provider: "v8",
      reportsDirectory: path.join("/cov", "vitest"),
      outputFile: "/cov/out.dat",
    });
  });
});

describe("rootReport", () => {
  it("roots relative and absolute paths at the workspace", () => {
    const report = [
      "TN:",
      "SF:app.tsx",
      "DA:1,1",
      "end_of_record",
      "SF:/work/typescript/web/greeting/greeting.tsx",
      "end_of_record",
      "",
    ].join("\n");
    expect(rootReport(report, "typescript/web", "/work/typescript/web")).toBe(
      [
        "TN:",
        "SF:typescript/web/app.tsx",
        "DA:1,1",
        "end_of_record",
        "SF:typescript/web/greeting/greeting.tsx",
        "end_of_record",
        "",
      ].join("\n"),
    );
  });
});

describe("hasFailed", () => {
  const passing = {
    failedTests: 0,
    fileStates: ["pass", "pass"],
    requestedFiles: 2,
    exitCode: undefined,
  };

  it("passes a clean run", () => {
    expect(hasFailed(passing)).toBe(false);
    expect(hasFailed({ ...passing, exitCode: 0 })).toBe(false);
  });

  it("fails on a failed test or file", () => {
    expect(hasFailed({ ...passing, failedTests: 1 })).toBe(true);
    expect(hasFailed({ ...passing, fileStates: ["pass", "fail"] })).toBe(true);
  });

  it("fails when Vitest set a nonzero exit code", () => {
    expect(hasFailed({ ...passing, exitCode: 1 })).toBe(true);
  });

  it("fails when a filter matched nothing", () => {
    expect(hasFailed({ ...passing, fileStates: ["pass"] })).toBe(true);
  });
});
