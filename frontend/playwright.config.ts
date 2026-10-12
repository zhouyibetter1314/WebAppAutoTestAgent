import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  use: {
    baseURL: 'http://127.0.0.1:5173',
    headless: true,
    launchOptions: { executablePath: process.env.WAAT_BROWSER_EXECUTABLE || undefined },
  },
  webServer: [
    {
      command: '../.venv/bin/python ../scripts/e2e_server.py',
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: false,
    },
    { command: 'pnpm dev', url: 'http://127.0.0.1:5173', reuseExistingServer: false },
  ],
})
