import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { fileLink, jobRow, uniqueName } from "./helpers";

async function download(page: Page, name: string) {
  await page.goto("/en");
  await page.getByLabel("Search or paste links").fill(fileLink(name, "size=4000"));
  await page.getByRole("button", { name: "Check link" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Download" }).click();
  await expect(jobRow(page, name)).toHaveAttribute("data-state", "done", { timeout: 15_000 });
}

test("library: finished downloads appear with a preview and tags", async ({ page }, testInfo) => {
  const image = uniqueName(testInfo, "photo", "jpg");
  const pdf = uniqueName(testInfo, "paper", "pdf");
  await download(page, image);
  await download(page, pdf);

  await page.goto("/en/library");
  const stem = image.replace(/\.jpg$/, "");
  await page.getByTestId("library-search").fill(stem);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  const card = page.getByTestId("library-item").filter({ hasText: stem });
  await expect(card).toHaveAttribute("data-kind", "image");
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);

  await card.click();
  const sheet = page.getByTestId("library-sheet");
  await expect(sheet.getByTestId("sheet-open")).toBeVisible(); // previews open in the viewer
  await sheet.getByLabel("Tags (comma separated)").fill(`e2e-${testInfo.project.name}`);
  await sheet.getByRole("button", { name: "Save tags" }).click();
  await expect(page.getByText("Tags saved")).toBeVisible();
  const withSheet = await new AxeBuilder({ page }).include("[role=dialog]").analyze();
  expect(withSheet.violations).toEqual([]);
  await page.keyboard.press("Escape");

  await page.getByTestId("library-search").fill(pdf.replace(/\.pdf$/, ""));
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page
    .getByTestId("library-item")
    .filter({ hasText: pdf.replace(/\.pdf$/, "") })
    .click();
  await page.getByTestId("library-sheet").getByTestId("sheet-open").click();
  // The fixture is random bytes named .pdf: the viewer says so instead of failing.
  await expect(page.getByTestId("viewer-fallback")).toHaveAttribute(
    "data-reason",
    "unsupported_format",
  );
});

test("watch: explains what can be watched and shows errors", async ({ page }) => {
  await page.goto("/en/watch");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Watches");
  await page.getByRole("button", { name: "Add watch" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Enter a link first");
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);
});

test("settings: saved values survive a reload; keys live in Connections", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "one browser changes shared settings");
  await page.goto("/en/settings");
  const template = page.getByTestId("folder-template");
  await template.fill("{type}");
  await expect(
    page.getByText("files/video.mp4").or(page.getByText("videos/video.mp4")),
  ).toBeVisible();
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.getByText("Settings saved")).toBeVisible();
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);

  await page.reload();
  await expect(page.getByTestId("folder-template")).toHaveValue("{type}");
  await expect(page.getByRole("link", { name: "Open Connections" })).toHaveAttribute(
    "href",
    "/en/connections",
  );
  // Put things back for the other tests.
  await page.getByTestId("folder-template").fill("");
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.getByText("Settings saved").first()).toBeVisible();
});

for (const path of ["/en/help", "/en/legal", "/ar/legal"]) {
  test(`${path} is readable and accessible`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    const axe = await new AxeBuilder({ page }).analyze();
    expect(axe.violations).toEqual([]);
  });
}
