// Ticket ENG-1002: the chase keeps its clock through a crash.
import { expect, test } from "@playwright/test";
import { approve, caseEnds, crashNow, messageDay, resetBank, signInWf, startCase } from "./fixtures/workflow";

test.beforeEach(async ({ request }) => { await resetBank(request); });

test("a crash on day 2 of KX-1004's wait: the reminder still goes on day 3, the escalation on day 7", async ({ page }) => {
  test.setTimeout(150_000);
  await signInWf(page);
  await startCase(page, "KX-1004");
  await approve(page, "KX-1004");
  await expect(page.getByTestId("case-state")).toHaveText("waiting for the applicant", { timeout: 45_000 });
  const asked = await messageDay(page, "request");
  await expect.poll(async () => Number(await page.getByTestId("case-day").innerText()), { timeout: 30_000 }).toBeGreaterThanOrEqual(asked + 2);
  await crashNow(page);
  await caseEnds(page, "escalated", 90_000);
  const reminded = await messageDay(page, "reminder");
  expect(reminded - asked, "the reminder is due 3 days after the request, crash or no crash").toBeLessThanOrEqual(3.9);
  await expect(page.getByTestId("count-reminders")).toContainText("1");
  await expect(page.getByTestId("count-escalations")).toContainText("1");
});

test("KX-1002's applicant replies on day 5, after the reminder: the case is worked again", async ({ page }) => {
  test.setTimeout(150_000);
  await signInWf(page);
  await startCase(page, "KX-1002");
  await approve(page, "KX-1002");
  await expect(page.getByTestId("event-documents")).toBeVisible({ timeout: 60_000 });
  await approve(page, "KX-1002");
  await caseEnds(page, "completed");
  await expect(page.getByTestId("count-reminders")).toContainText("1");
  await expect(page.getByTestId("case-outcomes")).toContainText("Ready for decision");
});
