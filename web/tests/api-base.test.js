// Node tests for web/shared/api-base.js (TECH-DEBT P3: JS-level tests).
// Run: node --test web/tests/
"use strict";
const { test } = require("node:test");
const assert = require("node:assert");
const fenApiBase = require("../shared/api-base.js");

function fakeStorage(initial) {
  const m = new Map(Object.entries(initial || {}));
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => m.set(k, String(v)),
  };
}

test("fenApiBase falls back to the default when nothing is set", () => {
  const storage = fakeStorage();
  assert.strictEqual(fenApiBase("fen_mock_base", "http://localhost:8100", { search: "", storage }), "http://localhost:8100");
});

test("fenApiBase strips trailing slashes from the fallback", () => {
  const storage = fakeStorage();
  assert.strictEqual(fenApiBase("k", "http://x:8100/", { search: "", storage }), "http://x:8100");
});

test("fenApiBase query param wins and is persisted", () => {
  const storage = fakeStorage();
  const got = fenApiBase("fen_mock_base", "fb", { search: "?fen_mock_base=https://remote.example", storage });
  assert.strictEqual(got, "https://remote.example");
  assert.strictEqual(storage.getItem("fen_mock_base"), "https://remote.example");
});

test("fenApiBase localStorage is used when no query param", () => {
  const storage = fakeStorage({ fen_mock_base: "https://saved.example" });
  assert.strictEqual(fenApiBase("fen_mock_base", "fb", { search: "", storage }), "https://saved.example");
});

test("fenApiBase tolerates a missing storage (opaque origin case)", () => {
  assert.strictEqual(fenApiBase("k", "fb", { search: "", storage: null }), "fb");
  assert.strictEqual(fenApiBase("k", "fb/", { search: "", storage: null }), "fb");
});
