// S06: a copy button per field. Written before the feature (docs/specs/copy_button_tests.md).
// Each test reads its values from the screen and uses a case no other test touches.
import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";

test.use({ permissions: ["clipboard-read", "clipboard-write"] });

const clipboard = (page: Page) => page.evaluate(() => navigator.clipboard.readText());

test("one click copies the field exactly as shown", async ({ page }) => {
  await page.goto("/#/cases/case/D03-003");
  const shown = (await page.getByTestId("field-address").textContent()) ?? "";
  expect(shown).toContain("7 Orchard Close, Tewkesbury, GL20 5RT");
  await page.getByTestId("copy-address").click();
  expect(await clipboard(page)).toBe("7 Orchard Close, Tewkesbury, GL20 5RT");
  await expect(page.getByTestId("copy-address")).toContainText("Copied");
});

test("a missing field has nothing to copy", async ({ page }) => {
  const fixture = JSON.parse(readFileSync("e2e/fixtures/case_D03-014.json", "utf-8"));
  const issuer = fixture.fields.find((f: { name: string }) => f.name === "issuer");
  Object.assign(issuer, { value: "", confidence: 0, status: "missing", box: null, page_text: "", note: "Not found on the page" });
  await page.route("**/api/cases/D03-014", (route) => route.fulfill({ json: fixture }));
  await page.goto("/#/cases/case/D03-014");
  await expect(page.getByTestId("field-issuer")).toBeVisible();
  await expect(page.getByTestId("copy-issuer")).toBeDisabled();
  await expect(page.getByTestId("copy-full_name")).toBeEnabled();
  await expect(page.getByTestId("copy-address")).toBeEnabled();
  await expect(page.getByTestId("copy-statement_date")).toBeEnabled();
});

test("after a correction, copy gives the corrected value", async ({ page }) => {
  await page.goto("/#/cases/case/D03-020");
  await expect(page.getByTestId("field-statement_date")).toContainText("14 Sep 2026");
  await page.getByTestId("correct-statement_date").click();
  await page.getByTestId("correct-input-statement_date").fill("01 Oct 2026");
  await page.getByTestId("correct-save-statement_date").click();
  await expect(page.getByTestId("field-statement_date")).toContainText("01 Oct 2026");
  await page.getByTestId("copy-statement_date").click();
  expect(await clipboard(page)).toBe("01 Oct 2026");
});
