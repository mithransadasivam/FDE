// Ticket ENG-1102: a smudged date is not trusted.
import { expect, test } from "@playwright/test";
import { openTab, train } from "./fixtures/modellab";

test.beforeAll(async ({ request }) => { await train(request); });

test("B-012: the smudged statement date has a confidence below 0.70 and goes to the pilot", async ({ page }) => {
  await openTab(page, "read", "/B-012");
  await expect(page.getByTestId("val-statement_date")).toHaveText("01 Sep 2026");
  const conf = Number(await page.getByTestId("conf-statement_date").innerText());
  expect(conf).toBeLessThan(0.7);
  await expect(page.getByTestId("ml-decision")).toContainText("To the pilot");
});

test("on the October batch, no error is one the small model is sure of", async ({ page }) => {
  await openTab(page, "read", "/B-001");
  await expect(page.getByTestId("confident-errors")).toHaveText("0");
});
