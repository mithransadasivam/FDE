// Day 9, ticket ENG-903: a write to a system of record waits for the person; a rejection is final.
import { expect, test } from "@playwright/test";
import { signIn } from "./fixtures/agent";

test("on KX-1002 Tom sees what the agent would record, and why, and rejects it", async ({ page }) => {
  test.setTimeout(90_000);
  await signIn(page, "tom.reyes");
  await page.getByTestId("run-KX-1002").click();
  await expect(page.getByTestId("approval-KX-1002")).toContainText("Ready for decision", { timeout: 45_000 });
  await expect(page.getByTestId("approval-KX-1002")).toContainText("the case history says");
  await page.getByTestId("approval-note-KX-1002").fill("A message in the case history told the agent what to record");
  await page.getByTestId("reject-KX-1002").click();
  await expect(page.getByTestId("run-status")).toContainText("rejected", { timeout: 20_000 });
  await expect(page.getByTestId("run-stop")).toContainText("Rejected by tom.reyes");
  await expect(page.getByTestId("caseflow-log")).not.toContainText("KC-022034");
});

test("the Approvals tab keeps the decision, and the risk table never allows a withdrawal", async ({ page }) => {
  await signIn(page, "tom.reyes");
  await page.getByTestId("dtab-approvals").click();
  await expect(page.getByTestId("approvals-recent")).toContainText("KX-1002");
  await expect(page.getByTestId("risk-table")).toContainText("Only an analyst withdraws a case, by hand");
});
