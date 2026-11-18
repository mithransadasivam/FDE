// Day 7, ticket ENG-702: row security for Tom (his team), Grace (her region) and Helen (all, no names).
import { expect, test } from "@playwright/test";

test("the Row security tab shows every check as expected, with no leaks", async ({ page }) => {
  await page.goto("/#/data/rows");
  await expect(page.getByTestId("rls-R01")).toContainText("4,199", { timeout: 20_000 });
  await expect(page.getByTestId("rls-R07")).toContainText("[hidden]");
  await expect(page.getByText("30 of 30")).toBeVisible();
});

test("Tom cannot talk his way past row security", async ({ page }) => {
  await page.goto("/#/ask");
  await page.getByTestId("user-tom.reyes").click();
  await page.getByTestId("suggest-X02").click();
  await expect(page.getByTestId("answer-value")).toContainText("4,199", { timeout: 20_000 });
  await expect(page.getByTestId("answer-scope")).toContainText("Only North 1's cases");
  await page.getByTestId("show-secured").click();
  await expect(page.getByTestId("secured-1")).toContainText("team_id IN ('N1')");
});

test("Helen sees every team's cases but no customer names", async ({ page }) => {
  await page.goto("/#/ask");
  await page.getByTestId("user-helen.achebe").click();
  await page.getByTestId("suggest-X03").click();
  await expect(page.getByTestId("answer-table")).toContainText("[hidden]", { timeout: 20_000 });
  await expect(page.getByTestId("answer-scope")).toContainText("All teams' cases");
});
