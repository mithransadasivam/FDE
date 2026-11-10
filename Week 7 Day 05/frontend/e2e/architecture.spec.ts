// Ticket ENG-202: architecture options checked against the client's rules, end to end.
import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.goto("/#/design/architecture");
});

test("option A meets every rule", async ({ page }) => {
  await expect(page.getByTestId("not-built")).toHaveCount(0);
  await expect(page.getByTestId("all-rules-met")).toBeVisible();
});

test("option C lists six broken rules", async ({ page }) => {
  await page.getByTestId("opt-C").click();
  await expect(page.getByTestId("violations").locator("li")).toHaveCount(6);
  await expect(page.getByTestId("rule-residency")).toHaveAttribute("data-ok", "false");
});

test("the canvas marks what breaks a rule", async ({ page }) => {
  await page.getByTestId("opt-C").click();
  await expect(page.getByTestId("node-saas")).toHaveAttribute("data-violation", "true");
  await expect(page.getByTestId("edge-saas-caseflow")).toHaveAttribute("data-violation", "true");
  await expect(page.getByTestId("node-analyst")).toHaveAttribute("data-violation", "false");
});
