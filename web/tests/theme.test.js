// Node tests for web/shared/theme.js (TECH-DEBT P3: JS-level tests).
// Run: node --test web/tests/
"use strict";
const { test } = require("node:test");
const assert = require("node:assert");
const { FEN_LIGHT, STATUS_COLOR, fenStatusColor } = require("../shared/theme.js");

test("light palette has all keys used by the portal views", () => {
  for (const k of ["bl", "gr", "rd", "gd", "hs", "ink", "mu"]) {
    assert.ok(/^#[0-9a-f]{6}$/i.test(FEN_LIGHT[k]), `FEN_LIGHT.${k} is a hex color`);
  }
});

test("status colors are consistent with the portal CSS palette", () => {
  // These hex values MUST match web/portal/index.html + triadic.html CSS.
  assert.strictEqual(STATUS_COLOR.validated, "#2e7d5b");
  assert.strictEqual(STATUS_COLOR.disputed, "#8b6914");
  assert.strictEqual(STATUS_COLOR.rejected, "#b23a3a");
  assert.strictEqual(STATUS_COLOR.pending, "#2d5a8e");
});

test("fenStatusColor falls back to muted for unknown statuses", () => {
  assert.strictEqual(fenStatusColor("validated"), "#2e7d5b");
  assert.strictEqual(fenStatusColor("weird-status"), FEN_LIGHT.mu);
});
