// Day 10: the Workflows screen and the worker. These pass from the start.
import { expect, test } from "@playwright/test";
import { caseEnds, resetBank, signInWf, startCase } from "./fixtures/workflow";

test.beforeEach(async ({ request }) => { await resetBank(request); });

test("Tom's exceptions and the worker are on the Workflows screen", async ({ page }) => {
  await signInWf(page);
  for (const t of ["KX-1001", "KX-1002", "KX-1003", "KX-1004"]) await expect(page.getByTestId(`start-${t}`)).toBeVisible();
  await expect(page.getByTestId("wf-tickets")).toContainText("ENG-1001");
});

test("a locked record ends the case: the agent stops and nothing is written", async ({ page }) => {
  test.setTimeout(90_000);
  await signInWf(page);
  await startCase(page, "KX-1003");
  await caseEnds(page, "stopped");
  await expect(page.getByTestId("count-outcomes")).toContainText("0");
  await expect(page.getByTestId("event-agent_ended")).toContainText('Repeating: click "Save"');
});

test("every write the workflow makes is listed with how it is made safe", async ({ page }) => {
  await signInWf(page);
  await page.getByTestId("wtab-crash").click();
  await expect(page.getByTestId("writes-table").locator("tbody tr")).toHaveCount(8);
  await expect(page.getByTestId("crash-points")).toContainText("after_send_request");
});
