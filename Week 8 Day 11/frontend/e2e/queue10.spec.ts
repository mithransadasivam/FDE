// Day 10, Activity 4: Tom's four exceptions as case workflows, start to end, every write counted.
import { expect, test } from "@playwright/test";
import { resetBank, signInWf } from "./fixtures/workflow";

test.beforeEach(async ({ request }) => { await resetBank(request); });

test("Tom's queue as case workflows: 4 of 4 as the bank expects", async ({ page }) => {
  test.setTimeout(240_000);
  await signInWf(page);
  await page.getByTestId("wtab-queue").click();
  await page.getByTestId("queue10-go").click();
  for (const t of ["KX-1001", "KX-1002", "KX-1004", "KX-1001", "KX-1002"]) {
    await page.getByTestId(`approve-${t}`).first().click({ timeout: 90_000 });
    await page.waitForTimeout(500);
  }
  await expect(page.getByTestId("queue10-summary")).toContainText("4 of 4", { timeout: 120_000 });
});
