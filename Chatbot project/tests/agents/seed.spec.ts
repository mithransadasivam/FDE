import { test, expect } from '@playwright/test';

// The seed test: how a test starts. It opens the app (running with the fake chatbot) and waits for the page to be ready.
// The planner, generator and healer agents copy this setup.
test('seed: the app opens', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: '🛠 IT Help Desk Assistant' }).first()).toBeVisible();
});
