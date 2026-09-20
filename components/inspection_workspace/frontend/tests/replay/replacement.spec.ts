import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
test('dense maximum-capacity replay survives ten replacements with all entities reachable', async ({ page, browser }) => {
    const protocol = await browser.newBrowserCDPSession();
    const memory = async () => {
        const result = await protocol.send('SystemInfo.getProcessInfo');
        return result.processInfo.reduce((sum, p) => {
            try {
                return sum + Number(execFileSync('ps', ['-o', 'rss=', '-p', String(p.id)], { encoding: 'utf8' }).trim()) * 1024;
            }
            catch {
                return sum;
            }
        }, 0);
    };
    const errors: string[] = [];
    page.on('pageerror', e => { errors.push(e.message); console.error(e.message); });
    page.on('crash', () => { page.close().catch(() => { }); });
    await page.goto('/');
    const idle = await memory();
    const loads: number[] = [];
    const cdp = await page.context().newCDPSession(page);
    let peak = idle;
    let sampling = false;
    const sampler = setInterval(async () => {
        if (sampling)
            return;
        sampling = true;
        try {
            peak = Math.max(peak, await memory());
        }
        catch { }
        finally {
            sampling = false;
        }
    }, 1000);
    page.on('close', () => clearInterval(sampler));
    async function run() { const start = Date.now(); await page.getByRole('button', { name: 'Run this example', exact: true }).click(); await expect(page.locator('canvas')).toHaveCount(0); await expect(page.getByRole('table', { name: 'Original entities' })).toBeVisible({ timeout: 120000 }); await expect(page.getByRole('button', { name: 'Run this example', exact: true })).toBeEnabled(); await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))); loads.push(Date.now() - start); console.log('load-ms', loads.at(-1)); await expect(page.locator('canvas')).toHaveCount(2); }
    await run();
    await cdp.send('HeapProfiler.collectGarbage');
    const initial = await memory();
    const responses: Record<string, number> = {};
    async function timed(label: string, selector: string, action: 'click' | 'change', value?: string) {
        responses[label] = await page.evaluate(async ({ selector, action, value }) => {
            const element = document.querySelector(selector) as HTMLInputElement;
            const start = performance.now();
            if (action === 'click')
                element.click();
            else {
                element.value = value!;
                element.dispatchEvent(new Event('change', { bubbles: true }));
            }
            await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
            return performance.now() - start;
        }, { selector, action, value });
    }
    await page.getByLabel('Defects only', { exact: true }).uncheck();
    for (const [kind, last] of [['vertex', 249999], ['edge', 749999], ['polygonal_face', 499999]] as const) {
        await page.getByLabel('Entity kind', { exact: true }).selectOption(kind);
        await page.getByRole('button', { name: 'Last', exact: true }).click();
        const label = `${kind === 'polygonal_face' ? 'Face' : kind === 'vertex' ? 'Vertex' : 'Edge'} ${last}`;
        await page.getByRole('button', { name: label, exact: true }).evaluate(e => e.setAttribute('data-capacity-target', 'true'));
        await timed(kind, '[data-capacity-target]', 'click');
        await expect(page.getByRole('status', { name: 'Selection' })).toContainText(label);
        await page.getByRole('button', { name: label, exact: true }).evaluate(e => e.removeAttribute('data-capacity-target'));
    }
    await timed('filter', 'select[aria-label="Category"]', 'change', 'unused_vertices');
    await page.getByLabel('Clip original', { exact: true }).evaluate(e => e.setAttribute('data-capacity-clip', 'true'));
    await timed('clipping', '[data-capacity-clip]', 'click');
    console.log('interaction-ms', responses);
    await page.getByRole('button', { name: 'Maximize', exact: true }).first().click();
    await page.setViewportSize({ width: 1200, height: 900 });
    await page.getByRole('button', { name: 'Restore', exact: true }).click();
    for (let i = 0; i < 10; i++) {
        await run();
        await expect(page.getByRole('status', { name: 'Selection' })).toHaveCount(0);
    }
    await cdp.send('HeapProfiler.collectGarbage');
    const final = await memory();
    clearInterval(sampler);
    peak = Math.max(peak, final);
    const evidence = { sampledPeakDeltaBytes: peak - idle, memorySampleIntervalMs: 1000, browser: browser.version(), loadsMs: loads, interactionMs: responses, residentDeltaBytes: initial - idle, retainedGrowthBytes: final - initial, errors, denseMemberships: true, replacements: 10 };
    writeFileSync('../../../docs/evidence/polygonal-inspection/browser-dense-replacement.json', JSON.stringify(evidence, null, 2) + '\n');
    expect(errors).toEqual([]);
    expect(Math.max(...loads)).toBeLessThan(30000);
    expect(Math.max(...Object.values(responses))).toBeLessThan(500);
    expect(peak - idle).toBeLessThan(4 * 1024 ** 3);
    expect(final - initial).toBeLessThan(256 * 1024 ** 2);
    await page.screenshot({ path: 'test-results/inspection-dense-capacity.png', fullPage: true });
});
