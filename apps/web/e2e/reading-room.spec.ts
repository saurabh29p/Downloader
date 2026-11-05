import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { fileLink, jobRow, uniqueName } from "./helpers";

const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

test("mode chips search inside a section", async ({ page }) => {
  await page.goto("/en");
  await page.locator("label", { hasText: /^Books$/ }).click();
  await page.getByLabel("Search or paste links").fill("Fixture Compass");
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page).toHaveURL(/\/en\/search\?q=Fixture\+Compass&section=books$/);
});

test("a link shows the check steps, then the preview", async ({ page }, testInfo) => {
  const name = uniqueName(testInfo, "steps");
  await page.goto("/en");
  await page.getByLabel("Search or paste links").fill(fileLink(name, "size=1000"));
  await page.getByRole("button", { name: "Check link" }).click();
  await expect(page.getByRole("dialog")).toContainText(name);
  await expect(page.getByTestId("link-steps")).toHaveAttribute("data-step", "ready");
});

test("removing a download can be undone", async ({ page }, testInfo) => {
  const name = uniqueName(testInfo, "removed");
  await page.goto("/en");
  await page
    .getByLabel("Search or paste links")
    .fill(`${fileLink(name, "size=1000")}\n${fileLink(`${name}.2`, "size=1000")}`);
  await page.getByRole("button", { name: "Queue 2 links" }).click();
  await page.goto("/en/downloads");
  const row = jobRow(page, name);
  await expect(row).toHaveAttribute("data-state", "done", { timeout: 15_000 });

  await row.getByRole("button", { name: `Remove from list: ${name}` }).click();
  await expect(row).toHaveCount(0);
  await page.getByTestId("toast").getByRole("button", { name: "Undo" }).click();
  await expect(row).toHaveAttribute("data-state", "done");

  await row.getByRole("button", { name: `Remove from list: ${name}` }).click();
  await expect(row).toHaveCount(0);
  await expect(page.getByTestId("toast").getByRole("button", { name: "Undo" })).toBeHidden({
    timeout: 8_000,
  });
  await page.reload();
  await expect(jobRow(page, `${name}.2`)).toBeVisible();
  await expect(jobRow(page, name)).toHaveCount(0); // deleted on the server once the toast ended
});

test("Settings is grouped; server details sit under Advanced", async ({ page }) => {
  await page.goto("/en/settings");
  const groups = page.getByRole("navigation", { name: "Settings sections" });
  for (const name of ["General", "Downloads", "AI helper", "Connections", "Advanced"]) {
    await expect(groups.getByRole("link", { name })).toBeVisible();
  }
  const advanced = page.locator("fieldset#advanced");
  await expect(advanced.getByText(/ANYGET_DOWNLOADS_DIR/)).toBeVisible();
  await expect(page.locator("fieldset#downloads").getByText(/ANYGET_/)).toHaveCount(0);
});

for (const path of ["/en/settings", "/en/library", "/en/sections/declassified", "/en/search"]) {
  test(`axe: ${path} has no violations (light and dark)`, async ({ page }) => {
    for (const scheme of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await page.waitForLoadState("networkidle").catch(() => undefined);
      const results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
      expect(results.violations).toEqual([]);
    }
  });
}
