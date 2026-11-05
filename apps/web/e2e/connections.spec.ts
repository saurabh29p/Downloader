import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const SECRET = "e2e-secret-cookie";
const future = Math.floor(Date.now() / 1000) + 30 * 86400;
const row = (domain: string, name: string) =>
  `${domain}\tTRUE\t/\tTRUE\t${future}\t${name}\t${SECRET}\n`;
const file = (text: string) => ({
  name: "cookies.txt",
  mimeType: "text/plain",
  buffer: Buffer.from(`# Netscape HTTP Cookie File\n${text}`),
});
const card = (page: Page, site: string) =>
  page.locator(`[data-testid="connection"][data-site="${site}"]`);

test.describe.configure({ mode: "serial" });

test("connections: cookies and keys are saved, never shown, and removable", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "one run is enough (shared server state)");
  await page.goto("/en/connections");
  const youtube = card(page, "youtube");
  await expect(youtube).toHaveAttribute("data-status", "not_connected");

  await page.getByTestId("upload-youtube").setInputFiles(file(row(".youtube.com", "LOGIN_INFO")));
  await expect(youtube).toHaveAttribute("data-status", "connected");
  await expect(youtube).toContainText("Connected on");
  await expect(page.getByText(SECRET)).toHaveCount(0);
  expect(await (await page.request.get("/api/connections")).text()).not.toContain(SECRET);

  await youtube.getByRole("button", { name: "Test" }).click();
  await expect(page.getByText("YouTube works.")).toBeVisible();
  await youtube.getByRole("button", { name: "Remove" }).click();
  await expect(youtube).toHaveAttribute("data-status", "not_connected");

  // One file for several sites: each gets its own cookies.
  await page
    .getByTestId("import-cookies")
    .setInputFiles(file(row(".reddit.com", "reddit_session") + row(".vimeo.com", "vimeo")));
  await expect(page.getByText("Connected: Reddit, Vimeo")).toBeVisible();
  await expect(card(page, "reddit")).toHaveAttribute("data-status", "connected");

  // A key: write-only.
  const dpla = card(page, "dpla");
  await page.getByTestId("dpla-token").fill("dpla-e2e-key");
  await dpla.getByRole("button", { name: "Save" }).click();
  await expect(dpla).toHaveAttribute("data-status", "connected");
  await expect(page.getByTestId("dpla-token")).toHaveValue("");
  expect(await (await page.request.get("/api/connections")).text()).not.toContain("dpla-e2e-key");
  await dpla.getByRole("button", { name: "Remove" }).click();
  await expect(dpla).toHaveAttribute("data-status", "not_connected");
});

test("a link to one site opens its card", async ({ page }) => {
  await page.goto("/en/connections#youtube");
  await expect(card(page, "youtube")).toBeInViewport();
});

for (const locale of ["en", "hi", "ar"]) {
  test(`axe: Connections page (${locale})`, async ({ page }) => {
    await page.goto(`/${locale}/connections`);
    await expect(page.getByTestId("cookie-sites")).toBeVisible();
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });
}
