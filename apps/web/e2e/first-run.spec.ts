import { expect, test } from "@playwright/test";

test("first-run hint offers safe examples and can be hidden", async ({ page }) => {
  await page.goto("/en");
  const hint = page.getByTestId("first-run-hint");
  await expect(hint).toBeVisible();
  const links = hint.getByRole("link");
  await expect(links).toHaveCount(3);
  await expect(links.first()).toHaveAttribute(
    "href",
    `/en?url=${encodeURIComponent("https://archive.org/details/alicesadventures19033gut")}`,
  );

  await hint.getByRole("button", { name: "Hide" }).click();
  await expect(page).toHaveURL(/\/en$/);
  await expect(page.getByTestId("first-run-hint")).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByTestId("first-run-hint")).toHaveCount(0);
});

test("the hint works without JavaScript", async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto("/ar");
  const hint = page.getByTestId("first-run-hint");
  await expect(hint).toBeVisible();
  await hint.getByRole("button", { name: "إخفاء" }).click();
  await expect(page).toHaveURL(/\/ar$/);
  await expect(page.getByTestId("first-run-hint")).toHaveCount(0);
  await context.close();
});
