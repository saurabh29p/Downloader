import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { FIXTURE, fileLink } from "./helpers";

// Every page, light and dark, phone and desktop, with all axe rules (WCAG and best
// practices). Downloads and the Library get a finished and a failed job first, so
// row-level problems (headings, long error text) are checked too.
const PAGES = [
  "/en",
  "/en/downloads",
  "/en/library",
  "/en/search?q=Fixture",
  "/en/sections",
  "/en/sections/movies",
  "/en/youtube",
  "/en/archive",
  "/en/wayback",
  "/en/code",
  "/en/images",
  "/en/books",
  "/en/libraries",
  "/en/watch",
  "/en/connections",
  "/en/settings",
  "/en/help",
  "/en/legal",
  "/en/login",
  "/ar",
  "/ar/downloads",
  "/ar/settings",
  "/hi/legal",
];

test.beforeAll(async ({ playwright }, testInfo) => {
  const request = await playwright.request.newContext({ baseURL: testInfo.project.use.baseURL });
  const tag = `${testInfo.project.name}-${testInfo.workerIndex}-${Date.now().toString(36)}`;
  const response = await request.post("/api/jobs", {
    headers: { "X-Requested-With": "anyget" },
    data: { urls: [fileLink(`axe-${tag}.bin`, "size=2048"), `${FIXTURE}/nope/axe-${tag}.bin`] },
  });
  expect(response.ok()).toBeTruthy();
  await expect
    .poll(async () => {
      const jobs: { url: string; state: string }[] = await (await request.get("/api/jobs")).json();
      return jobs.filter(
        (j) => j.url.includes(`axe-${tag}`) && ["done", "failed"].includes(j.state),
      ).length;
    })
    .toBe(2);
  await request.dispose();
});

for (const path of PAGES) {
  test(`axe (all rules): ${path} in light and dark`, async ({ page }) => {
    for (const scheme of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await page.waitForLoadState("networkidle").catch(() => undefined);
      const results = await new AxeBuilder({ page }).analyze();
      expect(results.violations, `${scheme} ${path}`).toEqual([]);
    }
  });
}
