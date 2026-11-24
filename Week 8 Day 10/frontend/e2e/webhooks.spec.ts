// Day 8, ticket ENG-803: only genuine, fresh, first deliveries reach Slack.
import { expect, test } from "@playwright/test";

test("of the six deliveries, only the genuine one is accepted", async ({ page }) => {
  await page.goto("/#/integrations/webhooks");
  await page.getByTestId("probes-go").click();
  await expect(page.getByTestId("webhook-summary")).toContainText("6 of 6", { timeout: 30_000 });
  await expect(page.getByTestId("wprobe-W4")).toContainText("Bad signature");
  await expect(page.getByTestId("wprobe-W6")).toContainText("Already received");
});

test("a new escalation in South 1 reaches #kyc-south and #financial-crime", async ({ page }) => {
  await page.goto("/#/integrations/webhooks");
  await page.getByTestId("raise-team").selectOption("S1");
  await page.getByTestId("raise-go").click();
  await page.getByTestId("chan-kyc-south").click();
  await expect(page.getByTestId("slack-messages")).toContainText("South 1", { timeout: 20_000 });
  await page.getByTestId("chan-financial-crime").click();
  await expect(page.getByTestId("slack-messages")).toContainText("Escalated document");
});
