/**
 * fenApiBase — ONE API-base override convention for the zero-build web
 * layer (TECH-DEBT P2 consolidation): query param (?key=...) wins and is
 * persisted, then localStorage, then the page default. Trailing slashes are
 * stripped. Portal views use this for fen_mock_base / fen_status_base.
 *
 * Options are injectable so Node tests can fake the browser bits:
 *   fenApiBase("fen_mock_base", "http://localhost:8100")            // browser
 *   fenApiBase("k", "fb", { search: "?k=QV", storage: fakeStorage }) // test
 */
(function (global) {
  "use strict";

  function defaults() {
    var search = "";
    var storage = null;
    try {
      if (global.location && global.location.search) search = global.location.search;
      storage = global.localStorage || null;
    } catch (e) { /* opaque origins throw on localStorage access */ }
    return { search: search, storage: storage };
  }

  function fenApiBase(key, fallback, opts) {
    var o = opts || defaults();
    var search = o.search || "";
    var storage = o.storage || null;
    var value = null;
    try {
      value = new URLSearchParams(search).get(key);
    } catch (e) { /* malformed search */ }
    if (value) {
      if (storage) { try { storage.setItem(key, value); } catch (e) { /* ignore */ } }
      return value.replace(/\/+$/, "");
    }
    if (storage) {
      try { value = storage.getItem(key); } catch (e) { /* ignore */ }
      if (value) return value.replace(/\/+$/, "");
    }
    return String(fallback == null ? "" : fallback).replace(/\/+$/, "");
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = fenApiBase;
  } else {
    global.fenApiBase = fenApiBase;
  }
})(typeof window !== "undefined" ? window : globalThis);
