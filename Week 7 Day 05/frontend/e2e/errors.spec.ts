// Ticket ENG-402: error analysis on the 50 checked documents.
import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/#/evaluation/errors");
  await page.getByTestId("run-eval").click();
});

test("the run is scored against Tom's labels", async ({ page }) => {
  await expect(page.getByTestId("not-built")).toHaveCount(0);
  await expect(page.getByTestId("accuracy")).toHaveText("94%");
  await expect(page.getByTestId("eval-kpis")).toContainText("84%");
});

test("every wrong field is listed with what Tom says", async ({ page }) => {
  await expect(page.getByTestId("errors").locator('[data-testid^="err-"]').filter({ hasNotText: "Decision" })).toHaveCount(12);
  await expect(page.getByTestId("err-D04-031|statement_date")).toContainText("12 Sep 2026");
});

test("tags become a Pareto chart", async ({ page }) => {
  for (const id of ["D04-031|statement_date", "D04-034|statement_date", "D04-033|full_name"]) {
    const box = page.getByTestId(`tag-${id}`);
    await box.fill(id.endsWith("full_name") ? "incomplete name" : "wrong date chosen");
    await box.blur();
  }
  await expect(page.getByTestId("pareto")).toBeVisible();
  await expect(page.getByTestId("taxonomy")).toContainText("wrong date chosen · 2");
});
