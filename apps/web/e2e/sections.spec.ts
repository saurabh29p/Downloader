import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("sections: Home lists them; a preset runs its search with site links", async ({ page }) => {
  await page.goto("/en");
  await page.getByTestId("sections-grid").getByRole("link", { name: /Books/ }).click();
  await expect(page).toHaveURL(/\/en\/sections\/books$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Books");
  await page.getByRole("button", { name: "Premchand stories" }).click();
  await expect(page).toHaveURL(/preset=premchand/);
  await expect(page.getByTestId("result-card").first()).toContainText("Premchand");
  const openLibrary = page.getByTestId("site-links").getByRole("link", { name: /Open Library/ });
  await expect(openLibrary).toHaveAttribute("href", /openlibrary\.org\/search\?q=Premchand/);
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);
});

test("movies: asks for a TMDB key and never offers piracy links", async ({ page }) => {
  await page.goto("/en/sections/movies");
  await expect(page.getByText("Add a free TMDB key in Connections")).toBeVisible();
  await page.getByRole("button", { name: "Film noir" }).click();
  await expect(page).toHaveURL(/preset=film-noir/);
  const links = page.getByTestId("site-links").getByRole("link");
  await expect(links.first()).toBeVisible();
  for (const href of await links.evaluateAll((all) => all.map((a) => a.getAttribute("href")))) {
    expect(href).not.toMatch(/torrent|pirate|1337x|yts|fmovies|123movies/i);
  }
});

test("declassified: official sites carry the query", async ({ page }) => {
  await page.goto("/en/sections/declassified?preset=mkultra");
  const cia = page.getByTestId("site-links").getByRole("link", { name: /CIA FOIA Reading Room/ });
  await expect(cia).toHaveAttribute("href", "https://www.cia.gov/readingroom/search/site/MKUltra");
});

for (const locale of ["en", "hi", "ar"]) {
  test(`axe: Sections pages (${locale})`, async ({ page }) => {
    await page.goto(`/${locale}/sections`);
    await expect(page.getByTestId("sections-grid").first()).toBeVisible();
    let results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
    await page.goto(`/${locale}/sections/more`);
    await expect(page.getByTestId("sections-grid")).toBeVisible();
    results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });
}
