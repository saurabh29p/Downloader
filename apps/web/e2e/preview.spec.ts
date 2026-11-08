import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Page, type TestInfo } from "@playwright/test";

import { FIXTURE, uniqueName } from "./helpers";

const AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
const WEB = { "X-Requested-With": "anyget" };

/** Download fixture files through AnyGet and wait until the Library has them. */
async function seed(
  request: APIRequestContext,
  testInfo: TestInfo,
  files: { fixture: string; name?: string; stem?: string; ext?: string; url?: string }[],
): Promise<string[]> {
  const names = files.map(
    (f) =>
      f.name ??
      uniqueName(testInfo, f.stem ?? f.fixture.split(".")[0]!, f.ext ?? f.fixture.split(".").pop()),
  );
  const urls = files.map(
    (f, i) => f.url?.replace("{name}", names[i]!) ?? `${FIXTURE}/media/${f.fixture}/${names[i]}`,
  );
  const created = await request.post("/api/jobs", { data: { urls, options: {} }, headers: WEB });
  expect(created.ok()).toBeTruthy();
  for (const name of names) {
    await expect
      .poll(
        async () => {
          const page = await request.get(`/api/library?q=${encodeURIComponent(name)}`);
          return (await page.json()).total;
        },
        { timeout: 20_000 },
      )
      .toBeGreaterThan(0);
  }
  return names;
}

async function openFromLibrary(page: Page, name: string) {
  await page.goto("/en/library");
  await page.getByTestId("library-search").fill(name);
  await page.getByTestId("library-search").press("Enter");
  await page.getByRole("button", { name: new RegExp(`^(Open|Play): ${name}`) }).click();
}

test("audio keeps playing across in-app navigation, and only one player plays", async ({
  page,
  request,
}, testInfo) => {
  const [tone, clip] = await seed(request, testInfo, [
    { fixture: "tone.ogg" },
    { fixture: "clip.webm" },
  ]);
  await openFromLibrary(page, tone!);
  const player = page.getByTestId("mini-player");
  await expect(player).toHaveAttribute("data-state", "playing");
  await expect(player).toContainText(tone!);
  const audio = page.getByTestId("app-audio");
  const before = await audio.evaluate((el: HTMLAudioElement) => ({
    t: el.currentTime,
    src: el.src,
  }));

  await page
    .getByRole("navigation", { name: "Main" })
    .getByRole("link", { name: /Downloads/ })
    .click();
  await expect(page).toHaveURL(/\/en\/downloads$/);
  await expect(player).toHaveAttribute("data-state", "playing");
  const after = await audio.evaluate((el: HTMLAudioElement) => ({
    t: el.currentTime,
    src: el.src,
  }));
  expect(after.src).toBe(before.src); // the same element and file, not restarted
  expect(after.t).toBeGreaterThanOrEqual(before.t);

  const axe = await new AxeBuilder({ page })
    .include("[data-testid=mini-player]")
    .withTags(AXE_TAGS)
    .analyze();
  expect(axe.violations).toEqual([]);

  // A video starting pauses the audio: one player at a time (opened in-app, from
  // Downloads: a full page load would end the audio by design).
  await page.getByRole("button", { name: `Open: ${clip}` }).click();
  const video = page.getByTestId("viewer-video");
  await expect(video).toBeVisible();
  await video.evaluate(async (el: HTMLVideoElement) => {
    el.muted = true;
    await el.play();
  });
  await expect(player).toHaveAttribute("data-state", "paused");
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Stop and close the player" }).click();
  await expect(player).toBeHidden();
});

test("video viewer shows subtitles and speed; Downloads opens the same viewer", async ({
  page,
  request,
}, testInfo) => {
  const stem = uniqueName(testInfo, "talk", "x").replace(/\.x$/, "");
  await seed(request, testInfo, [
    { fixture: "clip.webm", name: `${stem}.webm` },
    { fixture: "clip.en.vtt", name: `${stem}.en.vtt` },
  ]);
  await page.goto("/en/downloads");
  await page.getByRole("button", { name: `Open: ${stem}.webm` }).click();
  const video = page.getByTestId("viewer-video");
  await expect(video).toBeVisible();
  await expect.poll(() => video.evaluate((el: HTMLVideoElement) => el.textTracks.length)).toBe(1);
  await page.getByRole("combobox", { name: "Speed" }).selectOption("1.5");
  expect(await video.evaluate((el: HTMLVideoElement) => el.playbackRate)).toBe(1.5);
});

