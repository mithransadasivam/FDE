// The whole UC1 prototype, after the three tickets (ENG-301, 302, 303) are merged. Real backend, scripted model.
import { expect, test } from "@playwright/test";

test("a doubtful date is accepted by the analyst, then the document is approved", async ({ page }) => {
  await page.goto("/#/cases/case/D03-001");
  await expect(page.getByTestId("box-statement_date")).toHaveAttribute("data-status", "check");
  await expect(page.getByTestId("check-date")).toHaveAttribute("data-status", "look");
  await expect(page.getByTestId("decide-approve")).toBeDisabled();
  await page.getByTestId("accept-statement_date").click();
  await expect(page.getByTestId("box-statement_date")).toHaveAttribute("data-status", "confirmed");
  await expect(page.getByTestId("check-date")).toHaveAttribute("data-status", "pass");
  await page.getByTestId("decide-approve").click();
  await expect(page.getByTestId("decision")).toContainText("Approved by TR-014");
});

test("a value the page does not show is replaced with what the page says", async ({ page }) => {
  await page.goto("/#/cases/case/D03-014");
  await expect(page.getByTestId("field-statement_date")).toContainText('The page says "30 Sep 2026"');
  await page.getByTestId("accept-statement_date").click();
  await expect(page.getByTestId("field-statement_date")).toContainText("30 Sep 2026");
  await expect(page.getByTestId("check-date")).toHaveAttribute("data-status", "pass");
});

test("a mobile phone bill fails the issuer rule, and the analyst asks the applicant", async ({ page }) => {
  await page.goto("/#/cases/case/D03-007");
  await expect(page.getByTestId("check-issuer")).toHaveAttribute("data-status", "fail");
  await page.getByTestId("decide-ask").click();
  await expect(page.getByTestId("reason-input")).toHaveValue("Pocketwave Mobile is not on the approved list");
  await page.getByTestId("confirm-decision").click();
  await expect(page.getByTestId("decision")).toContainText("Asked the applicant by TR-014");
});

test("the demo measures the prototype against the success criteria", async ({ page }) => {
  await page.goto("/#/cases/demo");
  await page.getByTestId("run-demo").click();
  await expect(page.getByTestId("accuracy")).toHaveText("97.5%");
  await expect(page.getByTestId("crit-SC1")).toHaveAttribute("data-status", "pilot");
  await expect(page.getByTestId("agree")).toHaveText("25 of 26");
});
