// The request messages the app sends, built from the generated schema.
// Generated code lives under typescript/proto and is imported by relative
// path; it is never checked in.
import { create } from "@bufbuild/protobuf";

import {
  type GreetRequest,
  GreetRequestSchema,
} from "../../proto/hello/v1/greeting_pb.js";

export function greetRequest(name: string): GreetRequest {
  return create(GreetRequestSchema, { name: name.trim() });
}
