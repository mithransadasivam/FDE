// Ticket ENG-1101: the small model learns only from the reads the teacher is sure of.
import { expect, test } from "@playwright/test";
import { openTab } from "./fixtures/modellab";

test("Train keeps the 1,153 reads both readings agree on", async ({ page }) => {
  test.setTimeout(90_000);
  await openTab(page, "train");
  await page.getByTestId("train").click();
  await expect(page.getByTestId("kept")).toHaveText("1,153", { timeout: 60_000 });
  await expect(page.getByTestId("skipped")).toHaveText("347");
});

test("alone on the October batch, the small model gets 98.2% of fields right", async ({ page }) => {
  test.setTimeout(90_000);
  await openTab(page, "train");
  await page.getByTestId("train").click();
  await expect(page.getByTestId("trained")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("oct-acc")).toHaveText("98.2%");
  await expect(page.getByTestId("field-acc-statement_date")).toContainText("93.0%");
});
