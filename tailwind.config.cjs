const path = require("node:path");

/** @type {import('tailwindcss').Config} */
module.exports = {
  presets: [require("./src/tailwind/preset.cjs")],
  content: [
    path.join(__dirname, "src/**/*.{js,jsx,ts,tsx}"),
    path.join(__dirname, ".storybook/**/*.{js,ts}"),
  ],
};
