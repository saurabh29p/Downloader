import { defineConfig, devices } from "@playwright/test";

const webPort = 3100;
const apiPort = 8100;
export const fixturePort = 8200;
// Use a preinstalled Chromium when the bundled one is missing (e.g. sandboxes): PW_CHROMIUM_PATH=/path/to/chrome
const executablePath = process.env.PW_CHROMIUM_PATH || undefined;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${webPort}`,
    trace: "retain-on-failure",
    launchOptions: { executablePath },
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], launchOptions: { executablePath } } },
    {
      name: "phone",
      use: {
        ...devices["Pixel 7"],
        viewport: { width: 360, height: 780 },
        launchOptions: { executablePath },
      },
    },
  ],
  webServer: [
    {
      command: `node e2e/fixture-server.mjs`,
      url: `http://127.0.0.1:${fixturePort}/health`,
      env: { FIXTURE_PORT: String(fixturePort) },
      reuseExistingServer: !process.env.CI,
    },
    {
      // Fresh data every run; the allowlist lets the API reach only the fixture server.
      command: `rm -rf .e2e && uv run --project ../api uvicorn anyget.main:app --host 127.0.0.1 --port ${apiPort}`,
      url: `http://127.0.0.1:${apiPort}/api/health`,
      env: {
        ANYGET_DATA_DIR: ".e2e/data",
        ANYGET_DOWNLOADS_DIR: ".e2e/downloads",
        ANYGET_NET_ALLOWLIST: `127.0.0.1:${fixturePort}`,
      },
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      // Production build so axe checks what users get. API_URL is baked into the rewrites.
      command: `pnpm build && pnpm exec next start -H 127.0.0.1 -p ${webPort}`,
      url: `http://127.0.0.1:${webPort}/healthz`,
      env: { API_URL: `http://127.0.0.1:${apiPort}` },
      reuseExistingServer: !process.env.CI,
      timeout: 240_000,
    },
  ],
});
