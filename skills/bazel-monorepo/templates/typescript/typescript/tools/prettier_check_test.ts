import console from "node:console";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import process from "node:process";

import { afterEach, describe, expect, it, vi } from "vitest";

// Vitest runs in this directory; the shared Prettier config sits one up.
const CONFIG = path.resolve("../prettier.config.js");

interface Run {
  exit: number | string | null | undefined;
  stderr: string[];
}

// The checker is a program: it reads argv and calls process.exit. Each run
// imports a fresh copy with argv set, exit turned into a thrown sentinel so
// the program stops where it would have exited, and stderr captured. The
// program writes through Node's own console (node:console), not the one
// Vitest patches onto the global scope, so the spy goes on that object.
async function run(args: string[]): Promise<Run> {
  vi.resetModules();
  const stderr: string[] = [];
  vi.spyOn(console, "error").mockImplementation((...parts: unknown[]) => {
    stderr.push(parts.map(String).join(" "));
  });
  const result: Run = { exit: undefined, stderr };
  vi.spyOn(process, "exit").mockImplementation((code) => {
    result.exit = code;
    throw new Error("exit");
  });
  const argv = process.argv;
  process.argv = [argv[0] ?? "node", "prettier_check.mjs", ...args];
  try {
    await import("./prettier_check.mjs");
  } catch (error) {
    if (!(error instanceof Error && error.message === "exit")) {
      throw error;
    }
  } finally {
    process.argv = argv;
  }
  return result;
}

// Bazel gives a test its own scratch directory and removes it after the
// run; outside Bazel the system one serves, and each test removes what it
// wrote.
const scratch = process.env["TEST_TMPDIR"] ?? tmpdir();
const written: string[] = [];

async function tempFile(name: string, content: string): Promise<string> {
  const dir = await mkdtemp(path.join(scratch, "prettier_check-"));
  written.push(dir);
  const file = path.join(dir, name);
  await writeFile(file, content);
  return file;
}

afterEach(async () => {
  vi.restoreAllMocks();
  await Promise.all(
    written.splice(0).map((dir) => rm(dir, { recursive: true, force: true })),
  );
});

describe("prettier_check", () => {
  it("requires --config", async () => {
    const result = await run([]);
    expect(result.exit).toBe(2);
    expect(result.stderr.join("\n")).toContain("--config");
  });

  it("refuses a config module without a default export", async () => {
    const config = await tempFile("config.mjs", "export const answer = 42;\n");
    const result = await run(["--config", config, config]);
    expect(result.exit).toBe(2);
    expect(result.stderr.join("\n")).toContain("no default export");
  });

  it("passes a formatted file silently", async () => {
    const file = await tempFile("ok.ts", "const answer = 42;\n");
    const result = await run(["--config", CONFIG, file]);
    expect(result.exit).toBeUndefined();
    expect(result.stderr).toEqual([]);
  });

  it("names an unformatted file and the command that fixes it", async () => {
    const file = await tempFile("bad.ts", "const   answer=42\n");
    const result = await run(["--config", CONFIG, file]);
    expect(result.exit).toBe(1);
    const output = result.stderr.join("\n");
    expect(output).toContain("not formatted");
    expect(output).toContain(file);
    expect(output).toContain(`bazel run //:format -- ${file}`);
  });
});
