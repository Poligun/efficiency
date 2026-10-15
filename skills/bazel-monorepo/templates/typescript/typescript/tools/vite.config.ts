// Vitest configuration for the tools' own tests: Node, no DOM.
// Coverage includes the .mjs programs, which the tests import in-process.
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["**/*_test.ts"],
    coverage: {
      provider: "v8",
      include: ["**/*.mjs"],
      exclude: ["vitest_runner.mjs"],
    },
  },
});
