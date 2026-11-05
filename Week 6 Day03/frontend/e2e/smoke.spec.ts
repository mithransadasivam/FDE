// Works from the start: the console runs and the question plan can be drafted.
import { expect, test } from "@playwright/test";

test("the console opens on the client brief", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Discovery: Kestrelmoor Bank" })).toBeVisible();
  await expect(page.getByTestId("brief")).toContainText("AI for onboarding");
});

test("a question plan is drafted and questions can be starred", async ({ page }) => {
  await page.goto("/#/discovery/questions");
  await page.getByTestId("draft-questions").click();
  await expect(page.locator('[data-testid^="question-Q"]')).toHaveCount(15);
  await page.getByTestId("question-Q04").getByRole("button", { name: "star" }).click();
  await expect(page.getByTestId("starred-count")).toContainText("1 / 8");
});
