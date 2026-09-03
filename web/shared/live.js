/**
 * fenLive — shared SSE live-updates helper (TECH-DEBT P1).
 *
 * One implementation of the EventSource + polling-fallback pattern used by
 * the classic portal (app.js), the triadic view (triadic.js) and mirrored by
 * the Flow-2 widget (fen-status-widget.js, which stays self-contained for
 * third-party embedding but follows the same semantics).
 *
 * Unified semantics:
 *   - named event frames (e.g. vote/decision/candidates/status) stop the
 *     fallback ticker and are dispatched to onEvent(name, payload);
 *   - server-sent `event: error` frames (RDF store unreachable) surface via
 *     onServerError(msg) — the stream itself stays open, the server retries
 *     on its next poll tick;
 *   - TRANSPORT failures fire a 15s fallback ticker (opts.fallback) while
 *     EventSource auto-reconnects — no update is lost during the gap;
 *   - every (re)open stops the ticker and calls opts.onOpen() so the caller
 *     catches up on anything missed while disconnected.
 *
 * Usage:
 *   var live = fenLive({
 *     url: base + "/events",
 *     events: ["vote", "decision", "candidates"],   // named frames to hear
 *     onEvent: function (name, payload) { /* render *\/ },
 *     onServerError: function (msg) { /* show *\/ },
 *     onOpen: function () { reload(); },            // every (re)open
 *     fallback: function () { reload(); }           // 15s ticker while down
 *   });
 *   live.start();   // idempotent (re)connect
 *   live.stop();    // close stream + clear ticker
 */
(function (global) {
  "use strict";

  var FALLBACK_MS = 15000;

  function fenLive(opts) {
    var es = null;
    var fallbackTimer = null;

    function stopFallback() {
      if (fallbackTimer) { clearInterval(fallbackTimer); fallbackTimer = null; }
    }
    function startFallback() {
      if (!fallbackTimer) fallbackTimer = setInterval(opts.fallback, FALLBACK_MS);
    }
    function stop() {
      stopFallback();
      if (es) { es.close(); es = null; }
    }
    function start() {
      stop(); // idempotent (re)connect
      try {
        es = new EventSource(opts.url);
      } catch (e) {
        startFallback(); // EventSource unavailable -> poll instead
        return null;
      }
      (opts.events || []).forEach(function (name) {
        es.addEventListener(name, function (ev) {
          stopFallback();
          var payload = null;
          try { payload = JSON.parse(ev.data); } catch (e) { /* keep null */ }
          if (opts.onEvent) opts.onEvent(name, payload);
        });
      });
      // Server-sent `event: error` frame — NOT a transport error.
      es.addEventListener("error", function (ev) {
        var msg = "Status API unavailable";
        try {
          var d = JSON.parse(ev.data);
          if (d && d.error) msg = d.error;
        } catch (e) { /* non-JSON frame */ }
        if (opts.onServerError) opts.onServerError(msg);
      });
      es.onopen = function () {
        stopFallback();
        if (opts.onOpen) opts.onOpen(); // catch-up after any gap
      };
      es.onerror = function () { startFallback(); };
      return es;
    }
    return { start: start, stop: stop };
  }

  global.fenLive = fenLive;
})(window);
