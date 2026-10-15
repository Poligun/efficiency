import { toBinary } from "@bufbuild/protobuf";
import { describe, expect, it } from "vitest";

import { GreetRequestSchema } from "../../proto/hello/v1/greeting_pb.js";

import { greetRequest } from "./api";

describe("greetRequest", () => {
  it("carries the trimmed name", () => {
    expect(greetRequest("  Ada ").name).toBe("Ada");
  });

  it("serializes through the generated schema", () => {
    const bytes = toBinary(GreetRequestSchema, greetRequest("Ada"));
    expect(bytes.length).toBeGreaterThan(0);
  });
});
