import { chromium } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import { dirname, join, normalize } from 'node:path';
import { mkdir } from 'node:fs/promises';
const here=dirname(fileURLToPath(import.meta.url)),root=normalize(join(here,'../..')),output=join(here,'renders');await mkdir(output,{recursive:true});
const server=Bun.serve({port:48767,fetch(req){const path=new URL(req.url).pathname==='/'?'/prototypes/desktop-engineering/index.html':new URL(req.url).pathname;return new Response(Bun.file(join(root,path)))}});
const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});const page=await browser.newPage({viewport:{width:1600,height:1000},deviceScaleFactor:2});
const pageErrors=[];page.on('pageerror',error=>pageErrors.push(error.message));
const names={A:'topology-workbench',B:'revision-compare',C:'surface-uv',D:'quality-field',E:'trace-solver'};
for(const [key,name] of Object.entries(names)){
  await page.goto(`http://127.0.0.1:48767/prototypes/desktop-engineering/index.html?variant=${key}`);await page.waitForTimeout(900);await page.screenshot({path:join(output,`${key}-${name}.png`),fullPage:false});
  if(key==='B'){await page.locator('#camera-sync').click();if(!await page.locator('#camera-sync').textContent().then(x=>x.includes('INDEPENDENT')))throw new Error('camera sync toggle failed')}
  if(key==='D'){
    if(!await page.locator('.probe-status').textContent().then(x=>x.includes('PROBE OFF')))throw new Error('cross-probe should start clear');
    await page.locator('[data-bin="7"]').click();if(!await page.locator('.probe-status').textContent().then(x=>x.includes('WHITE FENCE')))throw new Error('context-isolation cross-probe failed');
    await page.waitForTimeout(200);await page.screenshot({path:join(output,'D-quality-field-probe-active.png'),fullPage:false});
    await page.locator('[data-bin="7"]').click();if(!await page.locator('.probe-status').textContent().then(x=>x.includes('PROBE OFF')))throw new Error('cross-probe clear failed');
  }
}
await browser.close();server.stop();if(pageErrors.length)throw new Error(pageErrors.join('\n'));
