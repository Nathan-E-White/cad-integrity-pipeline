import { test, expect } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';

let directory: string;
let source: string;
let refusedSource: string;
test.beforeAll(() => {
    directory = mkdtempSync(join(tmpdir(), 'native-inspection-browser-'));
    source = join(directory, 'asymmetric.step');
    refusedSource = join(directory, 'open-face.step');
    execFileSync(resolve('../../../.pixi/envs/default/bin/python'), ['-c',
        'import sys; from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox; from cad_integrity.adapters.ocp import export_checked_step; export_checked_step(BRepPrimAPI_MakeBox(2,3,5).Shape(), sys.argv[1])', source]);
    execFileSync(resolve('../../../.pixi/envs/default/bin/python'), ['-c',
        'import sys; from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace; from OCP.gp import gp_Pln,gp_Pnt,gp_Dir; from OCP.STEPControl import STEPControl_Writer,STEPControl_AsIs; w=STEPControl_Writer(); w.Transfer(BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(0,0,0),gp_Dir(0,0,1)),0,2,0,3).Face(),STEPControl_AsIs); w.Write(sys.argv[1])', refusedSource]);
});
test.afterAll(() => rmSync(directory, { recursive: true, force: true }));

test('STEP workspace selects native faces in each scope and clears replacement', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto('/');
    await page.getByRole('tab', { name: 'Local STEP workbench', exact: true }).click();
    await page.locator('input[type=file][accept*=".step"]').setInputFiles(source);
    const run = page.getByRole('button', { name: 'Audit and attempt configured repair', exact: true });
    await run.click();
    const workspace = page.getByRole('region', { name: 'Native inspection', exact: true });
    await expect(workspace.getByRole('table', { name: 'Original entities' })).toBeVisible();
    await expect(workspace.locator('canvas')).toHaveCount(2);
    await expect(workspace.getByLabel('Picking', { exact: true }).locator('option')).toHaveText(['Native face']);
    await workspace.getByRole('button', { name: 'Native face 0', exact: true }).click();
    await expect(workspace.getByRole('status', { name: 'Selection' })).toContainText('Native face 0');
    await workspace.getByRole('button', { name: 'Candidate', exact: true }).click();
    await expect(workspace.getByRole('status', { name: 'Selection' })).toHaveCount(0);
    await workspace.getByRole('button', { name: 'Native face 1', exact: true }).click();
    await workspace.getByRole('button', { name: 'Original', exact: true }).click();
    await expect(workspace.getByRole('status', { name: 'Selection' })).toContainText('Native face 0');
    // A real canvas pick uses the native face mapping, not a table-only path.
    await workspace.getByRole('button', { name: 'Clear selection', exact: true }).click();
    await expect(workspace.getByRole('status', { name: 'Selection' })).toHaveCount(0);
    const canvas = workspace.locator('canvas').first();
    await canvas.click({ position: { x: (await canvas.boundingBox())!.width / 2, y: 230 } });
    await expect(workspace.getByRole('status', { name: 'Selection' })).toContainText('Native face');
    await page.screenshot({ path: 'test-results/native-inspection.png', fullPage: true });
    await expect(run).toBeEnabled();
    await run.click();
    await expect(workspace.getByRole('status', { name: 'Selection' })).toHaveCount(0);
    await expect(workspace.getByRole('table', { name: 'Original entities' })).toBeVisible();
    expect(errors).toEqual([]);
});

test('refused native candidate keeps face-only picking across the vacant pane', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('tab', { name: 'Local STEP workbench', exact: true }).click();
    await page.locator('input[type=file][accept*=".step"]').setInputFiles(refusedSource);
    await page.getByRole('button', { name: 'Audit and attempt configured repair', exact: true }).click();
    const workspace = page.getByRole('region', { name: 'Native inspection', exact: true });
    await expect(workspace.getByRole('table', { name: 'Original entities' })).toBeVisible();
    await expect(workspace.locator('canvas')).toHaveCount(1);
    await workspace.getByRole('button', { name: 'Candidate', exact: true }).click();
    await expect(workspace.getByLabel('Picking', { exact: true }).locator('option')).toHaveText(['Native face']);
    await expect(workspace.getByLabel('Defects only', { exact: true })).toHaveCount(0);
    await workspace.getByLabel('Picking', { exact: true }).selectOption('native_face');
    await workspace.getByRole('button', { name: 'Original', exact: true }).click();
    const canvas = workspace.locator('canvas').first();
    await canvas.click({ position: { x: (await canvas.boundingBox())!.width / 2, y: 230 } });
    await expect(workspace.getByRole('status', { name: 'Selection' })).toContainText('Native face');
});
