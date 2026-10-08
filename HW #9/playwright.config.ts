// Day 9: Playwright Test settings for the TypeScript tests written by the Test Agents.
// The Python browser tests in tests/e2e do not use this file.
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests-ts',
  timeout: 60_000,
  use: {
    baseURL: 'http://localhost:8597',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  // Starts the streaming chat app before the tests. CHAT_FAKE=1: a fake chatbot, so no models
  // are needed and every run gives the same answers. Remove it to test the real chatbot.
  webServer: {
    command: 'python -m streamlit run app/rag_app_stream.py --server.port 8597 --server.headless true',
    url: 'http://localhost:8597',
    reuseExistingServer: true,
    timeout: 60_000,
    env: { CHAT_FAKE: '1' },
  },
});
