// Day 11: the Model lab is there from the start (these pass before any ticket is built).
import { expect, test } from "@playwright/test";
import { openTab, train } from "./fixtures/modellab";

test("the Model lab shows the teacher's reads and today's tickets", async ({ page }) => {
  await openTab(page, "train");
  await expect(page.getByTestId("teacher-reads")).toContainText("1,500");
  await expect(page.getByTestId("reads-agree")).toHaveText("1,153");
  await expect(page.getByTestId("ticket-ENG-1101")).toBeVisible();
  await expect(page.getByTestId("disagree-sample")).toBeVisible();
});

test("Train makes a small model and lists it", async ({ page }) => {
  test.setTimeout(90_000);
  await openTab(page, "train");
  await page.getByTestId("train").click();
  await expect(page.getByTestId("trained")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("models")).toContainText("in use");
  await expect(page.getByTestId("oct-acc")).toContainText("%");
});

test("Read a document shows the page and the four fields", async ({ page, request }) => {
  test.setTimeout(90_000);
  await train(request);
  await openTab(page, "read", "/B-001");
  await expect(page.getByTestId("ml-page")).toBeVisible();
  await expect(page.getByTestId("val-issuer")).toHaveText("Copperline Broadband");
});
