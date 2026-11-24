// Day 10 helpers: sign in, start a case workflow, decide its approvals, crash the worker, and read the case.
import { expect, type APIRequestContext, type Page } from "@playwright/test";

const BANK = "http://localhost:8110";

/** A clean bank (no messages, replies, grants or CaseFlow outcomes), so each test counts only its own writes. */
export async function resetBank(request: APIRequestContext) {
  await request.post(`${BANK}/course/reset`);
}

export async function signInWf(page: Page, who = "tom.reyes") {
  await page.goto("/#/workflows/case");
  await page.getByTestId("agent-sign-in").click();
  await page.locator("#username").selectOption(who);
  await page.locator("#password").fill("kyc-demo");
  await page.locator("#signin").click();
  await expect(page.getByTestId("wf-exceptions")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("worker-state")).toHaveText("Workflow worker up", { timeout: 20_000 });
}

export async function startCase(page: Page, ticket: string) {
  await page.getByTestId(`start-${ticket}`).click();
  await expect(page.getByTestId("case-ticket")).toHaveText(ticket, { timeout: 10_000 });
}

export async function approve(page: Page, ticket: string) {
  await page.getByTestId(`approve-${ticket}`).click({ timeout: 45_000 });
}

export async function crashNow(page: Page) {
  const crashes = async () => Number((await page.getByTestId("worker-crashes").innerText()).split(" ")[0]);
  const before = await crashes();
  await page.getByTestId("crash-now").click();
  await expect.poll(crashes, { timeout: 10_000 }).toBe(before + 1);
  await expect(page.getByTestId("worker-state")).toHaveText("Workflow worker up", { timeout: 20_000 });
}

export async function caseEnds(page: Page, state: string, timeout = 60_000) {
  await expect(page.getByTestId("case-state")).toHaveText(state, { timeout });
}

/** The course day of the first message of this kind, from the bank's records on the case screen. */
export async function messageDay(page: Page, kind: "request" | "reminder"): Promise<number> {
  const row = page.getByTestId("case-messages").locator("tr", { hasText: kind });
  await expect(row).toBeVisible();
  return Number((await row.locator("td").nth(1).innerText()).trim());
}
