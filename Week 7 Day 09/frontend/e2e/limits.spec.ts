// Day 9, ticket ENG-902: a run stops before it goes on too long, costs too much, or goes round in circles.
import { expect, test } from "@playwright/test";
import { runOne, signIn } from "./fixtures/agent";

test("on KX-1003, locked by Priya Nair, the run stops at the third Save", async ({ page }) => {
  test.setTimeout(90_000);
  await signIn(page, "tom.reyes");
  await runOne(page, "KX-1003");
  await expect(page.getByTestId("run-status")).toContainText("stopped");
  await expect(page.getByTestId("run-stop")).toContainText('Repeating: click "Save" 3 times in a row');
  await expect(page.getByTestId("run-limits")).toContainText("14 steps");
});

test("the screen shows ENG-902 as built", async ({ page }) => {
  await signIn(page, "tom.reyes");
  await expect(page.getByTestId("ticket-ENG-902")).not.toContainText("not built");
});
