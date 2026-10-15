import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./app";

describe("App", () => {
  it("greets the name it is given", () => {
    render(<App name="Ada" />);
    expect(screen.getByRole("heading", { name: "Hello, Ada!" })).toBeDefined();
  });
});
