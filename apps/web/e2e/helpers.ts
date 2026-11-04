import type { Page, TestInfo } from "@playwright/test";

export const FIXTURE = "http://127.0.0.1:8200";

/** A file name unique to this test run and project, so parallel tests never collide. */
export function uniqueName(testInfo: TestInfo, stem: string, ext = "bin") {
  const id = `${testInfo.project.name}-${testInfo.workerIndex}-${Date.now().toString(36)}`;
  return `${stem}-${id}.${ext}`;
}

export function fileLink(name: string, query = "") {
  return `${FIXTURE}/files/${encodeURIComponent(name)}${query ? `?${query}` : ""}`;
}

export function jobRow(page: Page, name: string) {
  return page.locator(`[data-testid="job-row"][data-name="${name}"]`);
}
