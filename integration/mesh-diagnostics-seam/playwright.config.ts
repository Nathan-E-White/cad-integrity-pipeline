import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/browser", workers: 1,
  use: { browserName: "chromium", channel: "chrome", headless: true, viewport: { width: 1600, height: 1000 } },
  webServer: { command: process.env.INSPECTOR_PRODUCTION ? "npm exec vite -- preview --host 127.0.0.1 --port 5178 --strictPort" : "npm run dev -- --port 5178 --strictPort", url: "http://127.0.0.1:5178", reuseExistingServer: false },
});
