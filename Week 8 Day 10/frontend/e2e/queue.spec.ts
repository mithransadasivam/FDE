// Day 9, Activity 4: Tom's queue, start to end, with Tom approving or rejecting each write.
import { expect, test } from "@playwright/test";
import { signIn } from "./fixtures/agent";

test("Tom's four exceptions end as the bank expects", async ({ page }) => {
  test.setTimeout(180_000);
  await signIn(page, "tom.reyes");
  await page.getByTestId("dtab-queue").click();
  await page.getByTestId("queue-go").click();
  for (const [t, d] of [["KX-1001", "approve"], ["KX-1002", "reject"], ["KX-1004", "approve"]] as const) {
    await page.getByTestId(`${d}-${t}`).click({ timeout: 60_000 });
  }
  await expect(page.getByTestId("queue-summary")).toContainText("4 of 4", { timeout: 60_000 });
  await expect(page.getByTestId("queue-row-KX-1003")).toContainText('Repeating: click "Save"');
});
