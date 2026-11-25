// Activity 4: the month at the bank's volumes, after the three tickets.
import { expect, test } from "@playwright/test";
import { openTab, train } from "./fixtures/modellab";

test("in the remediation the cascade costs less a month than the pilot alone, with no more errors", async ({ page, request }) => {
  test.setTimeout(120_000);
  await train(request);
  await request.post("/api/distil/cascade", { data: { set: "october", threshold: 0.7, spot: 5 }, timeout: 90_000 });
  await openTab(page, "scale");
  await expect(page.getByTestId("scale-table")).toBeVisible({ timeout: 90_000 });
  await expect(page.getByTestId("scale-kpis")).toContainText("2 vs 3");
  const cost = (t: string) => Number(t.replace(/[£,]/g, ""));
  expect(cost(await page.getByTestId("remediation-total").innerText())).toBeLessThan(7971);
});
