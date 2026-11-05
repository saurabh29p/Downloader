import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import item from "../test/fixtures/archive-item.json" with { type: "json" };
import lent from "../test/fixtures/archive-lent.json" with { type: "json" };
import search from "../test/fixtures/archive-search.json" with { type: "json" };
import snapshots from "../test/fixtures/wayback-snapshots.json" with { type: "json" };

const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
type JobsBody = { urls?: string[]; options: Record<string, unknown> };

/** archive.org and the Wayback Machine are not reachable in tests: mock the API. */
async function mockArchive(page: Page) {
  const sent: JobsBody[] = [];
  const searches: URL[] = [];
  await page.route("**/api/archive/search**", (route) => {
    searches.push(new URL(route.request().url()));
    return route.fulfill({ json: search });
  });
  await page.route("**/api/archive/items/alicesadventures00gut", (route) =>
    route.fulfill({ json: item }),
  );
  await page.route("**/api/archive/items/lentbook00", (route) => route.fulfill({ json: lent }));
  await page.route("**/api/wayback/snapshots**", (route) => route.fulfill({ json: snapshots }));
  await page.route("**/api/jobs", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    sent.push(route.request().postDataJSON() as JobsBody);
    await route.fulfill({ status: 201, json: { jobs: [], rejected: [], skipped: [] } });
  });
  return { sent, searches };
}

test("archive.org: search with filters, open an item, pick files by format, download", async ({
  page,
}) => {
  const { sent, searches } = await mockArchive(page);
  await page.goto("/en/archive");
  await page.getByTestId("archive-q").fill("alice");
  await page.getByText("Filters").click();
  await page.getByLabel("Type").selectOption("texts");
  await page.getByLabel("From year").fill("1860");
  await page.getByRole("button", { name: "Search" }).click();

  await expect(page.getByTestId("archive-results").getByRole("listitem")).toHaveCount(2);
  expect(searches.at(-1)!.searchParams.get("mediatype")).toBe("texts");
  expect(searches.at(-1)!.searchParams.get("year_from")).toBe("1860");

  await page.getByRole("button", { name: /Alice's Adventures/ }).click();
  const itemView = page.getByTestId("archive-item");
  await expect(itemView.getByTestId("archive-file")).toHaveCount(3);
  await expect(itemView.getByText("1 file selected", { exact: false })).toBeVisible(); // Text PDF pre-selected

  await itemView.getByRole("button", { name: /^EPUB/ }).click();
  await itemView.getByRole("button", { name: "Download 2 files" }).click();
  await expect.poll(() => sent.length).toBe(1);
  expect(sent[0]!.urls).toEqual([item.details_url]);
  expect((sent[0]!.options.files as string[]).sort()).toEqual(["alice.epub", "alice.pdf"]);
});

test("archive.org: a lending-library item is explained, not downloaded", async ({ page }) => {
  await mockArchive(page);
  await page.goto("/en/archive?id=lentbook00");
  await expect(page.getByRole("main").getByRole("alert")).toContainText("lending library");
  await expect(page.getByRole("button", { name: /Download/ })).toHaveCount(0);
});

test("Wayback: snapshots by year and a raw download", async ({ page }) => {
  const { sent } = await mockArchive(page);
  await page.goto("/en/wayback");
  await page.getByTestId("wayback-url").fill("example.com");
  await page.getByRole("button", { name: "Find snapshots" }).click();
  const timeline = page.getByTestId("wayback-timeline");
  await expect(timeline.getByRole("radio")).toHaveCount(3);
  await expect(timeline.getByTestId("snapshot")).toHaveCount(2); // 2005 is selected first
  await timeline
    .getByTestId("snapshot")
    .first()
    .getByRole("button", { name: /Download original/ })
    .click();
  await expect.poll(() => sent.length).toBe(1);
  expect(sent[0]!.urls).toEqual(["https://web.archive.org/web/20050105083000/http://example.com/"]);
  await timeline.locator("label").filter({ hasText: "2019" }).click();
  await expect(timeline.getByTestId("snapshot")).toHaveCount(1);
});

for (const locale of ["en", "hi", "ar"]) {
  test(`axe: archive.org and Wayback pages (${locale})`, async ({ page }) => {
    await mockArchive(page);
    await page.goto(`/${locale}/archive?id=alicesadventures00gut`);
    await expect(page.getByTestId("archive-item")).toBeVisible();
    let results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
    expect(results.violations).toEqual([]);

    await page.goto(`/${locale}/archive`);
    await page.getByTestId("archive-q").fill("alice");
    await page.locator("form[role=search] button[type=submit]").click();
    await expect(page.getByTestId("archive-results")).toBeVisible();
    results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
    expect(results.violations).toEqual([]);

    await page.goto(`/${locale}/wayback`);
    await page.getByTestId("wayback-url").fill("example.com");
    await page.locator("form button[type=submit]").click();
    await expect(page.getByTestId("wayback-timeline")).toBeVisible();
    results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
    expect(results.violations).toEqual([]);
  });
}
