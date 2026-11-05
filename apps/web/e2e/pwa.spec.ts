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

test("pages and the API send security headers", async ({ request }) => {
  const page = await request.get("/en");
  const csp = page.headers()["content-security-policy"];
  expect(csp).toContain("default-src 'self'");
  expect(csp).toContain("frame-ancestors 'none'");
  expect(csp).not.toContain("unsafe-eval");
  expect(page.headers()["x-content-type-options"]).toBe("nosniff");
  const api = await request.get("/api/health");
  expect(api.headers()["content-security-policy"]).toContain("default-src 'none'");
  expect(api.headers()["x-frame-options"]).toBe("DENY");
});

test("requests that came through Cloudflare need Access, even via the website", async ({
  request,
}) => {
  // cloudflared adds Cf-Ray / Cf-Connecting-Ip; the website must pass them on to the API.
  const viaTunnel = await request.get("/api/jobs", {
    headers: { "Cf-Ray": "8abc-LHR", "Cf-Connecting-Ip": "203.0.113.7" },
  });
  expect(viaTunnel.status()).toBe(401);
  expect((await viaTunnel.json()).code).toBe("auth_required");
  expect((await request.get("/api/jobs")).status()).toBe(200); // this computer
});
