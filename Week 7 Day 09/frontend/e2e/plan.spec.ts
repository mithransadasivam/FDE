// Ticket ENG-502: the bank's rules on the Terraform plan, on Pilot → Infrastructure.
// The end-to-end backend reads tests/fixtures/pilot/plan_start.json: the first plan, before the fix on slide 15.
import { expect, test } from "@playwright/test";

test("eight rules, and the first plan breaks only the model rule", async ({ page }) => {
  await page.goto("/#/pilot/infrastructure");
  await expect(page.getByTestId("rules").locator('[data-testid^="rule-"]')).toHaveCount(8);
  await expect(page.getByTestId("rule-model_in_region")).toHaveAttribute("data-ok", "false");
  await expect(page.getByTestId("rule-private_model")).toHaveAttribute("data-ok", "true");
  await expect(page.getByTestId("rule-model_in_region")).toContainText("eu.anthropic.claude-haiku-5-5");
});

test("the diagram marks the box that breaks the rule", async ({ page }) => {
  await page.goto("/#/pilot/infrastructure");
  await expect(page.getByTestId("node-bedrock")).toHaveAttribute("data-bad", "true");
  await expect(page.getByTestId("node-ep-bedrock")).toHaveAttribute("data-bad", "false");
  await expect(page.getByTestId("diagram")).toContainText("7 of 8 rules met");
});
