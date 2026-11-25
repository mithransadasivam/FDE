// Ticket ENG-1103: the cascade lets through no more errors than the pilot alone.
import { expect, test } from "@playwright/test";
import { openTab, train } from "./fixtures/modellab";

test.beforeAll(async ({ request }) => { await train(request); });

test("at 0.70: no small-model error slips through, and no more in all than the pilot's 3", async ({ page }) => {
  test.setTimeout(90_000);
  await openTab(page, "cascade");
  await page.getByTestId("th-0.7").click();
  await expect(page.getByTestId("cascade-kpis")).toContainText("from the small model: 0", { timeout: 60_000 });
  expect(Number(await page.getByTestId("slipped").innerText())).toBeLessThanOrEqual(3);
});

test("every unsure field is named, and the weakest one decides", async ({ page }) => {
  test.setTimeout(90_000);
  await openTab(page, "cascade");
  await page.getByTestId("th-0.7").click();
  await expect(page.getByTestId("cascade-reasons")).toContainText("statement_date 0.53 below 0.70", { timeout: 60_000 });
  const share = Number((await page.getByTestId("teacher-share").innerText()).replace("%", ""));
  expect(share).toBeGreaterThan(15);
  expect(share).toBeLessThan(35);
});
