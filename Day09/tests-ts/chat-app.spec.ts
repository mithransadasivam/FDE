// spec: specs/chat-app.md
// seed: tests-ts/seed.spec.ts
import { test, expect } from '@playwright/test';

const CHAT_BOX = 'Ask a question about the IT policies';

test.describe('IT Policies Chat App', () => {
  test('Page opens in its starting state', async ({ page }) => {
    // 1. Open the app (`/`).
    await page.goto('/');

    // The heading, the intro line and the empty chat box are visible.
    await expect(page.getByRole('heading', { level: 1, name: 'Ask the IT policies' })).toBeVisible();
    await expect(page.getByText('Answers come only from the IT policy documents')).toBeVisible();
    const box = page.getByPlaceholder(CHAT_BOX);
    await expect(box).toBeVisible();
    await expect(box).toHaveValue('');

    // No chat messages, no "Sources:" line and no decline line yet.
    await expect(page.getByTestId('stChatMessage')).toHaveCount(0);
    await expect(page.getByText(/^Sources: /)).toHaveCount(0);
    await expect(page.getByText(/^No sources:/)).toHaveCount(0);
  });

  test('An answerable question gets a cited answer and a Sources line', async ({ page }) => {
    // 1. Open the app.
    await page.goto('/');

    // 2. Type the question in the chat box and press Enter.
    const question = 'How long can a VPN session stay connected?';
    const box = page.getByPlaceholder(CHAT_BOX);
    await box.fill(question);
    await box.press('Enter');

    // 3. Wait for the "Sources: " line (shown only when the answer has finished streaming).
    const sources = page.getByText(/^Sources: /);
    await expect(sources).toBeVisible();

    // Two messages: the question first, then the answer.
    const messages = page.getByTestId('stChatMessage');
    await expect(messages).toHaveCount(2);
    await expect(messages.first()).toContainText(question);

    // The answer is not empty and has a [n] citation (structure, not exact wording).
    const answer = messages.last().getByTestId('stMarkdownContainer').first();
    await expect(answer).toHaveText(/\S/);
    await expect(answer).toHaveText(/\[\d+\]/);

    // Exactly one Sources line, naming a document (.pdf or .md) and a page number.
    await expect(sources).toHaveCount(1);
    await expect(sources).toHaveText(/\.(pdf|md), page \d+/);

    // The decline line is not shown.
    await expect(page.getByText(/^No sources:/)).toHaveCount(0);
  });

  test('Two questions in a row build up the conversation', async ({ page }) => {
    // 1. Open the app, ask the VPN question, wait for "Sources: ".
    await page.goto('/');
    const box = page.getByPlaceholder(CHAT_BOX);
    await box.fill('How long can a VPN session stay connected?');
    await box.press('Enter');
    const sources = page.getByText(/^Sources: /);
    await expect(sources).toHaveCount(1);

    // 2. Without reloading, ask "How often are laptops replaced?" and wait for the second "Sources: ".
    await box.fill('How often are laptops replaced?');
    await box.press('Enter');
    await expect(sources).toHaveCount(2);

    // Four chat messages in order: question 1, answer 1, question 2, answer 2.
    const messages = page.getByTestId('stChatMessage');
    await expect(messages).toHaveCount(4);
    await expect(messages.nth(0)).toContainText('How long can a VPN session stay connected?');
    await expect(messages.nth(2)).toContainText('How often are laptops replaced?');

    // Each answer has its own [n] citation and its own Sources line.
    for (const answer of [messages.nth(1), messages.nth(3)]) {
      await expect(answer).toContainText(/\[\d+\]/);
      await expect(answer.getByText(/^Sources: /)).toHaveCount(1);
    }
  });
});
