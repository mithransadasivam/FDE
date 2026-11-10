// Ticket ENG-501: the Bedrock client, checked offline on Pilot → Platform.
import { expect, test } from "@playwright/test";

test("the offline check shows the Converse request", async ({ page }) => {
  await page.goto("/#/pilot/platform");
  await page.getByTestId("selftest").click();
  const req = page.getByTestId("request");
  await expect(req).toContainText('"modelId": "anthropic.claude-sonnet-5"');
  await expect(req).toContainText('"temperature": 0');
  await expect(req).toContainText('"guardrailIdentifier"');
});

test("the reply is parsed and its usage recorded", async ({ page }) => {
  await page.goto("/#/pilot/platform");
  await page.getByTestId("selftest").click();
  await expect(page.getByTestId("selftest-result")).toContainText("4 fields parsed");
  await expect(page.getByTestId("selftest-result")).toContainText("1184 input");
});
