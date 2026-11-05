// Ticket ENG-101: findings with evidence, end to end (scripted model replies).
import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/#/discovery/findings");
  await page.getByTestId("extract-findings").click();
});

test("findings appear grouped, each with its quote", async ({ page }) => {
  await expect(page.locator('[data-testid^="finding-F"]')).toHaveCount(17);
  await expect(page.getByTestId("not-built")).toHaveCount(0);
  await expect(page.getByTestId("finding-F01")).toContainText("Our median is seven working days");
});

test("quotes that are not in the transcript are flagged", async ({ page }) => {
  await expect(page.getByTestId("bad-count")).toHaveText("2");
  await expect(page.getByTestId("finding-F07").getByTestId("evidence-bad")).toBeVisible();
  await expect(page.getByTestId("finding-F11").getByTestId("evidence-bad")).toBeVisible();
  await expect(page.getByTestId("finding-F04").getByTestId("evidence-ok")).toBeVisible();
});

test("pain points are placed on the matrix", async ({ page }) => {
  await expect(page.getByTestId("pain-matrix").locator('[data-testid^="pain-F"]')).toHaveCount(7);
});

test("a finding marked wrong stays marked after a reload", async ({ page }) => {
  await page.getByTestId("finding-F07").getByRole("button", { name: "wrong" }).click();
  await page.reload();
  await expect(page.getByTestId("finding-F07")).toHaveClass(/opacity-50/);
});
