import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// `npm run dev` proxies /api to the local backend (VITE_API_TARGET overrides, e.g. for a remote one).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy: { "/api": { target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000", changeOrigin: true } } },
  build: { sourcemap: false, rollupOptions: { output: { manualChunks: { react: ["react", "react-dom", "react-router"], query: ["@tanstack/react-query"] } } }, chunkSizeWarningLimit: 700 },
  test: { environment: "node" },
});
