import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e-live",
  testMatch: "**/*.pw.ts",
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: { timeout: 12_000 },
  use: {
    baseURL: "http://127.0.0.1:3115",
    headless: true,
    actionTimeout: 15_000,
    navigationTimeout: 20_000,
    viewport: { width: 1440, height: 960 },
    launchOptions: { executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe" },
    screenshot: "only-on-failure",
    // Traces/HAR could retain authentication headers; keep redacted reports
    // and screenshots instead of recording raw session credentials.
    trace: "off",
    video: "off",
  },
});
