// Day 5: the Pilot screen is in place. These pass from the start of Day 5.
import { expect, test } from "@playwright/test";

test("Pilot opens from the sidebar, with the model's routing", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("nav-pilot").click();
  await expect(page.getByTestId("model-id")).toHaveText("anthropic.claude-sonnet-5");
  await expect(page.getByTestId("residency")).toHaveAttribute("data-ok", "true");
  await expect(page.getByTestId("models").locator('[data-testid^="model-"]')).toHaveCount(4);
});

test("guardrail v1 lets the hidden instruction through and breaks an ordinary bill", async ({ page }) => {
  await page.goto("/#/pilot/guardrails");
  await page.getByTestId("probe-uc1_v1").click();
  await expect(page.getByTestId("probe-uc1_v1-P-001")).toHaveAttribute("data-verdict", "bad");
  await expect(page.getByTestId("probe-uc1_v1-P-003")).toHaveAttribute("data-verdict", "bad");
});

test("the budget and the teardown reminder", async ({ page }) => {
  await page.goto("/#/pilot/spend");
  await expect(page.getByTestId("spend-kpis")).toContainText("USD 20");
  await expect(page.getByTestId("teardown")).toContainText("terraform destroy");
});
