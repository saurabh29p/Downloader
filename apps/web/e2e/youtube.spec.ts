import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Locator, type Page } from "@playwright/test";

import playlist from "../test/fixtures/probe-playlist.json" with { type: "json" };
import video from "../test/fixtures/probe-video.json" with { type: "json" };

const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
type JobsBody = {
  urls?: string[];
  items?: { url: string; options: Record<string, unknown> }[];
  options: Record<string, unknown>;
};

/** Mock the probe (sites are not reachable in tests) and capture what the page queues. */
async function mockApi(page: Page, probe: object) {
  const sent: JobsBody[] = [];
  await page.route("**/api/probe", (route) => route.fulfill({ json: probe }));
  await page.route("**/api/jobs", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    sent.push(route.request().postDataJSON() as JobsBody);
    await route.fulfill({ status: 201, json: { jobs: [], rejected: [], skipped: [] } });
  });
  return sent;
}

/** Click a pill like a user does (its radio input is visually hidden inside the label). */
async function pick(scope: Locator, text: string) {
  await scope.locator("label").filter({ hasText: text }).first().click();
}

async function checkLink(page: Page, url: string) {
  await page.getByTestId("media-input").fill(url);
  await page.getByRole("button", { name: "Check link" }).click();
}

test("format picker shows the probed formats and sends the chosen preset", async ({ page }) => {
  const sent = await mockApi(page, video);
  await page.goto("/en/youtube");
  await checkLink(page, video.url);

  const card = page.getByTestId("video-card");
  await expect(card.getByRole("heading", { level: 2 })).toHaveText(video.title);
  const quality = card.getByRole("group", { name: "Quality" });
  const values = await quality
    .getByRole("radio")
    .evaluateAll((els) => els.map((el) => (el as HTMLInputElement).value));
  expect(values).toEqual(["best", "1080", "720", "480", "360"]); // no 2160: not in this video
  await expect(card.getByTestId("format-select").locator("option")).toHaveCount(7); // automatic + 6 video formats

  await pick(quality, "720p");
  await expect(quality.getByRole("radio", { name: /720p/ })).toBeChecked();
  await card.getByLabel("File type").selectOption("mp4");
  await card.getByRole("button", { name: "Download video" }).click();
  await expect.poll(() => sent.length).toBe(1);
  expect(sent[0]!.urls).toEqual([video.normalized_url]);
  expect(sent[0]!.options).toMatchObject({
    preset: "720",
    container: "mp4",
    embed_thumbnail: true,
  });
});

test("audio only sends mp3 with the cover image", async ({ page }) => {
  const sent = await mockApi(page, video);
  await page.goto("/en/youtube");
  await checkLink(page, video.url);
  const card = page.getByTestId("video-card");
  await card.getByRole("checkbox", { name: /Audio only/ }).check();
  await pick(card, "MP3");
  await card.getByRole("button", { name: "Download audio" }).click();
  await expect.poll(() => sent.length).toBe(1);
  expect(sent[0]!.options).toMatchObject({
    preset: "audio",
    audio_format: "mp3",
    embed_thumbnail: true,
  });
  expect(sent[0]!.options).not.toHaveProperty("container");
});

test("playlist: select all queues one item per video, in order", async ({ page }) => {
  const sent = await mockApi(page, playlist);
  await page.goto("/en/youtube");
  await checkLink(page, playlist.url);
  const view = page.getByTestId("playlist-view");
  await expect(view.getByTestId("playlist-item")).toHaveCount(3);
  await expect(view.getByText("Saved before")).toHaveCount(1); // item 2 is pre-unchecked
  await expect(view.getByRole("button", { name: "Download 2 items" })).toBeVisible();

  await view.getByRole("checkbox", { name: "Select all 3 items" }).check();
  await pick(view, "480p");
  await view.getByRole("button", { name: "Download 3 items" }).click();
  await expect.poll(() => sent.length).toBe(1);
  const body = sent[0]!;
  expect(body.items?.map((i) => i.options.index)).toEqual([1, 2, 3]);
  expect(body.items?.[0]?.options.archive_id).toBe("youtube aqz-KE-bpKQ");
  expect(body.options).toMatchObject({
    preset: "480",
    folder: playlist.title,
    archive: playlist.extra.archive,
  });
});

test("Home preview drawer uses the same format picker for media links", async ({ page }) => {
  const sent = await mockApi(page, video);
  await page.goto("/en");
  await page.getByLabel("Search or paste links").fill(video.url);
  await page.getByRole("button", { name: "Check link" }).click();
  const sheet = page.getByRole("dialog");
  await expect(sheet.getByTestId("format-picker")).toBeVisible();
  await pick(sheet, "480p");
  await sheet.getByRole("button", { name: "Download video" }).click();
  await expect.poll(() => sent.length).toBe(1);
  expect(sent[0]!.options).toMatchObject({ preset: "480" });
});

for (const locale of ["en", "hi", "ar"]) {
  test(`axe: YouTube page with a video and a playlist (${locale})`, async ({ page }) => {
    await mockApi(page, video);
    await page.goto(`/${locale}/youtube`);
    await page.getByTestId("media-input").fill(video.url);
    await page.locator("form button[type=submit]").click();
    await expect(page.getByTestId("video-card")).toBeVisible();
    let results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
    expect(results.violations).toEqual([]);

    await page.unroute("**/api/probe");
    await page.route("**/api/probe", (route) => route.fulfill({ json: playlist }));
    await page.getByTestId("media-input").fill(playlist.url);
    await page.locator("form button[type=submit]").click();
    await expect(page.getByTestId("playlist-view")).toBeVisible();
    results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
    expect(results.violations).toEqual([]);
  });

  test(`axe: Settings page (${locale})`, async ({ page }) => {
    await page.goto(`/${locale}/settings`);
    await expect(page.getByTestId("app-settings")).toBeVisible();
    const results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
    expect(results.violations).toEqual([]);
  });
}
