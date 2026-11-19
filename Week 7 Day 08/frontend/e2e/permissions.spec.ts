// Day 8, Activity 4: every tool as every person (needs ENG-801, ENG-802 and the bank's rules).
import { expect, test } from "@playwright/test";

test("the permission matrix is 30 of 30", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto("/#/integrations/permissions");
  await page.getByTestId("perm-run").click();
  await expect(page.getByTestId("perm-summary")).toContainText("30 of 30", { timeout: 60_000 });
});
