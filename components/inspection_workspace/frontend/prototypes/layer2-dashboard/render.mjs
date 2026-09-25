import { chromium } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { mkdir } from 'node:fs/promises';

const here = dirname(fileURLToPath(import.meta.url));
const output = join(here, 'renders');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
});
const page = await browser.newPage({ viewport: { width: 430, height: 932 }, deviceScaleFactor: 2 });
const names = {
  A: 'comparison-deck',
  B: 'evidence-ledger',
  C: 'field-lab',
  D: 'entity-navigator',
  E: 'change-story',
  F: 'mission-control',
};
for (const [key, name] of Object.entries(names)) {
  await page.goto(`file://${join(here, 'index.html')}?variant=${key}`);
  await page.screenshot({ path: join(output, `${key}-${name}.png`), fullPage: false });
}
await browser.close();
