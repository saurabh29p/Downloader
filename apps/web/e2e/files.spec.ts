import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { FIXTURE, jobRow, uniqueName } from "./helpers";

test("a web page lists its files; pick one and download it", async ({ page }, testInfo) => {
  const tag = uniqueName(testInfo, "page", "x").replace(/\.x$/, "");
  await page.goto("/en");
  await page.getByLabel("Links to download").fill(`${FIXTURE}/page.html?id=${tag}`);
  await page.getByRole("button", { name: "Check link" }).click();

  const sheet = page.getByRole("dialog");
  await expect(sheet).toContainText("Web page");
  const picker = sheet.getByTestId("file-picker");
  await expect(picker.getByTestId("file-choice")).toHaveCount(3);
  await expect(picker).toContainText("1 of 3 selected");
  const axe = await new AxeBuilder({ page }).include("[role=dialog]").analyze();
  expect(axe.violations).toEqual([]);

  await picker.getByLabel("A page.html").uncheck();
  await picker.getByLabel(`report-${tag}.pdf`).check();
  await sheet.getByRole("button", { name: "Download 1 file" }).click();
  await expect(sheet).toBeHidden();

  await page.goto("/en/downloads");
  await expect(jobRow(page, `report-${tag}.pdf`)).toHaveAttribute("data-state", "done", {
    timeout: 15_000,
  });
});

for (const path of ["/en/code", "/en/images"]) {
  test(`${path} explains itself and has no axe violations`, async ({ page }) => {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.getByRole("button", { name: /Find/ }).click();
    await expect(page.getByRole("main").getByRole("alert")).toContainText("Enter a link first");
    const axe = await new AxeBuilder({ page }).analyze();
    expect(axe.violations).toEqual([]);
  });
}

test("/en/code picks files from a probe", async ({ page }) => {
  // The fixture page stands in for a repo: any multi-file probe uses the same picker.
  await page.goto("/en/code");
  await page.getByTestId("source-url").fill(`${FIXTURE}/page.html?id=code`);
  await page.getByRole("button", { name: "Find files" }).click();
  const picker = page.getByTestId("file-picker");
  await expect(picker.getByTestId("file-choice")).toHaveCount(3);
  await picker.getByRole("button", { name: "Select all" }).click();
  await expect(page.getByRole("button", { name: "Download 3 files" })).toBeEnabled();
  await picker.getByRole("button", { name: "Select none" }).click();
  await expect(page.getByRole("button", { name: "Download" })).toBeDisabled();
});
