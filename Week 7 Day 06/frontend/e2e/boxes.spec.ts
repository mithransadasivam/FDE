// Ticket ENG-303: field boxes on the document. The backend is mocked with a contract fixture,
// so this test runs before ENG-301 and ENG-302 exist (that is how the UI session works in parallel).
import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";

const fixture = JSON.parse(readFileSync("e2e/fixtures/case_D03-014.json", "utf-8"));

test.beforeEach(async ({ page }) => {
  await page.route("**/api/cases/D03-014", (route) => route.fulfill({ json: fixture }));
  await page.goto("/#/cases/case/D03-014");
  await expect(page.getByTestId("doc-image")).toBeVisible();
});

test("one box per field, coloured by status", async ({ page }) => {
  await expect(page.getByTestId("page").locator('[data-testid^="box-"]')).toHaveCount(4);
  await expect(page.getByTestId("box-full_name")).toHaveAttribute("data-status", "ok");
  await expect(page.getByTestId("box-issuer")).toHaveAttribute("data-status", "check");
  await expect(page.getByTestId("box-statement_date")).toHaveAttribute("data-status", "not_on_page");
});

test("each box sits where the field is on the page", async ({ page }) => {
  const img = (await page.getByTestId("doc-image").boundingBox())!;
  const box = (await page.getByTestId("box-full_name").boundingBox())!;
  const [x0, y0, x1] = fixture.fields[0].box as number[];
  expect(Math.abs(box.x - (img.x + x0 * img.width))).toBeLessThan(3);
  expect(Math.abs(box.y - (img.y + y0 * img.height))).toBeLessThan(3);
  expect(Math.abs(box.width - (x1 - x0) * img.width)).toBeLessThan(4);
});

test("each box is labelled with the field and how sure it is", async ({ page }) => {
  await expect(page.getByTestId("box-full_name")).toContainText("Full name · 0.96");
  await expect(page.getByTestId("box-issuer")).toContainText("Issuer · 0.72");
  await expect(page.getByTestId("box-statement_date")).toContainText("Statement date · not on the page");
});

test("clicking a box selects its field, and the other way round", async ({ page }) => {
  await page.getByTestId("box-address").click();
  await expect(page.getByTestId("box-address")).toHaveAttribute("data-selected", "true");
  await expect(page.getByTestId("field-address")).toHaveAttribute("data-selected", "true");
  await page.getByTestId("field-issuer").click();
  await expect(page.getByTestId("box-issuer")).toHaveAttribute("data-selected", "true");
  await expect(page.getByTestId("box-address")).toHaveAttribute("data-selected", "false");
});
