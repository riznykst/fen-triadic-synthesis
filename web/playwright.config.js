// Playwright config for the FEN UI e2e (BACKLOG P3 "UI e2e test").
// Runs against the LIVE local/CI stack (status-api :8082 serves /web,
// mock-fen-api :8100): docker compose up -d first, then
//   npx playwright test            # from web/
// The CI e2e job runs the same command after its docker compose up.
"use strict";
const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  retries: 0,
  workers: 1, // one shared stack; candidates are global state
  use: {
    baseURL: "http://localhost:8082",
    headless: true,
  },
  reporter: [["list"]],
});
