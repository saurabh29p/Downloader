import { createHash } from "node:crypto";

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { fileLink, jobRow, uniqueName } from "./helpers";

test("paste → preview → download → done → save file", async ({ page, request }, testInfo) => {
  const name = uniqueName(testInfo, "sample");
  await page.goto("/en");
  await page.getByLabel("Links to download").fill(fileLink(name));
  await expect(page.getByTestId("detect-chip")).toHaveText("127.0.0.1");
  await page.getByRole("button", { name: "Check link" }).click();

  const sheet = page.getByRole("dialog");
  await expect(sheet).toContainText(name);
  await expect(sheet).toContainText("2\u00a0MB");
  await expect(sheet).toContainText("MD5 will be checked");

  const axe = await new AxeBuilder({ page }).include("[role=dialog]").analyze();
  expect(axe.violations).toEqual([]);

  await sheet.getByRole("button", { name: "Download" }).click();
  await expect(sheet).toBeHidden();
  await expect(page.getByText("Added 1 download")).toBeVisible();
  const withToast = await new AxeBuilder({ page }).analyze();
  expect(withToast.violations).toEqual([]);

  // Recent list on Home updates live over SSE.
  await expect(jobRow(page, name)).toHaveAttribute("data-state", "done", { timeout: 15_000 });

  await page.goto("/en/downloads");
  const row = jobRow(page, name);
  await expect(row).toHaveAttribute("data-state", "done");
  await expect(row.getByText("Checksum OK")).toBeVisible();

  const href = await row.getByRole("link", { name: `Save file: ${name}` }).getAttribute("href");
  const file = await request.get(href!);
  expect(file.ok()).toBeTruthy();
  const body = await file.body();
  expect(body.length).toBe(2 * 1024 * 1024);
  const original = await request.get(fileLink(name));
  expect(createHash("md5").update(body).digest("hex")).toBe(
    createHash("md5")
      .update(await original.body())
      .digest("hex"),
  );
});

test("batch of three links", async ({ page }, testInfo) => {
  const names = ["a", "b", "c"].map((stem) => uniqueName(testInfo, `batch-${stem}`, "dat"));
  await page.goto("/en");
  await page
    .getByLabel("Links to download")
    .fill(names.map((n) => fileLink(n, "size=50000")).join("\n"));
  await page.getByRole("button", { name: "Queue 3 links" }).click();
  await expect(page.getByText("Added 3 downloads")).toBeVisible();
  await page.goto("/en/downloads");
  for (const name of names) {
    await expect(jobRow(page, name)).toHaveAttribute("data-state", "done", { timeout: 15_000 });
  }
});

test("pause and resume a slow download", async ({ page }, testInfo) => {
  const name = uniqueName(testInfo, "slow");
  await page.goto("/en");
  await page.getByLabel("Links to download").fill(fileLink(name, "size=4000000&slow=1"));
  await page.getByRole("button", { name: "Check link" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Download" }).click();

  await page.goto("/en/downloads");
  await expect(page.getByTestId("connection")).toHaveText("Live");
  const row = jobRow(page, name);
  await expect(row).toHaveAttribute("data-state", "downloading", { timeout: 10_000 });
  await expect(row.getByRole("progressbar")).toHaveAttribute("aria-valuenow", /^[1-9]\d?$/, {
    timeout: 10_000,
  });

  await row.getByRole("button", { name: `Pause: ${name}` }).click();
  await expect(row).toHaveAttribute("data-state", "paused");
  await expect(row.getByText(/of \u2066?3\.8\u00a0MB/)).toBeVisible();

  await row.getByRole("button", { name: `Resume: ${name}` }).click();
  await expect(row).toHaveAttribute("data-state", "done", { timeout: 60_000 });
});

test("blocked and unsupported links get clear messages", async ({ page }) => {
  await page.goto("/en");
  const input = page.getByLabel("Links to download");
  await input.fill("http://10.0.0.1/router.cfg");
  await page.getByRole("button", { name: "Check link" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("private or local network");

  await input.fill("http://127.0.0.1:8200/page.html");
  await page.getByRole("button", { name: "Check link" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("isn't supported yet");

  await input.fill("hello there");
  await page.getByRole("button", { name: "Check link" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("doesn't look like a link");
});

test("keyboard only: paste, Enter, Enter", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "phone", "keyboard flow is for desktop");
  const name = uniqueName(testInfo, "keys");
  await page.goto("/en");
  const input = page.getByLabel("Links to download");
  for (let i = 0; i < 15 && !(await input.evaluate((el) => el === document.activeElement)); i++) {
    await page.keyboard.press("Tab");
  }
  await expect(input).toBeFocused();
  await page.keyboard.type(fileLink(name, "size=1000"));
  await page.keyboard.press("Enter");
  const download = page.getByRole("dialog").getByRole("button", { name: "Download" });
  await expect(download).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(jobRow(page, name)).toHaveAttribute("data-state", "done", { timeout: 15_000 });
});

test("command palette opens with Ctrl+K", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === "phone", "keyboard shortcut is for desktop");
  await page.goto("/en");
  await expect(page.getByTestId("api-status")).toHaveAttribute("data-state", "online");
  await page.keyboard.press("Control+k");
  await page.getByRole("combobox", { name: "Quick menu" }).fill("downl");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/en\/downloads$/);
});
