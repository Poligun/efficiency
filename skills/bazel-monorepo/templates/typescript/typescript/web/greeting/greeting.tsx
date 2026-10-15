// The greeting screen and the function behind it. The function is exported
// on its own so the logic is testable without rendering.
import type { JSX } from "react";

export function greet(name: string): string {
  const trimmed = name.trim();
  if (trimmed === "") {
    throw new Error("a name is required");
  }
  return `Hello, ${trimmed}!`;
}

export function Greeting({ name }: { name: string }): JSX.Element {
  return <h1>{greet(name)}</h1>;
}
