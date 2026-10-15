// The shell: composes the screens. Dependencies arrive as props from the
// entry point, so a test renders the shell with whatever it needs.
import type { JSX } from "react";

import { Greeting } from "./greeting/greeting";

export function App({ name }: { name: string }): JSX.Element {
  return (
    <main>
      <Greeting name={name} />
    </main>
  );
}
