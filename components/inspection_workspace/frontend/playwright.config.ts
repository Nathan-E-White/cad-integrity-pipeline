import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'tests/browser',workers:1,timeout:60000,
 use:{browserName:'chromium',channel:'chrome',headless:true,viewport:{width:1600,height:1100},baseURL:'http://127.0.0.1:7863'},
 webServer:{command:'.pixi/envs/default/bin/python scripts/run_inspection_preview.py',cwd:'../../..',url:'http://127.0.0.1:7863',reuseExistingServer:false,timeout:60000},
});
