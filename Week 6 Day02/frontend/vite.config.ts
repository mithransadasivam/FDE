import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The browser talks to /api; Vite passes those calls to the FastAPI backend.
export default defineConfig({
  plugins: [react()],
  server: {
    port: Number(process.env.WEB_PORT ?? 5173),
    proxy: { "/api": process.env.API_TARGET ?? "http://localhost:8000" },
  },
});
