// Day 4: the Evaluation screen is in place. These pass from the start of Day 4.
import { expect, test } from "@playwright/test";

test("Evaluation opens from the sidebar", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("nav-evaluation").click();
  await expect(page.getByTestId("run-eval")).toBeVisible();
});

test("twenty values to label, with the first guidelines", async ({ page }) => {
  await page.goto("/#/evaluation/labelling");
  await expect(page.getByTestId("items").locator('[data-testid^="item-"]')).toHaveCount(20);
  await expect(page.getByTestId("guidelines")).toContainText("v0");
});

test("two judges, and no runs to compare yet", async ({ page }) => {
  await page.goto("/#/evaluation/judges");
  await expect(page.getByTestId("judge-wrong_date")).toBeVisible();
  await expect(page.getByTestId("judge-incomplete_name")).toBeVisible();
  await page.getByTestId("etab-compare").click();
  await expect(page.getByTestId("no-runs")).toBeVisible();
});
