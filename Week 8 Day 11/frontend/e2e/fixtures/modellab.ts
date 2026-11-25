// Helpers for the Day 11 end-to-end tests: train a small model through the API, open a Model lab tab.
import { expect, type APIRequestContext, type Page } from "@playwright/test";

export async function train(request: APIRequestContext, readFiles: string[] = ["pilot"], name?: string) {
  const r = await request.post("/api/distil/train", { data: { read_files: readFiles, name }, timeout: 90_000 });
  expect(r.ok()).toBeTruthy();
  return (await r.json()) as { name: string; kept: number; skipped: number; october: { accuracy: number } };
}

export async function openTab(page: Page, tab: "train" | "read" | "cascade" | "scale" | "drift", rest = "") {
  await page.goto(`/#/modellab/${tab}${rest}`);
  await expect(page.getByTestId(`mtab-${tab}`)).toBeVisible();
}
