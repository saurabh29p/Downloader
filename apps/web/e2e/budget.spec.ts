import { gzipSync } from "node:zlib";

import { expect, test } from "@playwright/test";

// CLAUDE.md budget: first-load JS under 170 KB gzip.
const BUDGET_KB = 170;

for (const path of [
  "/en",
  "/en/downloads",
  "/en/youtube",
  "/en/settings",
  "/en/archive",
  "/en/wayback",
]) {
  test(`first-load JS on ${path} stays under ${BUDGET_KB} KB gzip`, async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "measured once");
    const sizes = new Map<string, number>();
    page.on("response", async (response) => {
      if (!response.url().endsWith(".js")) return;
      try {
        sizes.set(response.url(), gzipSync(await response.body()).length);
      } catch {
        // aborted or redirected responses have no body
      }
    });
    await page.goto(path, { waitUntil: "networkidle" });
    await page.waitForTimeout(500);
    const totalKb = [...sizes.values()].reduce((a, b) => a + b, 0) / 1024;
    testInfo.annotations.push({ type: "first-load JS", description: `${totalKb.toFixed(1)} KB` });
    expect(totalKb).toBeLessThan(BUDGET_KB);
  });
}
