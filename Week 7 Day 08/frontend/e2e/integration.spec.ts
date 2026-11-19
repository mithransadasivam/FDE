// Day 8: the Integrations screen and the bank's sign-in are in place. These pass from the start of Day 8.
import { expect, test } from "@playwright/test";

test("Integrations opens with the bank's sign-in service and the MCP server running", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("nav-integrations").click();
  await expect(page.getByTestId("int-bank")).toContainText("running", { timeout: 20_000 });
  await expect(page.getByTestId("int-mcp")).toContainText("running");
  await expect(page.getByTestId("claude-command")).toContainText("claude mcp add --transport http kestrelmoor-kyc");
});

test("Grace signs in to the console with the bank, and Ask the data answers as her", async ({ page }) => {
  await page.goto("/#/integrations/signin");
  await page.getByTestId("sign-in").click();
  await page.locator("#username").selectOption("grace.mensah");
  await page.locator("#password").fill("kyc-demo");
  await page.locator("#signin").click();
  await expect(page.getByTestId("me-name")).toHaveText("Grace Mensah", { timeout: 20_000 });
  await page.getByTestId("nav-ask").click();
  await expect(page.getByTestId("ask-locked")).toContainText("Grace Mensah");
  await expect(page.getByTestId("user-tom.reyes")).toHaveCount(0);
});

test("a wrong password stays on the bank's page", async ({ page }) => {
  await page.goto("/#/integrations/signin");
  await page.getByTestId("sign-in").click();
  await page.locator("#password").fill("guess");
  await page.locator("#signin").click();
  await expect(page.locator("#signin-error")).toHaveText("Wrong user or password");
});
