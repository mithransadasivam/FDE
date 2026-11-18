// Ticket ENG-401: agreement with the expert, for labels and for judges.
import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

const labels: Record<string, string> = JSON.parse(readFileSync("../backend/tests/fixtures/labels_student_v0.json", "utf-8"));

test("labels compared with Tom: percent agreement and kappa", async ({ page }) => {
  await page.goto("/#/evaluation/labelling");
  for (const [item, label] of Object.entries(labels)) await page.getByTestId(`${label}-${item}`).click();
  await expect(page.getByTestId("progress")).toHaveText("20 of 20");
  await page.getByTestId("compare").click();
  await expect(page.getByTestId("not-built")).toHaveCount(0);
  await expect(page.getByTestId("percent")).toHaveText("75%");
  await expect(page.getByTestId("kappa")).toHaveText("0.31");
  await expect(page.getByTestId("rounds")).toContainText("Round 1");
});

test("a judge is calibrated against Tom's tags", async ({ page }) => {
  await page.goto("/#/evaluation/judges");
  await page.getByTestId("prompt-wrong_date").click();
  await page.getByTestId("run-wrong_date").click();
  await expect(page.getByTestId("kappa-wrong_date")).toHaveText("0.69");
  await expect(page.getByTestId("caught-wrong_date")).toHaveText("0.8");
  await expect(page.getByTestId("judge-wrong_date").getByTestId("judge-disagreement")).toHaveCount(3);
});
