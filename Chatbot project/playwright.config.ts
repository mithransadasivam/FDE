import { defineConfig, devices } from '@playwright/test';

// The Test Agents (planner, generator, healer) work against the app running with the FAKE chatbot:
// fixed topics, no models, no key, so a plan or a test written by an agent is repeatable and costs nothing.
export default defineConfig({
  testDir: './tests/agents',
  fullyParallel: false,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:8620',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: '.venv\\Scripts\\python.exe -m streamlit run app/ui.py --server.port 8620 --server.address 127.0.0.1 --server.headless true',
    url: 'http://127.0.0.1:8620/_stcore/health',
    reuseExistingServer: true,
    timeout: 90_000,
    env: { CHAT_FAKE: '1', CHAT_FAKE_DELAY: '0.02', CALL_LOG: '0', OPENROUTER_API_KEY: '' },
  },
});
