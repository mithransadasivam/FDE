// Day 9 helpers: sign in to the console with the bank, and run the agent on one exception.
import { expect, type Page } from "@playwright/test";

export async function signIn(page: Page, who = "tom.reyes", tab = "run") {
  await page.goto(`/#/agent/${tab}`);
  await page.getByTestId("agent-sign-in").click();
  await page.locator("#username").selectOption(who);
  await page.locator("#password").fill("kyc-demo");
  await page.locator("#signin").click();
  await expect(page.getByTestId("dtab-run")).toBeVisible({ timeout: 20_000 });
}

/** Run one exception. decide: what to do if the agent asks for approval ("approve" or "reject"). */
export async function runOne(page: Page, ticket: string, decide: "approve" | "reject" = "approve", note = "") {
  await page.getByTestId(`run-${ticket}`).click();
  const ended = page.getByTestId("run-status").filter({ hasNotText: /running|waiting/ });
  const ask = page.getByTestId(`${decide}-${ticket}`);
  await expect(ended.or(ask)).toBeVisible({ timeout: 45_000 });
  if (await ask.isVisible()) {
    if (note) await page.getByTestId(`approval-note-${ticket}`).fill(note);
    await ask.click();
  }
  await expect(ended).toBeVisible({ timeout: 45_000 });
}
