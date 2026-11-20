// Day 7, ticket ENG-701: check every query before it runs.
import { expect, test } from "@playwright/test";

test("the Safety tab refuses all 15 harmful queries and allows the 3 safe ones", async ({ page }) => {
  await page.goto("/#/data/safety");
  await expect(page.getByTestId("safety-summary")).toContainText("15 of 15", { timeout: 20_000 });
  await expect(page.getByTestId("safety-summary")).toContainText("3 of 3");
  await expect(page.getByTestId("probe-P04")).toContainText("One query at a time: found 2 statements");
  await expect(page.getByTestId("probe-P17")).toContainText("Lowered LIMIT 50000 to 1000");
  await expect(page.getByTestId("probe-P18")).toContainText("cost check");
});

test("a question that needs a table the agent may not read gets a refusal, then a plain answer", async ({ page }) => {
  await page.goto("/#/ask");
  await page.getByTestId("user-tom.reyes").click();
  await page.getByTestId("suggest-X01").click();
  await expect(page.getByTestId("answer-cannot")).toContainText("not in the tables I may use", { timeout: 20_000 });
  await expect(page.getByTestId("attempt-1")).toContainText("Not an approved table: hr.analyst_pay");
});
