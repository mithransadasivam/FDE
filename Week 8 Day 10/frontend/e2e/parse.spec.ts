// Day 6, ticket ENG-601: every document parsed, digital PDFs from their text layer, scans from the bank's OCR.
import { expect, test } from "@playwright/test";

test("the Parse tab counts 108 text layers and 92 OCR files", async ({ page }) => {
  await page.goto("/#/pipeline/parse");
  await expect(page.getByTestId("parse-kpis")).toContainText("108", { timeout: 20_000 });
  await expect(page.getByTestId("parse-kpis")).toContainText("12 PDFs with no text layer");
  await page.getByTestId("filter-scanned_pdf").click();
  await expect(page.getByTestId("doc-table").locator('[data-testid^="doc-B-"]')).toHaveCount(12);
});

test("a run of the first vision prompt shows what reformatting does", async ({ page }) => {
  await page.goto("/#/pipeline/compare");
  await page.getByTestId("run-extract_vlm_v0").click();
  await expect(page.getByTestId("cmp-extract_vlm_v0")).toContainText("73.4%", { timeout: 20_000 });
});
