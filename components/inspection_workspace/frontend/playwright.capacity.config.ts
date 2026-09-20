import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testDir:'tests/capacity',timeout:900_000});
