import { test, expect } from '@playwright/test';
import { writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
test('full admitted source and candidate remain reachable in the installed parent', async ({ page, browser }) => {
    const protocol = await browser.newBrowserCDPSession();
    const memory = async () => {
        const result = await protocol.send('SystemInfo.getProcessInfo');
        let rss = 0;
        for (const p of result.processInfo) {
            try {
                rss += Number(execFileSync('ps', ['-o', 'rss=', '-p', String(p.id)], { encoding: 'utf8' }).trim()) * 1024;
            }
            catch { }
        }
        return rss;
    };
    const before = await memory();
    const errors: string[] = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('crash', () => { console.error('Capacity browser crashed'); page.close().catch(() => { }); });
    await page.goto('/');
    await page.getByRole('tab', { name: 'Upload your NPZ', exact: true }).click();
    await page.locator('input[type=file]').first().setInputFiles('/private/tmp/polygonal-inspection-capacity.npz');
    await page.getByText('Upload stitching policy', { exact: true }).click();
    await page.getByLabel('Weld nearby boundary vertices', { exact: true }).uncheck();
    await page.getByLabel('Synchronize face orientation', { exact: true }).uncheck();
    const started = Date.now();
    await page.getByRole('button', { name: 'Analyze mesh', exact: true }).click();
    await expect(page.getByRole('table', { name: 'Original entities' })).toBeVisible({ timeout: 300000 });
    const controllerAndDeliveryMs = Date.now() - started;
    await expect(page.locator('canvas')).toHaveCount(2);
    const selected = Date.now();
    await page.getByLabel('Defects only', { exact: true }).uncheck();
    await page.getByRole('button', { name: 'Last', exact: true }).click();
    await page.getByRole('button', { name: 'Face 499999', exact: true }).click();
    await expect(page.getByRole('status', { name: 'Selection' })).toContainText('Face 499999');
    const interactionMs = Date.now() - selected;
    const used = (await memory()) - before;
    const evidence = { controllerAndDeliveryMs, interactionSequenceMs: interactionMs, browserResidentDeltaBytes: used, errors,
        trianglesPerPane: 500000, verticesPerPane: 250000 };
    writeFileSync('../../../docs/evidence/polygonal-inspection/browser-capacity.json', JSON.stringify(evidence, null, 2) + '\n');
    expect(errors).toEqual([]);
    expect(used).toBeLessThan(4 * 1024 ** 3);
    await page.screenshot({ path: 'test-results/inspection-capacity.png', fullPage: true });
});
