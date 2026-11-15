import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// dash-api runs on 8090 (docker compose publishes it). Override with DASH_API=http://host:port.
const target = process.env.DASH_API ?? "http://localhost:8090";

export default defineConfig({
  plugins: [react()],
  // shadcn-style "@/components/ui/..." imports.
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    port: 5173,
    proxy: {
      "/api": { target, changeOrigin: true },
      "/ws": { target: target.replace(/^http/, "ws"), ws: true },
    },
  },
});
