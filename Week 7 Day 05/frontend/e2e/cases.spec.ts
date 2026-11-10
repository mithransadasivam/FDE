// Day 3: the Cases screen is in place. These pass from the start of Day 3.
import { expect, test } from "@playwright/test";

test("Cases opens from the sidebar and lists all 30 documents", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("nav-cases").click();
  await expect(page.getByTestId("queue").locator('[data-testid^="row-"]')).toHaveCount(30);
});

test("opening a case shows the document and the application", async ({ page }) => {
  await page.goto("/#/cases/queue");
  await page.getByTestId("row-D03-002").click();
  await expect(page.getByTestId("doc-image")).toBeVisible();
  await expect(page.getByTestId("application")).toContainText("22 Mill Lane, Stroud, GL5 1AB");
});

test("the FDE tabs open", async ({ page }) => {
  await page.goto("/#/cases/pr");
  await expect(page.getByTestId("no-review")).toBeVisible();
  await page.getByTestId("ctab-demo").click();
  await expect(page.getByTestId("run-demo")).toBeVisible();
});
