// Day 8, ticket ENG-801: the MCP server checks every token.
import { expect, test } from "@playwright/test";

test("the Sign-in tab accepts Tom's token and refuses the other eight", async ({ page }) => {
  await page.goto("/#/integrations/signin");
  await expect(page.getByTestId("token-summary")).toContainText("9 of 9", { timeout: 20_000 });
  await expect(page.getByTestId("tprobe-T3")).toContainText("Wrong audience: crm");
  await expect(page.getByTestId("tprobe-T8")).toContainText("Algorithm not allowed: HS256");
});

test("a signed-in person reaches the bank through the MCP server", async ({ page }) => {
  await page.goto("/#/integrations/act");
  await page.getByTestId("act-person-helen.achebe").click();
  await page.getByTestId("act-exceptions").click();
  await expect(page.getByTestId("act-result")).toContainText("allowed", { timeout: 20_000 });
});
