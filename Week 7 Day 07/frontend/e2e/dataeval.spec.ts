// Day 7, Activity 3: evaluate the agent on the bank's 30 questions (needs ENG-701 and ENG-702).
import { expect, test } from "@playwright/test";

test("with caseflow_v1 the agent gets 20 of 30 right, and ambiguous terms are the most common failure", async ({ page }) => {
  await page.goto("/#/data/eval");
  await page.getByTestId("run-caseflow_v1").click();
  await expect(page.getByTestId("evrun-caseflow_v1")).toContainText("20 / 30", { timeout: 30_000 });
  await expect(page.getByTestId("top-failure")).toContainText("Ambiguous term, 8 of the 10 wrong answers");
});

test("a wrong answer shows what the agent assumed", async ({ page }) => {
  await page.goto("/#/data/eval");
  await page.getByTestId("run-caseflow_v1").click();
  await expect(page.getByTestId("evrun-caseflow_v1")).toContainText("20 / 30", { timeout: 30_000 });
  await page.getByTestId("evq-Q07").click();
  await expect(page.getByTestId("detail-assumptions")).toContainText("calendar days");
  await expect(page.getByTestId("eval-detail")).toContainText("16.8");
});
