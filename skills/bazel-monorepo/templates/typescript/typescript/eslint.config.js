// ESLint for every package under typescript/ (docs/conventions/typescript.md):
// the typescript-eslint strict and stylistic presets with type information,
// React hooks and accessibility rules, import ordering, and Prettier's
// config last so no formatting rule fights the formatter. Every rule is an
// error: the per-target lint tests fail bazel test on any finding, the way
// clippy fails the Rust build. An eslint-disable comment must carry a
// description, mirroring the reason clippy demands on an allow.
import js from "@eslint/js";
import prettier from "eslint-config-prettier";
import importX from "eslint-plugin-import-x";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: ["**/node_modules/**", "**/dist/**"],
  },
  js.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
  importX.flatConfigs.recommended,
  importX.flatConfigs.typescript,
  jsxA11y.flatConfigs.recommended,
  reactHooks.configs.flat.recommended,
  {
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    linterOptions: {
      reportUnusedDisableDirectives: "error",
    },
    rules: {
      // Every rule fires as an error, so a warning-level preset entry
      // cannot pass the gate by being ignored.
      "no-warning-comments": "off",
      "@typescript-eslint/no-non-null-assertion": "error",
      "@typescript-eslint/ban-ts-comment": [
        "error",
        {
          "ts-expect-error": "allow-with-description",
          minimumDescriptionLength: 10,
        },
      ],
      "@typescript-eslint/explicit-module-boundary-types": "error",
      "@typescript-eslint/consistent-type-imports": [
        "error",
        { prefer: "type-imports", fixStyle: "inline-type-imports" },
      ],
      "import-x/no-default-export": "error",
      "import-x/no-cycle": "error",
      // A stylesheet import is Vite's to resolve, not the module graph's:
      // the entry point imports its stylesheet for the side effect, and the
      // lint sandbox holds only the TypeScript sources.
      "import-x/no-unresolved": ["error", { ignore: ["\\.css$"] }],
      "import-x/order": [
        "error",
        {
          groups: [
            "builtin",
            "external",
            "internal",
            "parent",
            "sibling",
            "index",
          ],
          "newlines-between": "always",
          alphabetize: { order: "asc", caseInsensitive: true },
        },
      ],
    },
  },
  {
    // JavaScript sources (the programs under typescript/tools) carry their
    // types in JSDoc, which tsc verifies under checkJs; the rule that asks
    // for annotation syntax cannot see them.
    files: ["**/*.mjs"],
    rules: {
      "@typescript-eslint/explicit-module-boundary-types": "off",
    },
  },
  {
    // Tool configuration files are consumed by tools that expect a default
    // export, and they are plain JavaScript or untyped TypeScript, so the
    // type-aware rules do not apply.
    files: ["**/*.config.{js,ts}"],
    ...tseslint.configs.disableTypeChecked,
    rules: {
      // The preset's rule-disables must survive this object's own `rules`,
      // or the inherited type-aware rules run without type information.
      ...tseslint.configs.disableTypeChecked.rules,
      "import-x/no-default-export": "off",
    },
  },
  prettier,
);
