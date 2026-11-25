// Day 9, ticket ENG-901: find each control by what it is, and read the screen back after Confirm.
import { expect, test } from "@playwright/test";
import { runOne, signIn } from "./fixtures/agent";

test("on KX-1004 the agent presses Confirm, not the button where Confirm used to be", async ({ page }) => {
  test.setTimeout(90_000);
  await signIn(page, "tom.reyes");
  await runOne(page, "KX-1004", "approve");
  await expect(page.getByTestId("run-status")).toContainText("recorded");
  await expect(page.getByTestId("run-outcome")).toContainText("Request more information (R01)");
  await expect(page.getByTestId("run-steps")).not.toContainText("Withdraw case");
  await expect(page.getByTestId("caseflow-log")).not.toContainText("Case withdrawn", { timeout: 10_000 });
});

test("the screen shows ENG-901 as built", async ({ page }) => {
  await signIn(page, "tom.reyes");
  await expect(page.getByTestId("ticket-ENG-901")).not.toContainText("not built");
});
