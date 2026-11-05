// Day 2 screens that work from the start.
import { expect, test } from "@playwright/test";

test("the sidebar opens Design & cost", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("nav-design").click();
  await expect(page.getByRole("heading", { name: /Solution design/ })).toBeVisible();
});

test("option A is drawn from its JSON file", async ({ page }) => {
  await page.goto("/#/design/architecture");
  await expect(page.getByTestId("arch-canvas").locator('[data-testid^="node-"]')).toHaveCount(9);
});

test("run-cost shows a bar for every option and the value of time saved", async ({ page }) => {
  await page.goto("/#/design/cost");
  await expect(page.getByTestId("bar-A")).toBeVisible();
  await expect(page.getByTestId("bar-C")).toBeVisible();
  await expect(page.getByTestId("value")).toHaveText("£10,836");
});

test("decision record and plan tabs explain what to do when empty", async ({ page }) => {
  await page.goto("/#/design/adr");
  await expect(page.getByTestId("no-adr")).toBeVisible();
  await page.getByTestId("dtab-plan").click();
  await expect(page.getByTestId("no-plan")).toBeVisible();
});
