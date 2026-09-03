// FEN UI end-to-end tests (BACKLOG P3). Zero-build portal views are served
// by status-api (/web) and talk to the mock DAO on :8100 — run against a
// live stack: docker compose up -d, then `npx playwright test` from web/.
"use strict";
const { test, expect } = require("@playwright/test");

const PORTAL = "/web/portal/index.html";
const TRIADIC = "/web/portal/triadic.html";
const WIDGET = "/web/widget/demo.html";

function collectPageErrors(page) {
  const errors = [];
  page.on("pageerror", (err) => errors.push(String(err)));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push("console.error: " + msg.text());
  });
  return errors;
}

test("classic portal loads without JS errors", async ({ page }) => {
  const errors = collectPageErrors(page);
  await page.goto(PORTAL);
  await expect(page.locator("h1")).toContainText("FEN");
  await expect(page.locator("#submit")).toBeVisible();
  await expect(page.locator("#auto_toggle")).toContainText("Live updates");
  await page.waitForTimeout(1500); // let SSE connect + first load settle
  expect(errors).toEqual([]);
});

test("portal submits a candidate that flips to validated via SSE", async ({ page }) => {
  const label = "UI e2e entity " + Date.now();
  await page.goto(PORTAL);
  await page.fill("#entity_label", label);
  await page.click("#submit");
  await expect(page.locator("#submit_err")).toContainText("accepted", { timeout: 15000 });
  // auto mode: the mock decides after ~3s; the SSE stream must flip the row.
  const row = page.locator("#rows tr", { hasText: label });
  await expect(row.locator(".b-validated")).toBeVisible({ timeout: 45000 });
});

test("triadic view loads without JS errors", async ({ page }) => {
  const errors = collectPageErrors(page);
  await page.goto(TRIADIC);
  await expect(page.locator("h1")).toContainText("Validation Commons");
  await expect(page.locator("#run")).toContainText("Scaffolding Agent");
  await page.waitForTimeout(1500);
  expect(errors).toEqual([]);
});

test("triadic scaffold run produces a triple row", async ({ page }) => {
  await page.goto(TRIADIC);
  await page.fill("#text", "The biennial fair of St. Michael's was held on the first Sunday after Michaelmas");
  await page.click("#run");
  await expect(page.locator("#steps .step").first()).toBeVisible({ timeout: 30000 });
  await expect(page.locator("#scaffoldErr")).not.toContainText("failed");
});

test("flow-2 widget demo loads and renders status badges", async ({ page }) => {
  const errors = collectPageErrors(page);
  await page.goto(WIDGET);
  await expect(page.locator("h1")).toContainText("FEN status widget");
  const badges = page.locator("fen-status");
  await expect(badges).toHaveCount(3);
  await page.waitForTimeout(1500);
  expect(errors).toEqual([]);
});
