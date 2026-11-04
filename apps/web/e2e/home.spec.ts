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
  const body = await response.json();
  expect(body.status).toBe("ok");
  expect(body.components).toHaveProperty("yt_dlp");
});

test("Arabic page is right-to-left", async ({ page }) => {
  await page.goto("/ar/downloads");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("التنزيلات");
});

test("language menu keeps the current page", async ({ page }) => {
  await page.goto("/en/downloads");
  await page.getByRole("combobox", { name: "Language" }).selectOption("hi");
  await expect(page).toHaveURL(/\/hi\/downloads$/);
  await expect(page.locator("html")).toHaveAttribute("lang", "hi");
});

test("theme choice applies and survives a reload", async ({ page }) => {
  await page.goto("/en");
  await page.getByRole("combobox", { name: "Theme" }).selectOption("dark");
  await expect(page.locator("html")).toHaveClass(/\bdark\b/);
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/\bdark\b/);
});

test("navigation works and marks the current page", async ({ page }) => {
  await page.goto("/en");
  await page
    .getByRole("navigation", { name: "Main" })
    .getByRole("link", { name: /Downloads/ })
    .click();
  await expect(page).toHaveURL(/\/en\/downloads$/);
  await expect(
    page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: /Downloads/ }),
  ).toHaveAttribute("aria-current", "page");
});

for (const path of ["/en", "/en/downloads"]) {
  test(`no horizontal scroll on ${path}`, async ({ page }) => {
    await page.goto(path);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
  });
}

const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

for (const locale of ["en", "hi", "ar"]) {
  for (const page_ of ["", "/downloads"]) {
    test(`axe: ${locale}${page_ || "/"} has no violations`, async ({ page }) => {
      await page.goto(`/${locale}${page_}`);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await page.waitForLoadState("networkidle").catch(() => undefined);
      const results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
      expect(results.violations).toEqual([]);
    });
  }
}

test("axe: dark theme has no violations", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/en");
  await expect(page.getByTestId("api-status")).toHaveAttribute("data-state", "online");
  const results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
  expect(results.violations).toEqual([]);
});
