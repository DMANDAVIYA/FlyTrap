/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)", panel: "var(--panel)", line: "var(--line)", text: "var(--text)", text2: "var(--text-2)",
        real: "var(--real)", trap: "var(--trap)", warn: "var(--warn)", ok: "var(--ok)",
      },
      fontFamily: {
        display: ['"Chakra Petch"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
