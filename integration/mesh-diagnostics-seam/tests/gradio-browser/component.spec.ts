import { test, expect } from "@playwright/test";

test("installed Gradio assets load, replace, clear and survive hidden resize", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  await page.goto("http://127.0.0.1:7878");
  await expect(page.getByText("No mesh to inspect.")).toBeVisible();
  await page.getByRole("button", { name: "Load illustrative comparison", exact: true }).click();
  await expect(page.locator("canvas")).toHaveCount(2);
  await expect(page.getByRole("heading", { name: "Original · artificial defects", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Boundary edges", exact: false }).first().click();
  await expect(page.getByRole("button", { name: "Focus selection" }).first()).toBeEnabled();
  await page.getByRole("button", { name: "Hide inspector", exact: true }).click();
  await expect(page.locator("canvas").first()).toBeHidden();
  await page.setViewportSize({ width: 1100, height: 900 });
  await page.getByRole("button", { name: "Show inspector", exact: true }).click();
  await expect(page.locator("canvas").first()).toBeVisible();
  await page.getByRole("button", { name: "Clear document", exact: true }).click();
  await expect(page.locator("canvas")).toHaveCount(0);
  await expect(page.getByText("No mesh to inspect.")).toBeVisible();
  await page.getByRole("button", { name: "Load illustrative comparison", exact: true }).click();
  await expect(page.locator("canvas")).toHaveCount(2);
  await expect(page.getByRole("button", { name: "Focus selection" }).first()).toBeDisabled();
  await page.screenshot({ path: "test-results/gradio.png", fullPage: true });
  expect(errors).toEqual([]);
});

test("installed host loading, dynamic mounting and WebGL recovery", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  await page.goto("http://127.0.0.1:7878");
  await page.getByRole("button", { name: "Preview loading state", exact: true }).click();
  await expect(page.getByText("Fixture loading preview", { exact: false })).toBeVisible();
  await expect(page.getByText("Fixture loading preview", { exact: false })).toHaveCount(0);
  await expect(page.locator("canvas")).toHaveCount(2);
  await page.locator("canvas").first().evaluate(canvas => {
    const gl = (canvas as HTMLCanvasElement).getContext("webgl2")!;
    const extension = gl.getExtension("WEBGL_lose_context")!;
    extension.loseContext();
    setTimeout(() => extension.restoreContext(), 300);
  });
  await expect(page.getByRole("alert")).toContainText("WebGL context lost");
  await expect(page.getByRole("alert")).toHaveCount(0);
  await page.getByLabel("Mount inspector", { exact: true }).uncheck();
  await expect(page.locator("canvas")).toHaveCount(0);
  await expect(page.getByText("No mesh to inspect.")).toHaveCount(0);
  await page.getByLabel("Mount inspector", { exact: true }).check();
  await expect(page.getByText("No mesh to inspect.")).toBeVisible();
  await page.getByRole("button", { name: "Load illustrative comparison", exact: true }).click();
  await expect(page.locator("canvas")).toHaveCount(2);
  await page.screenshot({ path: "test-results/gradio.png", fullPage: true });
  expect(errors).toEqual([]);
});
