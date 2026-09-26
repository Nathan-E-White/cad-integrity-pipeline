import { test, expect } from '@playwright/test';
test('unfinished application chrome is keyboard accessible and stays browser local', async ({ page }) => {
    const queued: string[] = [];
    page.on('request', request => {
        if (request.url().includes('/queue/join')) queued.push(request.url());
    });
    await page.goto('/');
    const tooltip = page.getByRole('status', { name: 'Unavailable action' });
    const menuNames = ['File', 'View', 'Selection', 'Fields', 'Analysis'];
    for (const [index, name] of menuNames.entries()) {
        const control = page.getByRole('button', { name, exact: true });
        await control.focus();
        await page.keyboard.press(index % 2 === 0 ? 'Space' : 'Enter');
        await expect(tooltip).toContainText('Not ready yet.');
        await expect(control).toHaveAttribute('aria-describedby', 'cad-unavailable-tooltip');
    }
    const file = page.getByRole('button', { name: 'File', exact: true });
    await file.click();
    await page.waitForTimeout(50);
    const filePosition = await tooltip.boundingBox();
    const analysis = page.getByRole('button', { name: 'Analysis', exact: true });
    await analysis.click();
    await page.waitForTimeout(50);
    const analysisPosition = await tooltip.boundingBox();
    expect(Math.abs(analysisPosition!.x - filePosition!.x)).toBeGreaterThan(10);
    expect(analysisPosition!.x).toBeGreaterThanOrEqual(8);
    expect(analysisPosition!.x + analysisPosition!.width).toBeLessThanOrEqual(
        await page.evaluate(() => window.innerWidth - 8)
    );
    await analysis.click();
    await page.waitForTimeout(900);
    await analysis.click();
    await page.waitForTimeout(500);
    await expect(tooltip).toHaveAttribute('data-visible', 'true');
    await page.keyboard.press('Escape');
    await expect(tooltip).not.toHaveAttribute('data-visible', 'true');
    await page.getByRole('button', { name: 'View', exact: true }).click();
    await expect(tooltip).toHaveAttribute('data-visible', 'true');
    await expect(tooltip).not.toHaveAttribute('data-visible', 'true', { timeout: 2500 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    expect(await tooltip.evaluate(element => getComputedStyle(element).transitionDuration)).toBe('0s');
    expect(queued).toEqual([]);
});

test('shell controls remain reachable in a narrow desktop window', async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 800 });
    await page.goto('/');
    await expect(page.getByRole('button', { name: 'File', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: /^Run Setup/ })).toBeVisible();
    await page.getByRole('button', { name: 'Run this example', exact: true }).click();
    await expect(page.getByRole('region', { name: 'Polygonal inspection' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Artifacts', exact: true })).toBeVisible();
});

test('evidence dock retains each tab and its selected state', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Run this example', exact: true }).click();
    const evidence = page.getByRole('tab', { name: 'Evidence', exact: true });
    const verification = page.getByRole('tab', { name: 'Verification', exact: true });
    const artifacts = page.getByRole('tab', { name: 'Artifacts', exact: true });
    await expect(evidence).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByRole('region', { name: 'Topological & Geometric Delta Audit' })).toBeVisible();
    await verification.click();
    await expect(verification).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByRole('region', { name: 'Verification' })).toBeVisible();
    await artifacts.click();
    await expect(artifacts).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByText('Original source', { exact: true })).toBeVisible();
    await evidence.click();
    await expect(evidence).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByRole('region', { name: 'Topological & Geometric Delta Audit' })).toBeVisible();
});

