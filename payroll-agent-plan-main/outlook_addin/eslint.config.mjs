// Picked up by office-addin-lint in place of its default config (ESLint 9 flat config).
import officeAddins from "eslint-plugin-office-addins";
import tsParser from "@typescript-eslint/parser";
import globals from "globals";

export default [
  { ignores: ["dist/**", "node_modules/**"] },
  ...officeAddins.configs.react,
  {
    plugins: { "office-addins": officeAddins },
    languageOptions: {
      parser: tsParser,
      globals: { ...globals.browser, ...globals.es2021, Office: "readonly" },
    },
  },
  {
    files: ["webpack.config.js"],
    languageOptions: { globals: globals.node },
  },
];
