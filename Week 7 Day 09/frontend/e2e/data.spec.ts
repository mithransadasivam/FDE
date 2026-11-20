// Day 7: the Ask the data and Data agent screens are in place. These pass from the start of Day 7.
import { expect, test } from "@playwright/test";

test("Data agent opens from the sidebar with the warehouse and its approved tables", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("nav-data").click();
  await expect(page.getByTestId("wh-tables")).toContainText("9 tables, 7 approved", { timeout: 20_000 });
  await expect(page.getByTestId("wh-caseflow.documents")).toContainText("65,117");
  await expect(page.getByTestId("wh-hr.analyst_pay")).toContainText("Not approved");
});

test("semantic layer v1 describes the tables but has none of the bank's terms", async ({ page }) => {
  await page.goto("/#/data/warehouse");
  await expect(page.getByTestId("layer-terms")).toContainText("No terms yet", { timeout: 20_000 });
  await page.getByTestId("layer-view-yaml").click();
  await expect(page.getByTestId("layer-yaml")).toContainText("working_days_open");
});

test("Ask the data opens from the client workspace with three people to sign in as", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("nav-ask").click();
  await expect(page.getByTestId("user-tom.reyes")).toContainText("Only North 1's cases");
  await expect(page.getByTestId("user-grace.mensah")).toContainText("North region");
  await expect(page.getByTestId("user-helen.achebe")).toContainText("customer names hidden");
});