test("PDF reader: pages, search, keyboard, and focus returns on Escape", async ({
  page,
  request,
}, testInfo) => {
  const [doc] = await seed(request, testInfo, [{ fixture: "doc.pdf" }]);
  await openFromLibrary(page, doc!);
  await expect(page.getByTestId("pdf-pages")).toHaveText("/ 3");
  await page.getByTestId("pdf-area").press("ArrowRight");
  await expect(page.getByTestId("pdf-page")).toHaveValue("2");
  await page.getByTestId("pdf-search").fill("compass");
  await page.getByTestId("pdf-search").press("Enter");
  await expect(page.getByTestId("pdf-page")).toHaveValue("3");
  const axe = await new AxeBuilder({ page })
    .include("[data-testid=viewer]")
    .withTags(AXE_TAGS)
    .analyze();
  expect(axe.violations).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("viewer")).toBeHidden();
  await expect(page.getByRole("button", { name: `Open: ${doc}` })).toBeFocused();
});

test("EPUB reader: contents, safe chapter text, remembered position", async ({
  page,
  request,
}, testInfo) => {
  const [book] = await seed(request, testInfo, [{ fixture: "book.epub" }]);
  await openFromLibrary(page, book!);
  const reader = page.getByTestId("epub-page");
  await expect(reader).toContainText("reading room steps");
  await expect(page.getByTestId("epub-toc").locator("option")).toHaveText(["Opening", "Closing"]);
  await expect(reader.locator("script, img")).toHaveCount(0); // the book's script and remote image
  await page.getByRole("button", { name: "Next chapter" }).click();
  await expect(reader).toContainText("wrote the last line");
  await page.getByRole("button", { name: "Larger text" }).click();
  await page.keyboard.press("Escape");
  await openFromLibrary(page, book!);
  await expect(page.getByText("Back where you left off: Closing.")).toBeVisible();
  await expect(reader).toContainText("wrote the last line");
});

test("text preview pages and search; images: next, zoom, keyboard", async ({
  page,
  request,
}, testInfo) => {
  const id = uniqueName(testInfo, "pics", "x").replace(/^pics-|\.x$/g, "");
  const [notes, one, two] = await seed(request, testInfo, [
    { fixture: "notes.txt", url: `${FIXTURE}/text/{name}?lines=20000` },
    { fixture: "bars-1.png", name: `bars-1-${id}.png` },
    { fixture: "bars-2.png", name: `bars-2-${id}.png` },
  ]);
  await openFromLibrary(page, notes!);
  const text = page.getByTestId("viewer-text");
  await expect(text).toContainText("Line 1: the lighthouse keeper's log. पंक्ति 1");
  await expect(page.getByRole("button", { name: "Load more" })).toBeVisible(); // ~1.3 MB: paged
  await page.getByTestId("text-search").fill("पंक्ति 1999");
  await expect(page.getByTestId("text-matches")).toHaveText("1 match");
  await page.keyboard.press("Escape");

  // Two pictures from this test: the viewer steps between them.
  await page.goto("/en/library");
  await page.getByTestId("library-search").fill(id);
  await page.getByTestId("library-search").press("Enter");
  await page.getByRole("button", { name: `Open: ${two}` }).click();
  await expect(page.getByTestId("image-position")).toHaveText(/^[12] \/ 2$/);
  await expect(page.getByTestId("viewer-image")).toHaveAttribute("alt", two!);
  await page.getByTestId("image-area").press("ArrowRight");
  await expect(page.getByTestId("viewer-image")).toHaveAttribute("alt", one!);
  await page.getByTestId("image-area").press("ArrowLeft");
  await expect(page.getByTestId("viewer-image")).toHaveAttribute("alt", two!);
  await page.getByTestId("image-area").press("+");
  await expect(page.getByTestId("image-zoom")).not.toHaveText("Fit");
  await page.getByTestId("image-area").press("0");
  await expect(page.getByTestId("image-zoom")).toHaveText("Fit");
});

test("files that can't be shown get a reason and Download, never a broken player", async ({
  page,
  request,
}, testInfo) => {
  // Named .mp4 but not a video (random bytes): the server sniffs the real type.
  const [fake] = await seed(request, testInfo, [
    { fixture: "x", stem: "not-a-video", ext: "mp4", url: `${FIXTURE}/files/{name}?size=4000` },
  ]);
  await openFromLibrary(page, fake!);
  const fallback = page.getByTestId("viewer-fallback");
  await expect(fallback).toHaveAttribute("data-reason", "unsupported_format");
  await expect(fallback.getByRole("link", { name: "Download" })).toBeVisible();
  await expect(page.getByTestId("viewer-video")).toHaveCount(0);
});
