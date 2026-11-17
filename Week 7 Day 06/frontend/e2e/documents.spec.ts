// Day 6: the Pipeline and Review queue screens are in place. These pass from the start of Day 6.
import { expect, test } from "@playwright/test";

test("Pipeline opens from the sidebar with the October batch", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("nav-pipeline").click();
  await expect(page.getByTestId("parse-kpis")).toContainText("200", { timeout: 20_000 });
  await expect(page.getByTestId("parse-kpis")).toContainText("120 PDF · 80 JPG");
});

test("Compare shows the bank's own bar and a run button for each prompt", async ({ page }) => {
  await page.goto("/#/pipeline/compare");
  await expect(page.getByTestId("human-bar")).toContainText("98.6%");
  await expect(page.getByTestId("run-extract_v2")).toBeVisible();
  await expect(page.getByTestId("run-extract_vlm_v0")).toBeVisible();
});

test("the Review queue opens from the client workspace", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("nav-queue").click();
  await expect(page.getByTestId("queue-progress")).toBeVisible();
});
