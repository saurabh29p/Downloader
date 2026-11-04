import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("root redirects to English and shows the API as online", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/en$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Paste any link, get the file");
  await expect(page.getByTestId("api-status")).toHaveAttribute("data-state", "online");
});

test("API rewrite proxies /api/health", async ({ request }) => {
  const response = await request.get("/api/health");
  expect(response.ok()).toBeTruthy();
  expect(await response.json()).toEqual({ status: "ok" });
});

test("Arabic page is right-to-left", async ({ page }) => {
  await page.goto("/ar");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
});

test("language switcher changes the locale", async ({ page }) => {
  await page.goto("/en");
  await page.getByRole("link", { name: "हिन्दी" }).click();
  await expect(page).toHaveURL(/\/hi$/);
  await expect(page.locator("html")).toHaveAttribute("lang", "hi");
});

test("no horizontal scroll", async ({ page }) => {
  await page.goto("/en");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

for (const locale of ["en", "hi", "ar"]) {
  test(`axe: no accessibility violations (${locale})`, async ({ page }) => {
    await page.goto(`/${locale}`);
    await expect(page.getByTestId("api-status")).toHaveAttribute("data-state", "online");
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();
    expect(results.violations).toEqual([]);
  });
}
