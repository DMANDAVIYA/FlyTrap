/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // rgb channels so opacity modifiers (border-trap/50) work.
      colors: Object.fromEntries(
        [["bg", "bg"], ["panel", "panel"], ["line", "line"], ["line2", "line-2"], ["text", "text"], ["text2", "text-2"],
          ["green", "green"], ["real", "sage"], ["trap", "green"], ["ok", "green"], ["warn", "warn"], ["breach", "breach"]]
          .map(([name, v]) => [name, `rgb(var(--${v}-rgb) / <alpha-value>)`]),
      ),
      borderColor: { DEFAULT: "rgb(var(--line-rgb) / <alpha-value>)" },
      fontFamily: {
        sans: ['"Montserrat Variable"', "system-ui", "sans-serif"],
        display: ['"Sofia Sans Extra Condensed Variable"', '"Montserrat Variable"', "sans-serif"],
        mono: ['"JetBrains Mono Variable"', "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
