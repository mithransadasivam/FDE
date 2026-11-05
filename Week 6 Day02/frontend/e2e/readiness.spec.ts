// Ticket ENG-201: the data readiness screen, end to end.
import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/#/design/data");
  await page.getByTestId("run-profile").click();
});

test("every column of the sample is profiled", async ({ page }) => {
  await expect(page.getByTestId("not-built")).toHaveCount(0);
  await expect(page.getByTestId("profile-table").locator('[data-testid^="col-"]')).toHaveCount(17);
  await expect(page.getByTestId("col-file_format")).toContainText("heic");
});

test("personal data in the notes turns Private red", async ({ page }) => {
  await expect(page.getByTestId("col-analyst_notes").getByTestId("pii")).toContainText("phone");
  await expect(page.getByTestId("ready-Private").getByTestId("status")).toHaveAttribute("data-status", "red");
});

test("the issues list names the duplicates", async ({ page }) => {
  await expect(page.getByTestId("issues")).toContainText("3 duplicate values");
});
