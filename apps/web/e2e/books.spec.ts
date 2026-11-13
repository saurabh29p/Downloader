import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { FIXTURE, jobRow, uniqueName } from "./helpers";

test("books: the best legal copy is on top and downloads", async ({ page }, testInfo) => {
  const title = uniqueName(testInfo, "Fixture Novel", "x").replace(/\.x$/, "");
  const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, "-");
  await page.goto("/en/books");
  await page.getByRole("button", { name: "Find books" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Enter a title");

  await page.getByTestId("books-query").fill(title);
  await page.getByRole("button", { name: "Find books" }).click();
  const best = page.getByTestId("best-copy");
  await expect(best).toContainText(title);
  await expect(best).toContainText("Best legal copy");
  await expect(best).toContainText("Free to download");
  await expect(page.getByTestId("source-status")).toContainText("1 of 1 sources answered");
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);

  await best.getByRole("button", { name: `Download EPUB: ${title}` }).click();
  await expect(page.getByText("Added 1 download")).toBeVisible();
  await page.goto("/en/downloads");
  await expect(jobRow(page, `${slug}.epub`)).toHaveAttribute("data-state", "done", {
    timeout: 15_000,
  });
});

test("libraries: regions, then a IIIF item's pages", async ({ page }, testInfo) => {
  const tag = uniqueName(testInfo, "album", "x")
    .replace(/\.x$/, "")
    .replace(/[^\w-]/g, "-");
  await page.goto("/en/libraries");
  const list = page.getByTestId("library-list");
  await expect(list).toContainText("Internet Archive");
  await page.locator("label", { hasText: "Asia" }).click();
  await expect(list).toContainText("National Diet Library");
  await page.locator("label", { hasText: "Oceania" }).click();
  await expect(list).toContainText("Trove");
  // Libraries that need a key link to their Connections entry, not to an env variable.
  await expect(list.locator('a[href="/en/connections#trove"]')).toHaveText("Add it in Connections");
  await expect(list).not.toContainText("ANYGET_");
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);

  await page.getByTestId("library-item-url").fill(`${FIXTURE}/iiif/${tag}/manifest.json`);
  await page.getByRole("button", { name: "Find pages" }).click();
  const picker = page.getByTestId("file-picker");
  await expect(picker.getByTestId("file-choice")).toHaveCount(3);
  await expect(picker.locator("img")).toHaveCount(3);
  await page.getByLabel("Also merge the pages into one PDF").uncheck();
  await page.getByRole("button", { name: "Download 3 files" }).click();
  await expect(page.getByText("Added 1 download")).toBeVisible();
});

test("search: results stream in as cards, with licence and download", async ({ page }) => {
  await page.goto("/en/search");
  await expect(page.getByText("Results appear here")).toBeVisible();
  await page.getByTestId("search-query").fill("Fixture Compass");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  const card = page.getByTestId("result-card").first();
  await expect(card).toContainText("Fixture Compass");
  await expect(card).toContainText("Public domain");
  await expect(page).toHaveURL(/q=Fixture\+Compass/);
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);
  await card.getByRole("button", { name: "Download" }).click();
  await expect(page.getByText("Added 1 download")).toBeVisible();
});

test("home: typing words instead of a link searches everything", async ({ page }) => {
  await page.goto("/en");
  await page.getByLabel("Search or paste links").fill("Fixture Compass");
  await page.getByRole("button", { name: "Search" }).click();
  await expect(page).toHaveURL(/\/en\/search\?q=Fixture/);
  await expect(page.getByTestId("result-card").first()).toContainText("Fixture Compass");
});
