import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testDir:'tests/replay',timeout:300000,
 webServer:{...base.webServer,command:'.pixi/envs/default/bin/python scripts/run_inspection_capacity_replay.py'}});
