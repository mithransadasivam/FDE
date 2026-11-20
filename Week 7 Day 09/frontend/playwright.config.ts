import { defineConfig } from "@playwright/test";

// End-to-end tests run the real backend in fake-model mode (no API key, no network),
// on their own ports and their own engagement folder, so your dev servers and work are untouched.
const python = process.env.PYTHON ?? "python";
const DAY8 = { FDE_BANK_URL: "http://localhost:8110", FDE_MCP_URL: "http://localhost:8210" };

export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/seed-rows.ts",
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
      env: {
        FDE_FAKE_LLM: "1", FDE_RESET_ON_START: "1", FDE_ENGAGEMENT_DIR: "../.e2e/engagement", FDE_DOCS_DIR: "../.e2e/docs", FDE_SYNTHETIC_DIR: "../.e2e/synthetic",
        // Day 5: the same model settings for everyone, whatever your .env says, and the first plan from slide 15
        FDE_LLM_PROVIDER: "bedrock", FDE_BEDROCK_REGION: "eu-west-2", FDE_BEDROCK_MODEL_ID: "anthropic.claude-sonnet-5",
        FDE_GUARDRAIL_ID: "", FDE_GUARDRAIL_VERSION: "", FDE_GUARDRAIL_POLICY: "", FDE_PLAN_FILE: "tests/fixtures/pilot/plan_start.json",
        // Day 8: the bank's systems and the MCP server, on their own ports too
        ...DAY8,
      },
      reuseExistingServer: false,
    },
    {
      command: `${python} -m bank.server --port 8110`,
      cwd: "../backend",
      url: "http://localhost:8110/health",
      env: { ...DAY8, FDE_RESET_ON_START: "1", FDE_BANK_STATE: "../.e2e/bank", FDE_WEBHOOK_URL: "http://localhost:8010/api/hooks/kyc-exceptions" },
      reuseExistingServer: false,
    },
    {
      command: `${python} -m app.integration.mcp_server`,
      cwd: "../backend",
      url: "http://localhost:8210/.well-known/oauth-protected-resource/mcp",
      env: { ...DAY8, FDE_ENGAGEMENT_DIR: "../.e2e/engagement" },
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