test('workspace presents human geometry identity without rendering revision digests', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Run this example', exact: true }).click();
    const workspace = page.getByRole('region', { name: 'Polygonal inspection' });
    await workspace.getByRole('button', { name: 'Expand docks', exact: true }).click();

    await expect(workspace.locator('.identity .geometry-identity')).toHaveText('Original geometry');
    await expect(workspace.getByRole('status', { name: 'Active geometry identity' })).toHaveText('Original geometry');
    await expect(workspace.locator('.tree-row').filter({ hasText: 'Original geometry' })).toBeVisible();
    await expect(workspace.locator('.tree-row').filter({ hasText: 'Candidate geometry' })).toBeVisible();
    const visibleIdentityChrome = [
        await workspace.innerText(),
        ...(await page.locator('#cad-evidence-dock [role="tab"]').allInnerTexts()),
    ].join('\n');
    expect(visibleIdentityChrome).not.toMatch(/\b[0-9a-f]{7,64}\b/i);

    await workspace.getByRole('button', { name: 'Candidate', exact: true }).click();
    await expect(workspace.locator('.identity .geometry-identity')).toHaveText('Candidate geometry');
    await expect(workspace.getByRole('status', { name: 'Active geometry identity' })).toHaveText('Candidate geometry');

    await page.getByRole('tab', { name: 'Artifacts', exact: true }).click();
    await expect(page.getByText('Raw JSON evidence', { exact: true })).toBeVisible();
    const downloads = page.locator('#cad-evidence-dock a[href*="/file="]');
    await expect(downloads).toHaveCount(4);
    const hrefs = await downloads.evaluateAll(anchors =>
        anchors.map(anchor => (anchor as HTMLAnchorElement).href)
    );
    expect(hrefs.some(href => href.endsWith('/decision-brief.md'))).toBe(true);
    expect(hrefs.some(href => href.endsWith('/evidence.json'))).toBe(true);
    for (const href of hrefs) {
        expect((await page.request.get(href)).ok()).toBe(true);
    }
});
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
    await expect(workspace.getByRole('region', { name: 'Model and entities' })).toBeVisible();
    await expect(workspace.getByRole('region', { name: 'Inspection viewport' })).toBeVisible();
    await expect(workspace.getByRole('region', { name: 'Validation and diagnostics' })).toBeVisible();
    await expect(workspace.getByRole('region', { name: 'Analytical instruments' })).toBeVisible();
    await expect(page.getByRole('table', { name: 'Original entities' })).toBeVisible();
    const visibleBox = (selector: string) => workspace.locator(selector).evaluateAll((nodes, label) => {
        const rect = nodes.map(node => node.getBoundingClientRect())
            .find(candidate => candidate.width > 0 && candidate.height > 0);
        if (!rect) throw new Error(`No rendered ${label} region`);
        return { x: rect.x, y: rect.y, width: rect.width };
    }, selector);
    const modelBounds = await visibleBox('.model-dock');
    const viewportBounds = await visibleBox('.viewport-deck');
    const validationBounds = await visibleBox('.validation-dock');
    const instrumentBounds = await visibleBox('.instrument-dock');
    expect(modelBounds!.x).toBeLessThan(viewportBounds!.x);
    expect(viewportBounds!.x).toBeLessThan(validationBounds!.x);
    expect(instrumentBounds!.y).toBeGreaterThan(viewportBounds!.y);
    expect(viewportBounds!.width).toBeGreaterThan(modelBounds!.width);
    await workspace.getByRole('button', { name: 'Expand docks', exact: true }).click();
    const cameraLink = workspace.getByRole('button', { name: 'Cameras linked', exact: true });
    await expect(cameraLink).toBeVisible();
    await expect(page.getByRole('table', { name: 'Original entities' })).toBeVisible();
    const canvases = workspace.locator('canvas');
    await expect(canvases).toHaveCount(2);
    const orbit = async () => {
        const box = (await canvases.first().boundingBox())!;
        await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
        await page.mouse.down();
        await page.mouse.move(box.x + box.width / 2 + 60, box.y + box.height / 2 + 20, {steps: 4});
        await page.mouse.up();
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    };
    const linkedBefore = await canvases.nth(1).screenshot();
    await orbit();
    expect((await canvases.nth(1).screenshot()).equals(linkedBefore)).toBe(false);
    await cameraLink.click();
    await expect(workspace.getByRole('button', { name: 'Independent cameras', exact: true })).toBeVisible();
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const independentBefore = await canvases.nth(1).screenshot();
    await orbit();
    expect((await canvases.nth(1).screenshot()).equals(independentBefore)).toBe(true);
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
    await page.getByRole('button', { name: /^Run Setup/ }).click();
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
    await page.getByRole('button', { name: 'Expand docks', exact: true }).click();
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
    await page.getByRole('button', { name: 'File', exact: true }).hover();
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
    await page.getByRole('button', { name: /^Run Setup/ }).click();
    await page.getByRole('tab', { name: 'Upload your NPZ', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Analyze mesh', exact: true })).toBeEnabled();
});
test('rejected candidate leaves its pane vacant and a subsequent invalid start cannot restore old results', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('combobox').first().click();
    await page.getByRole('option', { name: 'Pinched vertex', exact: true }).click();
    await page.getByRole('button', { name: 'Run this example', exact: true }).click();
    await expect(page.getByRole('table', { name: 'Original entities' })).toBeVisible();
    await expect(page.locator('canvas')).toHaveCount(1);
    await expect(page.getByRole('region', { name: 'Candidate' }).locator('.vacant')).toHaveText('Candidate geometry unavailable');
    await expect(page.getByRole('button', { name: 'Maximize', exact: true }).last()).toBeDisabled();
    const widths = await page.locator('.pane').evaluateAll(nodes => nodes.map(n => n.getBoundingClientRect().width));
    expect(Math.abs(widths[0] - widths[1])).toBeLessThan(2);
    await expect(page.getByRole('tab', { name: 'Upload your NPZ', exact: true })).toBeVisible();
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
