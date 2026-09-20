import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/gradio-browser", workers: 1,
  use: { browserName: "chromium", channel: "chrome", headless: true, viewport: { width: 1600, height: 1000 } },
  webServer: {
    command: `"${process.env.INSPECTOR_PYTHON ?? "python"}" examples/gradio_demo.py`,
    url: "http://127.0.0.1:7878", timeout: 60000, reuseExistingServer: false,
    env: { GRADIO_SERVER_PORT: "7878", GRADIO_ANALYTICS_ENABLED: "False" },
  },
});
