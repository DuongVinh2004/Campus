import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "ui-final.pw.ts",
  workers: 1,
  retries: 0,
  timeout: 180_000,
  reporter: "line",
  use: {
    headless: true,
    viewport: { width: 1280, height: 800 },
    launchOptions: { executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe" },
    trace: "off",
    video: "off",
    screenshot: "off",
  },
});
