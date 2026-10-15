// Runs before every test file of this app (vite.config.ts names it).
// Testing Library unmounts what a test rendered only when it finds a
// global afterEach at import time; Vitest exposes none unless asked, so
// the cleanup is registered here explicitly, and a second render in one
// file starts from an empty document.
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});
