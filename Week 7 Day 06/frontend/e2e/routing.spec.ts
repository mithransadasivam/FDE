// Day 6, ticket ENG-602: route each field by confidence and by agreement between the two methods.
import { expect, test } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  await request.post("/api/pipeline/run", { data: { set: "october", prompts: ["extract_v2", "extract_vlm_v1"], concurrency: 8 }, timeout: 60_000 });
});

test("agreement catches the confident wrong dates that confidence alone lets through", async ({ page }) => {
  await page.goto("/#/pipeline/routing");
  await page.getByTestId("vision-prompt").selectOption("extract_vlm_v1");
  await expect(page.getByTestId("routing-kpis")).toContainText("10.9%", { timeout: 20_000 });
  await expect(page.getByTestId("routing-kpis")).toContainText("99.6%");
  await page.getByTestId("use-agreement").uncheck();
  await expect(page.getByTestId("routing-kpis")).toContainText("6.8%");
  await expect(page.getByTestId("slipped")).toContainText("The 20 errors");
  await page.getByTestId("use-agreement").check();
  await expect(page.getByTestId("slipped")).toContainText("The 3 errors");
});

test("an analyst checks a field in the Review queue", async ({ page }) => {
  await page.goto("/#/pipeline/routing");
  await page.getByTestId("vision-prompt").selectOption("extract_vlm_v1");
  await expect(page.getByTestId("routing-kpis")).toContainText("10.9%", { timeout: 20_000 });
  await page.goto("/#/queue");
  await expect(page.getByTestId("queue-progress")).toContainText("of 87 checked");
  await page.getByTestId("q-accept").click();
  await expect(page.getByTestId("queue-progress")).toContainText("1");
  await page.getByTestId("queue-done").or(page.getByTestId("queue-open")).first().waitFor();
});

test("16 calls at once hits the rate limit; 8 finishes all 200", async ({ page }) => {
  await page.goto("/#/pipeline/batch");
  await page.getByTestId("conc-16").click();
  await page.getByTestId("run-batch").click();
  await expect(page.getByTestId("batch-report")).toContainText("need running again", { timeout: 20_000 });
  await page.getByTestId("conc-8").click();
  await page.getByTestId("run-batch").click();
  await expect(page.getByTestId("batch-report")).toContainText("200 of 200", { timeout: 20_000 });
  await expect(page.getByTestId("batch-history")).toBeVisible();
});
