// Lighthouse check against a running production build.
// Usage: pnpm lighthouse [baseUrl]   (default http://127.0.0.1:3000)
// Needs Chrome/Chromium; set CHROME_PATH if it is not found automatically.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const base = process.argv[2] ?? "http://127.0.0.1:3000";
const pages = ["/en", "/en/downloads", "/en/youtube", "/ar/youtube", "/en/settings"];
const budgets = { performance: 0.9, accessibility: 1, "best-practices": 0.9 };
const out = mkdtempSync(join(tmpdir(), "anyget-lh-"));
let failed = false;

for (const formFactor of ["mobile", "desktop"]) {
  for (const page of pages) {
    const file = join(out, `${formFactor}${page.replaceAll("/", "_")}.json`);
    execFileSync(
      "pnpm",
      [
        "dlx",
        "lighthouse@13.6.0",
        base + page,
        "--quiet",
        "--output=json",
        `--output-path=${file}`,
        "--only-categories=performance,accessibility,best-practices",
        "--chrome-flags=--headless=new --no-sandbox",
        ...(formFactor === "desktop" ? ["--preset=desktop"] : []),
      ],
      { stdio: ["ignore", "ignore", "inherit"] },
    );
    const report = JSON.parse(readFileSync(file, "utf8"));
    const scores = Object.fromEntries(
      Object.entries(report.categories).map(([key, value]) => [key, value.score]),
    );
    const lcp = report.audits["largest-contentful-paint"].displayValue;
    const cls = report.audits["cumulative-layout-shift"].displayValue;
    const line = Object.entries(scores)
      .map(([key, value]) => `${key} ${Math.round(value * 100)}`)
      .join(", ");
    console.log(`${formFactor.padEnd(7)} ${page.padEnd(14)} ${line} | LCP ${lcp}, CLS ${cls}`);
    for (const [key, min] of Object.entries(budgets)) {
      if (scores[key] < min) failed = true;
    }
  }
}
if (failed) {
  console.error(
    "Lighthouse budget not met (performance 90, accessibility 100, best practices 90).",
  );
  process.exit(1);
}
