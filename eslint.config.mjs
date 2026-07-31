import js from "@eslint/js";
import nounsanitized from "eslint-plugin-no-unsanitized";

export default [
  js.configs.recommended,
  nounsanitized.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: 2021,
      sourceType: "script",
      globals: {
        $: "readonly", jQuery: "readonly", ko: "readonly", _: "readonly",
        OctoPrint: "readonly", OCTOPRINT_VIEWMODELS: "writable",
        API_BASEURL: "readonly", PNotify: "readonly", GCODE: "readonly",
        window: "readonly", document: "readonly", console: "readonly",
        setTimeout: "readonly", clearTimeout: "readonly", location: "readonly",
      },
    },
    rules: { "no-unused-vars": ["error", { args: "none" }] },
  },
];
