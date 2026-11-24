// Ticket ENG-1001: a crash while Tom decides does not make the agent work the case again.
import { expect, test } from "@playwright/test";
import { approve, caseEnds, crashNow, resetBank, signInWf, startCase } from "./fixtures/workflow";

test.beforeEach(async ({ request }) => { await resetBank(request); });

test("the worker crashes while KX-1001 waits for Tom: one agent run, and Tom's approval still counts", async ({ page }) => {
  test.setTimeout(150_000);
  await signInWf(page);
  await startCase(page, "KX-1001");
  await expect(page.getByTestId("approve-KX-1001")).toBeVisible({ timeout: 45_000 });
  await crashNow(page);
  await page.waitForTimeout(2_500);  // the new worker has picked the case up
  await expect(page.getByTestId("case-runs")).toContainText("1 agent run ");
  await approve(page, "KX-1001");
  await expect(page.getByTestId("event-recorded").first()).toBeVisible({ timeout: 30_000 });
  await approve(page, "KX-1001");     // round 2, after the applicant's utility bill
  await caseEnds(page, "completed");
  await expect(page.getByTestId("case-runs")).toContainText("2 agent runs");
});

test("Tom's approval reaches the workflow after a restart of the console's screen", async ({ page }) => {
  test.setTimeout(150_000);
  await signInWf(page);
  await startCase(page, "KX-1004");
  await expect(page.getByTestId("approve-KX-1004")).toBeVisible({ timeout: 45_000 });
  await page.reload();
  await approve(page, "KX-1004");
  await expect(page.getByTestId("event-recorded")).toBeVisible({ timeout: 30_000 });
  await caseEnds(page, "escalated", 90_000);
});
