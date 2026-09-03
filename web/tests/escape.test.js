// Node tests for web/shared/escape.js (TECH-DEBT P3: JS-level tests).
// Run: node --test web/tests/  (Node >= 18 with node:test).
"use strict";
const { test } = require("node:test");
const assert = require("node:assert");
const { fenEscapeHtml, fenJsAttr, fenSafeHref } = require("../shared/escape.js");

test("fenEscapeHtml escapes the five HTML metacharacters", () => {
  assert.strictEqual(fenEscapeHtml(`<a href="x" title='y'>&`), "&lt;a href=&quot;x&quot; title=&#39;y&#39;&gt;&amp;");
});

test("fenEscapeHtml handles null/undefined/numbers", () => {
  assert.strictEqual(fenEscapeHtml(null), "");
  assert.strictEqual(fenEscapeHtml(undefined), "");
  assert.strictEqual(fenEscapeHtml(0), "0");
  assert.strictEqual(fenEscapeHtml("plain"), "plain");
});

test("fenJsAttr escapes backslashes and quotes for inline handlers", () => {
  // Input: a ' b \ c. Backslash is doubled first, then the quote becomes
  // \' whose backslash survives HTML escaping (only &<>"' are entities),
  // then the quote itself is HTML-escaped: a \ &#39; b \ \ c
  assert.strictEqual(fenJsAttr("a'b\\c"), "a\\&#39;b\\\\c");
  assert.strictEqual(fenJsAttr('say "hi"'), "say &quot;hi&quot;");
});

test("fenSafeHref allows http(s) and rejects everything else", () => {
  assert.ok(fenSafeHref("https://example.org/x").startsWith("https://example.org/x"));
  assert.ok(fenSafeHref("http://example.org/x").startsWith("http://example.org/x"));
  assert.strictEqual(fenSafeHref("javascript:alert(1)"), null);
  assert.strictEqual(fenSafeHref("data:text/html,<b>"), null);
  assert.strictEqual(fenSafeHref(""), null);
});
