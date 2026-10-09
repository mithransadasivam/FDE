// Day 9: the seed test. The Test Agents start from here: it opens the chat app and waits until
// the chat box is ready. Done: you don't need to change it.
import { test, expect } from '@playwright/test';

test('seed', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByPlaceholder('Ask a question about the IT policies')).toBeVisible();
});
