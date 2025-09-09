import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: 'tests',
  timeout: 600_000, // 10 min – 스크롤 캡처/렌더 여유
  expect: { timeout: 180_000 },
  workers: 1,
  use: {
    headless: true,
    baseURL: process.env.WEB_URL || 'http://localhost:3100',
    actionTimeout: 60_000,
    navigationTimeout: 120_000,
  },
  reporter: [['list']],
  webServer: {
    command: 'npm run dev',
    url: process.env.WEB_URL || 'http://localhost:3100',
    reuseExistingServer: true,
    timeout: 180_000,
    stdout: 'pipe',
    stderr: 'pipe',
  },
});

