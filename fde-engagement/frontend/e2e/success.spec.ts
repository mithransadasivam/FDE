// Ticket ENG-102: measurable success criteria and the use-case matrix.
import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/#/discovery/success");
});

test("a vague criterion shows every problem; a good one is measurable", async ({ page }) => {
  await expect(page.getByTestId("criterion-SC2").getByTestId("problems").locator("li")).toHaveCount(7);
  await expect(page.getByTestId("criterion-SC1").getByTestId("measurable")).toBeVisible();
});

test("fixing a criterion makes it measurable", async ({ page }) => {
  const card = page.getByTestId("criterion-SC2");
  await card.getByRole("button", { name: "edit" }).click();
  await card.getByTestId("edit-metric").fill("Minutes of analyst time per application");
  await card.getByTestId("edit-baseline").fill("22");
  await card.getByTestId("edit-target").fill("12");
  await card.getByTestId("edit-unit").fill("minutes");
  await card.getByTestId("edit-measured_how").fill("CaseFlow work timer, pilot cases, weekly");
  await card.getByTestId("edit-owner").fill("Deborah Okafor");
  await card.getByTestId("edit-by_when").fill("Week 6");
  await page.locator("select").nth(1).selectOption("decrease");
  await card.getByTestId("save-criterion").click();
  await expect(page.getByTestId("criterion-SC2").getByTestId("measurable")).toBeVisible();
});

test("the matrix shows all five use cases, with UC5 excluded", async ({ page }) => {
  const m = page.getByTestId("usecase-matrix");
  await expect(m.locator('[data-testid^="uc-UC"]')).toHaveCount(5);
  await expect(m.getByTestId("uc-UC5")).toHaveAttribute("data-excluded", "true");
});

test("choosing a first use case highlights it on the matrix", async ({ page }) => {
  await page.getByTestId("pick-UC1").click();
  await expect(page.getByTestId("usecase-matrix").getByTestId("uc-UC1")).toHaveAttribute("data-first", "true");
  await expect(page.getByTestId("uc-row-UC1")).toContainText("first");
});
