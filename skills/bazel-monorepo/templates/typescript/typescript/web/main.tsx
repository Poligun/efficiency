// The entry point: mounts the app into the page Vite serves and holds
// nothing else, the way a Rust main.rs stays logic-free. The types
// reference is what declares import.meta.env and the CSS import, and it is
// scoped to this file so only this library depends on Vite's types.
/// <reference types="vite/client" />
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./app.css";
import { App } from "./app";

const container = document.getElementById("root");
if (container === null) {
  throw new Error("index.html has no #root element");
}
createRoot(container).render(
  <StrictMode>
    <App name="world" />
  </StrictMode>,
);
