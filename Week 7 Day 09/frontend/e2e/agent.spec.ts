// Day 9: the Agent runs screen and CaseFlow Classic. These pass from the start of the day.
import { expect, test } from "@playwright/test";
import { runOne, signIn } from "./fixtures/agent";

test("the agent works as the person signed in, on their own exceptions", async ({ page }) => {
  await page.goto("/#/agent/run");
  await expect(page.getByTestId("agent-signin")).toBeVisible();
  await signIn(page, "tom.reyes");
  await expect(page.getByTestId("my-exceptions")).toContainText("KX-1004");
  await expect(page.getByTestId("my-exceptions")).not.toContainText("KX-1005");
  await expect(page.getByTestId("agent-limits")).toContainText("25 steps");
});

test("the agent works KX-1001 to an outcome in CaseFlow Classic, as Tom", async ({ page }) => {
  test.setTimeout(90_000);
  await signIn(page, "tom.reyes");
  await runOne(page, "KX-1001", "approve");
  await expect(page.getByTestId("run-status")).toContainText("recorded");
  await expect(page.getByTestId("run-outcome")).toContainText("Request more information (R02)");
  await expect(page.getByTestId("run-reference")).toContainText("OUT-");
  await expect(page.getByTestId("caseflow-log")).toContainText("tom.reyes via fde-mcp", { timeout: 10_000 });
  await page.getByTestId("step-4").click();
  await expect(page.getByTestId("run-shot").locator("img")).toBeVisible();
});

test("CaseFlow Classic has its own sign-in, and no API", async ({ page }) => {
  await page.goto("http://localhost:8110/legacy");
  await page.locator("#user").selectOption("grace.mensah");
  await page.locator("#pw").fill("kyc-demo");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Main menu" })).toBeVisible();
  await page.getByRole("link", { name: "Find a case" }).click();
  await page.getByLabel("Case reference").fill("KC-021805");
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page.getByRole("heading", { name: "Case KC-021805" })).toBeVisible();
});
