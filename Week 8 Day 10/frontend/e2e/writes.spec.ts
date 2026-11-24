// Ticket ENG-1003: a crash right after a write does not make the write happen twice.
import { expect, test } from "@playwright/test";
import { approve, caseEnds, resetBank, signInWf, startCase } from "./fixtures/workflow";

test.beforeEach(async ({ request }) => { await resetBank(request); });

test("a crash right after the request is sent: KX-1004's applicant gets one request", async ({ page, request }) => {
  test.setTimeout(150_000);
  await signInWf(page);
  await request.post("/api/workflow/crash", { data: { point: "after_send_request", ticket: "KX-1004" } });
  await startCase(page, "KX-1004");
  await approve(page, "KX-1004");
  await expect(page.getByTestId("timeline-restart")).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId("case-state")).toHaveText("waiting for the applicant", { timeout: 30_000 });
  await expect(page.getByTestId("count-requests")).toContainText("1");
  await caseEnds(page, "escalated", 90_000);
  await expect(page.getByTestId("count-requests")).toContainText("1");
});

test("a crash right after CaseFlow confirms: KX-1001 has one outcome per round", async ({ page, request }) => {
  test.setTimeout(150_000);
  await signInWf(page);
  await request.post("/api/workflow/crash", { data: { point: "after_confirm", ticket: "KX-1001" } });
  await startCase(page, "KX-1001");
  await approve(page, "KX-1001");
  await expect(page.getByTestId("timeline-restart")).toBeVisible({ timeout: 45_000 });
  await expect(page.getByTestId("count-outcomes")).toContainText("1", { timeout: 30_000 });
  await approve(page, "KX-1001");
  await caseEnds(page, "completed");
  await expect(page.getByTestId("count-outcomes")).toContainText("2");
  await expect(page.getByTestId("count-comments")).toContainText("2");
});
