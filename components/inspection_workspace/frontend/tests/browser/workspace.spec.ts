import { test, expect } from '@playwright/test';
test('installed parent renders both panes, selects a face, preserves selection and clears on a new run', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', e => { errors.push(e.message); console.error(e.stack || String(e)); });
    page.on('console', m => {
        if (m.type() === 'error')
            console.error(m.text());
    });
    page.on('response', r => {
        if (r.status() >= 400)
            console.error(r.status(), r.url());
    });
    await page.goto('/');
    await page.getByRole('button', { name: 'Run this example', exact: true }).click();
    const workspace = page.getByRole('region', { name: 'Polygonal inspection' });
    await expect(page.getByRole('table', { name: 'Original entities' })).toBeVisible();
    await expect(page.locator('canvas')).toHaveCount(2);
    await page.getByLabel('Defects only', { exact: true }).uncheck();
    await page.getByRole('button', { name: 'Face 0', exact: true }).click();
    await expect(page.getByRole('status', { name: 'Selection' })).toContainText('Face 0');
    await page.getByLabel('Picking', { exact: true }).selectOption('vertex');
    await expect(page.getByRole('status', { name: 'Selection' })).toContainText('Face 0');
    await page.getByRole('button', { name: 'Candidate', exact: true }).click();
    await expect(page.getByRole('table', { name: 'Candidate entities' })).toBeVisible();
    await page.getByRole('button', { name: 'Original', exact: true }).click();
    await expect(page.getByRole('status', { name: 'Selection' })).toContainText('Face 0');
    await page.getByRole('button', { name: 'Maximize', exact: true }).first().click();
    await expect(page.getByRole('button', { name: 'Restore', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Restore', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Run this example', exact: true })).toBeEnabled();
    await page.getByRole('button', { name: 'Run this example', exact: true }).click();
    await expect(page.getByRole('status', { name: 'Selection' })).toHaveCount(0);
    await expect(page.getByRole('table', { name: 'Original entities' })).toBeVisible();
    expect(errors).toEqual([]);
});
test('hover and clipping stay local without geometry allocation; context loss recovers', async ({ page }) => {
    await page.addInitScript(() => {
        (window as any).bufferAllocations = 0;
        const original = WebGL2RenderingContext.prototype.bufferData;
        WebGL2RenderingContext.prototype.bufferData = function (...args: any[]) { (window as any).bufferAllocations++; return original.apply(this, args as any); };
    });
    await page.goto('/');
    await page.getByRole('button', { name: 'Run this example', exact: true }).click();
    await expect(page.getByRole('table', { name: 'Original entities' })).toBeVisible();
    await page.getByLabel('Defects only', { exact: true }).uncheck();
    await page.getByRole('button', { name: 'Face 0', exact: true }).click();
    await page.locator('canvas').first().screenshot();
    const allocations = await page.evaluate(() => (window as any).bufferAllocations);
    const computations: string[] = [];
    page.on('request', r => {
        if (r.url().includes('/queue/join'))
            computations.push(r.url());
    });
    await page.getByRole('button', { name: 'Face 1', exact: true }).hover();
    await page.getByRole('heading', { name: 'CAD Integrity Lab', exact: true }).hover();
    await expect(page.getByRole('status', { name: 'Selection' })).toContainText('Face 0');
    await page.getByLabel('X-ray', { exact: true }).check();
    await page.getByLabel('Clip original', { exact: true }).check();
    await page.getByLabel('Category', { exact: true }).selectOption('unused_vertices');
    await expect(page.getByRole('status', { name: 'Selection' })).toContainText('Face 0');
    await page.locator('canvas').first().screenshot();
    expect(await page.evaluate(() => (window as any).bufferAllocations)).toBe(allocations);
    expect(computations).toEqual([]);
    await page.locator('canvas').first().evaluate(canvas => {
        const gl = (canvas as HTMLCanvasElement).getContext('webgl2')!;
        const extension = gl.getExtension('WEBGL_lose_context')!;
        (canvas as any).restoreTestContext = () => extension.restoreContext();
        extension.loseContext();
    });
    await expect(page.getByRole('alert')).toContainText('WebGL context lost');
    await page.locator('canvas').first().evaluate(canvas => { (canvas as any).restoreTestContext(); });
    await expect(page.getByRole('alert')).toHaveCount(0);
    await page.screenshot({ path: 'test-results/inspection-parent.png', fullPage: true });
});
test('restricted upload reaches the same installed workspace', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('tab', { name: 'Upload your NPZ', exact: true }).click();
    await page.locator('input[type=file]').first().setInputFiles('../../../examples/pathological-mesh-fixtures/meshes/00_clean_boss.npz');
    await page.getByRole('button', { name: 'Analyze mesh', exact: true }).click();
    await expect(page.getByRole('table', { name: 'Original entities' })).toBeVisible();
    await expect(page.locator('canvas')).toHaveCount(2);
    await expect(page.getByRole('button', { name: 'Analyze mesh', exact: true })).toBeEnabled();
});
test('rejected candidate leaves its pane vacant and a subsequent invalid start cannot restore old results', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('combobox').first().click();
    await page.getByRole('option', { name: 'Pinched vertex', exact: true }).click();
    await page.getByRole('button', { name: 'Run this example', exact: true }).click();
    await expect(page.getByRole('table', { name: 'Original entities' })).toBeVisible();
    await expect(page.locator('canvas')).toHaveCount(1);
    await expect(page.getByRole('button', { name: 'Maximize', exact: true }).last()).toBeDisabled();
    const widths = await page.locator('.pane').evaluateAll(nodes => nodes.map(n => n.getBoundingClientRect().width));
    expect(Math.abs(widths[0] - widths[1])).toBeLessThan(2);
    await page.getByRole('tab', { name: 'Upload your NPZ', exact: true }).click();
    await page.getByRole('button', { name: 'Analyze mesh', exact: true }).click();
    await expect(page.locator('canvas')).toHaveCount(0);
    await expect(page.getByRole('table', { name: 'Original entities' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Analyze mesh', exact: true })).toBeEnabled();
});
test('viewport picking produces a source face selection and explicit focus remains available', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Run this example', exact: true }).click();
    await expect(page.getByRole('table', { name: 'Original entities' })).toBeVisible();
    const canvas = page.locator('canvas').first();
    const box = await canvas.boundingBox();
    await canvas.click({ position: { x: box!.width / 2, y: box!.height / 2 } });
    await expect(page.getByRole('status', { name: 'Selection' })).toContainText(/Face \d+/);
    await page.getByRole('button', { name: 'Focus selection', exact: true }).click();
    await expect(page.locator('canvas')).toHaveCount(2);
});
