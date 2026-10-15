// Vite builds and serves the app, and Vitest reads the test section. The
// root is this directory: index.html sits beside the sources, with no src/
// (docs/conventions/typescript.md). Tests are the *_test.ts and *_test.tsx
// files beside the code they cover, the same rule as Rust and Python.
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    // A busy port must fail loudly here rather than move the app to an
    // origin a server's allowlist would then refuse.
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  test: {
    environment: "jsdom",
    include: ["**/*_test.{ts,tsx}"],
    // Resolved against this directory, Vitest's root.
    setupFiles: ["vitest_setup.ts"],
    coverage: {
      provider: "v8",
      include: ["**/*.{ts,tsx}"],
      exclude: ["**/*_test.{ts,tsx}", "vite.config.ts", "vitest_setup.ts"],
    },
  },
});
