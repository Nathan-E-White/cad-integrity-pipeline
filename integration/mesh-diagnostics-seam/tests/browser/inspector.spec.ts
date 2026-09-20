import { test, expect } from "@playwright/test";

test("comparison, selection, clear, replacement and invalid documents", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("http://127.0.0.1:5178");
  await expect(page.locator("canvas")).toHaveCount(2);
  await page.getByRole("button", { name: "Boundary edges", exact: false }).first().click();
  await expect(page.getByRole("button", { name: "Focus selection" }).first()).toBeEnabled();
  await page.getByRole("button", { name: "Clear selection" }).first().click();
  await expect(page.getByRole("button", { name: "Focus selection" }).first()).toBeDisabled();
  await page.getByRole("button", { name: "Single mesh", exact: true }).click();
  await expect(page.locator("canvas")).toHaveCount(1);
  await page.getByRole("button", { name: "Clear document", exact: true }).click();
  await expect(page.locator("canvas")).toHaveCount(0);
  await expect(page.getByText("No mesh to inspect.")).toBeVisible();
  await page.getByRole("button", { name: "Load comparison", exact: true }).click();
  await expect(page.locator("canvas")).toHaveCount(2);
  await page.getByRole("button", { name: "Invalid document", exact: true }).click();
  await expect(page.locator("canvas")).toHaveCount(0);
  await expect(page.getByRole("alert")).toContainText("Invalid mesh document");
  expect(errors).toEqual([]);
});

test("controls, hidden resize, context recovery and repeated mounts", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  await page.goto("http://127.0.0.1:5178");
  await expect(page.locator("canvas")).toHaveCount(2);
  await page.getByLabel("Face scalar", { exact: true }).first().selectOption("mean-ratio");
  await expect(page.getByLabel("Triangle mean ratio (unsigned) color legend")).toBeVisible();
  await page.getByLabel("Plane clip", { exact: true }).first().check();
  await page.getByLabel("Clip axis", { exact: true }).first().selectOption("1");
  await page.getByRole("button", { name: "Hide inspector", exact: true }).click();
  await page.setViewportSize({ width: 1000, height: 850 });
  await page.getByRole("button", { name: "Show inspector", exact: true }).click();
  await expect(page.locator("canvas").first()).toBeVisible();
  // Exercise the browser's actual WebGL context-loss extension.
  await page.locator("canvas").first().evaluate(canvas => {
    const gl = (canvas as HTMLCanvasElement).getContext("webgl2")!;
    const extension = gl.getExtension("WEBGL_lose_context")!;
    extension.loseContext();
    setTimeout(() => extension.restoreContext(), 300);
  });
  await expect(page.getByRole("alert")).toContainText("WebGL context lost");
  await expect(page.getByRole("alert")).toHaveCount(0);
  for (let i = 0; i < 3; i++) {
    await page.getByRole("button", { name: "Unmount inspector", exact: true }).click();
    await expect(page.locator("canvas")).toHaveCount(0);
    await page.getByRole("button", { name: "Mount inspector", exact: true }).click();
    await expect(page.locator("canvas")).toHaveCount(2);
  }
  await page.screenshot({ path: "test-results/inspector.png", fullPage: true });
  expect(errors).toEqual([]);
});

test("failed viewport setup releases its canvas and leaves metrics readable", async ({ page }) => {
  await page.addInitScript(() => {
    window.ResizeObserver = class {
      constructor() { throw new Error("Resize observation unavailable"); }
    } as unknown as typeof ResizeObserver;
  });
  await page.goto("http://127.0.0.1:5178");
  await expect(page.getByRole("alert").first()).toContainText("Resize observation unavailable");
  await expect(page.getByRole("heading", { name: "Diagnostic audit" }).first()).toBeVisible();
  await expect(page.locator("canvas")).toHaveCount(0);
});

test("camera links follow orbit while independent panes keep their pose", async ({ page }) => {
  await page.goto("http://127.0.0.1:5178");
  const canvases = page.locator("canvas");
  await expect(canvases).toHaveCount(2);
  const settle = () => page.waitForTimeout(700); // OrbitControls damping must settle before pixel comparison.
  const orbit = async () => {
    const box = (await canvases.first().boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2 + 85, box.y + box.height / 2 + 55, { steps: 12 });
    await page.mouse.up();
    await settle();
  };
  await settle();
  const linkedBefore = await canvases.nth(1).screenshot();
  await orbit();
  expect((await canvases.nth(1).screenshot()).equals(linkedBefore)).toBe(false);
  await page.getByRole("button", { name: "Independent views", exact: true }).click();
  await expect(canvases).toHaveCount(2);
  await settle();
  const independentBefore = await canvases.nth(1).screenshot();
  await orbit();
  expect((await canvases.nth(1).screenshot()).equals(independentBefore)).toBe(true);
});
