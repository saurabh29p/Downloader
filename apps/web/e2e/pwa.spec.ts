import { expect, test } from "@playwright/test";

import { fileLink, uniqueName } from "./helpers";

test("the manifest makes AnyGet installable and a share target", async ({ request }) => {
  const response = await request.get("/manifest.webmanifest");
  expect(response.ok()).toBeTruthy();
  const manifest = await response.json();
  expect(manifest.display).toBe("standalone");
  expect(manifest.share_target).toMatchObject({ action: "/share", method: "GET" });
  for (const icon of manifest.icons) {
    expect((await request.get(icon.src)).ok()).toBeTruthy();
  }
});

test("sharing a link opens its preview", async ({ page }, testInfo) => {
  const name = uniqueName(testInfo, "shared");
  // What Android sends: often the title and text, with the link inside the text.
  await page.goto(
    `/share?title=${encodeURIComponent("A file")}&text=${encodeURIComponent(`Look ${fileLink(name)} now`)}`,
  );
  const sheet = page.getByRole("dialog");
  await expect(sheet).toContainText(name);
  await expect(page).toHaveURL(/\/en$/);
  await expect(page.getByLabel("Links to download")).toHaveValue(fileLink(name));
});

test("sharing text without a link says so", async ({ page }) => {
  await page.goto("/en/share?text=hello");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Nothing to download");
});

test("the service worker installs and never caches API answers", async ({ page }) => {
  await page.goto("/en");
  const scope = await page.evaluate(async () => (await navigator.serviceWorker.ready).scope);
  expect(scope).toMatch(/\/$/);
  await page.reload();
  await page.evaluate(() => fetch("/api/health"));
  const cached = await page.evaluate(async () => {
    const urls: string[] = [];
    for (const name of await caches.keys()) {
      for (const req of await (await caches.open(name)).keys())
        urls.push(new URL(req.url).pathname);
    }
    return urls;
  });
  expect(cached.some((p) => p.startsWith("/_next/static/"))).toBeTruthy();
  expect(cached.some((p) => p.startsWith("/api/"))).toBeFalsy();
});
