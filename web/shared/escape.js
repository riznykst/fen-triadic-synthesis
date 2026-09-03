/**
 * fenEscapeHtml / fenJsAttr / fenSafeHref — ONE escaping implementation for
 * the zero-build web layer (TECH-DEBT P2 consolidation). Portal views load
 * this file and alias their local helpers to it; the Flow-2 widget keeps a
 * self-contained copy for third-party embedding but must mirror these
 * semantics.
 *
 * UMD-ish: attaches to `window` in the browser, `module.exports` under Node
 * (web/tests/*.test.js run with `node --test`).
 */
(function (global) {
  "use strict";

  var HTML_MAP = {
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  };

  function fenEscapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return HTML_MAP[c];
    });
  }

  // Escaping for values embedded in INLINE JS handlers inside double-quoted
  // attributes: JS-string escaping first (backslash, single quote), then HTML
  // entity escaping for the attribute. (HTML entity decoding happens before
  // JS parsing, so plain HTML escaping alone would NOT stop quote breakout
  // in that context.)
  function fenJsAttr(s) {
    return fenEscapeHtml(String(s == null ? "" : s).replace(/\\/g, "\\\\").replace(/'/g, "\\'"));
  }

  // Only http(s) URLs are allowed in hrefs; anything else renders as text.
  function fenSafeHref(u) {
    try {
      var parsed = new URL(String(u), global.location ? global.location.href : undefined);
      return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : null;
    } catch (e) {
      return null;
    }
  }

  var api = { fenEscapeHtml: fenEscapeHtml, fenJsAttr: fenJsAttr, fenSafeHref: fenSafeHref };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.fenEscapeHtml = fenEscapeHtml;
    global.fenJsAttr = fenJsAttr;
    global.fenSafeHref = fenSafeHref;
  }
})(typeof window !== "undefined" ? window : globalThis);
