/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // rgb channels so opacity modifiers (border-trap/50) work.
      colors: Object.fromEntries(
        [["bg", "bg"], ["panel", "panel"], ["line", "line"], ["line2", "line-2"], ["text", "text"], ["text2", "text-2"],
          ["real", "real"], ["trap", "trap"], ["warn", "warn"], ["ok", "matrix"], ["matrix", "matrix"]]
          .map(([name, v]) => [name, `rgb(var(--${v}-rgb) / <alpha-value>)`]),
      ),
      borderColor: { DEFAULT: "rgb(var(--line-rgb) / <alpha-value>)" },
      fontFamily: {
        sans: ['"Mona Sans Variable"', "system-ui", "sans-serif"],
        display: ['"Mona Sans Variable"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono Variable"', "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
