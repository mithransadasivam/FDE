// Day 8, ticket ENG-802: the MCP server calls the bank as the person, never as the console.
import { expect, test } from "@playwright/test";

test("Tom sees North 1's twelve customers, and the CRM records Tom via the MCP server", async ({ page }) => {
  await page.goto("/#/integrations/act");
  await page.getByTestId("act-person-tom.reyes").click();
  await page.getByTestId("act-customers").click();
  await expect(page.getByTestId("act-count")).toContainText("12", { timeout: 20_000 });
  await expect(page.getByTestId("audit-table")).toContainText("tom.reyes via fde-mcp");
});

test("the CRM refuses Helen's note in her own name", async ({ page }) => {
  await page.goto("/#/integrations/act");
  await page.getByTestId("act-person-helen.achebe").click();
  await page.getByTestId("act-note").click();
  await expect(page.getByTestId("act-error")).toContainText("read-only", { timeout: 20_000 });
});
