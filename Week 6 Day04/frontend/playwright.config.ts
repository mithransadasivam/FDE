import { defineConfig } from "@playwright/test";

// End-to-end tests run the real backend in fake-model mode (no API key, no network),
// on their own ports and their own engagement folder, so your dev servers and work are untouched.
const python = process.env.PYTHON ?? "python";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:5183", viewport: { width: 1440, height: 900 }, actionTimeout: 5_000 },
  webServer: [
    {
      command: `${python} -m uvicorn app.main:app --port 8010`,
      cwd: "../backend",
      url: "http://localhost:8010/api/health",
      env: { FDE_FAKE_LLM: "1", FDE_RESET_ON_START: "1", FDE_ENGAGEMENT_DIR: "../.e2e/engagement", FDE_DOCS_DIR: "../.e2e/docs", FDE_SYNTHETIC_DIR: "../.e2e/synthetic" },
      reuseExistingServer: false,
    },
    {
      command: "npx vite",
      url: "http://localhost:5183",
      env: { WEB_PORT: "5183", API_TARGET: "http://localhost:8010" },
      reuseExistingServer: false,
    },
  ],
});
