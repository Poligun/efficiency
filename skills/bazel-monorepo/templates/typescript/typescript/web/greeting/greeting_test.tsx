import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { greet, Greeting } from "./greeting";

describe("greet", () => {
  it("names the person", () => {
    expect(greet("Ada")).toBe("Hello, Ada!");
  });

  it("trims whitespace", () => {
    expect(greet("  Ada ")).toBe("Hello, Ada!");
  });

  it("refuses an empty name", () => {
    expect(() => greet("   ")).toThrow("a name is required");
  });
});

describe("Greeting", () => {
  it("renders the greeting as the heading", () => {
    render(<Greeting name="Ada" />);
    expect(screen.getByRole("heading", { name: "Hello, Ada!" })).toBeDefined();
  });
});
