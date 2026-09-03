/**
 * <fen-status> — embeddable validation-status widget (Flow 2, zero-build).
 *
 * Usage:
 *   <script src="fen-status-widget.js"></script>
 *   <fen-status annotation-id="annotation_a1" api-base="http://localhost:8082"></fen-status>
 *
 * Attributes:
 *   annotation-id  (required) — oa:Annotation id, e.g. annotation_a1
 *   api-base       (optional) — Status API origin, default http://localhost:8082
 *   theme          (optional) — "dark" (default) | "light"
 *   live           (optional) — "off" disables the SSE live stream (some
 *                                third-party pages disallow EventSource/CSP);
 *                                default is on. Fallback polling still works.
 *
 * Live updates: subscribes to GET {api-base}/api/v1/events/{annotation-id}
 * (SSE, see web/api.md §4b). `event: status` carries the same payload as
 * GET /api/v1/status/{annotation-id} and reuses the exact same render path.
 * While the stream is down (EventSource auto-reconnects) a 15s polling
 * fallback keeps the badge fresh; the next `onopen` stops the ticker and
 * catches up. Reads GET {api-base}/api/v1/status/{annotation-id} (see
 * web/api.md) and renders the gfen:validationStatus badge; clicking expands
 * decision details (method, dereferenceable PID, reputation snapshot, ledger
 * anchor). Never writes anything — read-only by design (ADR-001).
 */
(function () {
  "use strict";

  // Escape server-provided values before any innerHTML interpolation (the
  // widget is meant to be embedded on third-party pages; the data source is
  // the SPARQL-backed Status API, so values must never become markup).
  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }
  // Only http(s) URLs are allowed in hrefs; anything else renders as text.
  function safeHref(u) {
    try {
      const parsed = new URL(String(u), window.location.href);
      return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : null;
    } catch (e) {
      return null;
    }
  }

  const COLORS = {
    validated: "#3fce7c",
    disputed: "#ffb020",
    rejected: "#ff5c5c",
    pending: "#4da3ff",
    unknown: "#8fa0bf",
  };

  class FenStatusWidget extends HTMLElement {
    static get observedAttributes() {
      return ["annotation-id", "api-base", "theme", "live"];
    }

    constructor() {
      super();
      this._data = null;
      this._error = null;
      this._loading = false;
      this._expanded = false;
      this._sse = null;            // EventSource for live status
      this._sseOk = false;         // has the stream ever opened
      this._fallbackTimer = null;  // 15s polling while the stream is down
      this.attachShadow({ mode: "open" });
    }

    get annotationId() {
      return this.getAttribute("annotation-id") || "";
    }
    get apiBase() {
      return (this.getAttribute("api-base") || "http://localhost:8082").replace(/\/+$/, "");
    }
    get theme() {
      return this.getAttribute("theme") || "dark";
    }
    get live() {
      return this.getAttribute("live") !== "off";
    }

    connectedCallback() {
      this._load();
      this._startLive();
    }

    disconnectedCallback() {
      this._stopLive();
    }

    attributeChangedCallback(name) {
      if (name === "live") {
        // Toggle streaming without reloading the current record.
        if (this.live) this._startLive(); else this._stopLive();
        return;
      }
      // annotation-id / api-base / theme changed: re-fetch and reconnect.
      this._load();
      this._startLive();
    }

    // ------------------------------------------------------------- live (SSE)
    // Self-contained on purpose (third-party embedding loads only this file),
    // but mirrors the canonical shared helper web/shared/live.js semantics
    // (TECH-DEBT P1): fallback ticker while the stream is down, catch-up
    // reload on every (re)open.
    _startLive() {
      if (!this.live) return;
      this._stopLive();  // idempotent (re)connect
      if (!this.annotationId) return;
      const url = this.apiBase + "/api/v1/events/" + encodeURIComponent(this.annotationId);
      try {
        this._sse = new EventSource(url);
      } catch (e) {
        this._startFallback();  // EventSource unavailable -> poll instead
        return;
      }
      this._sseOk = false;
      this._sse.addEventListener("status", (ev) => this._onSseStatus(ev));
      this._sse.addEventListener("error", (ev) => this._onSseError(ev));
      this._sse.onopen = () => {
        // Stream (re)opened: stop the fallback ticker and catch up — the
        // gap while disconnected must not lose a status flip.
        this._sseOk = true;
        this._stopFallback();
        this._load();
      };
      // Transport-level failure: EventSource auto-reconnects; while it is
      // down the fallback ticker keeps the badge fresh (no lost updates).
      this._sse.onerror = () => this._startFallback();
    }

    _stopLive() {
      this._stopFallback();
      if (this._sse) { this._sse.close(); this._sse = null; }
      this._sseOk = false;
    }

    _onSseStatus(ev) {
      // Server pushed a CHANGED record — same payload shape as the REST
      // endpoint, so it renders through the exact same path (no flicker).
      this._sseOk = true;
      this._stopFallback();
      try {
        this._data = JSON.parse(ev.data);
        this._error = null;
      } catch (e) {
        this._error = "bad live payload";
      }
      this._loading = false;
      this._render();
    }

    _onSseError(ev) {
      // Server-side error frame (RDF store unreachable): show it, keep the
      // stream — status-api retries on its next poll tick.
      let msg = "Status API unavailable";
      try {
        const d = JSON.parse(ev.data);
        if (d && d.error) msg = d.error;
      } catch (e) { /* non-JSON error frame */ }
      this._error = msg + " (live)";
      this._render();
    }

    _startFallback() {
      if (!this._fallbackTimer) this._fallbackTimer = setInterval(() => this._load(), 15000);
    }

    _stopFallback() {
      if (this._fallbackTimer) { clearInterval(this._fallbackTimer); this._fallbackTimer = null; }
    }

    async _load() {
      if (!this.annotationId) {
        this._error = "missing annotation-id attribute";
        this._render();
        return;
      }
      this._loading = true;
      this._render();
      try {
        const resp = await fetch(this.apiBase + "/api/v1/status/" + encodeURIComponent(this.annotationId));
        if (resp.status === 404) {
          this._data = { found: false, validation_status: "unknown" };
        } else if (!resp.ok) {
          throw new Error("HTTP " + resp.status);
        } else {
          this._data = await resp.json();
        }
        this._error = null;
      } catch (err) {
        this._data = null;
        this._error = "Status API unavailable (" + err.message + ")";
      }
      this._loading = false;
      this._render();
    }

    _style() {
      const dark = this.theme === "dark";
      const bg = dark ? "#171e2e" : "#f5f7fb";
      const fg = dark ? "#dde3f0" : "#1a2332";
      const muted = dark ? "#8fa0bf" : "#5a6b85";
      const border = dark ? "#26314d" : "#d5deec";
      return `
        :host { display: inline-block; font: 13px/1.5 "Segoe UI", system-ui, sans-serif; }
        .card { background: ${bg}; color: ${fg}; border: 1px solid ${border}; border-radius: 10px; padding: 8px 12px; min-width: 200px; }
        .badge { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; user-select: none; }
        .dot { width: 9px; height: 9px; border-radius: 50%; }
        .label { font-weight: 600; }
        .hint { color: ${muted}; font-size: 11px; margin-top: 4px; }
        .details { margin-top: 8px; border-top: 1px solid ${border}; padding-top: 6px; font-size: 12px; }
        .details div { margin: 2px 0; word-break: break-all; }
        .details .k { color: ${muted}; }
        a { color: #4da3ff; }
        .err { color: #ff5c5c; }
      `;
    }

    _render() {
      const status = this._data ? this._data.validation_status : (this._loading ? "loading" : "unknown");
      const color = COLORS[status] || COLORS.unknown;
      let body;
      if (this._error) {
        body = `<div class="hint err">${escapeHtml(this._error)} <a href="#" id="retry">retry</a></div>`;
      } else if (this._loading) {
        body = `<div class="hint">checking validation status…</div>`;
      } else if (!this._data || !this._data.found) {
        body = `<div class="hint">no governance record found — entity is not (yet) community-validated</div>`;
      } else {
        const d = this._data;
        const pidHref = safeHref(d.governance_decision_id);
        const pidCell = pidHref
          ? `<a href="${pidHref}" target="_blank" rel="noopener">${escapeHtml(d.governance_decision_id)}</a>`
          : escapeHtml(d.governance_decision_id || "");
        const details = this._expanded ? `
          <div class="details">
            ${d.validation_method ? `<div><span class="k">method</span> ${escapeHtml(d.validation_method)}</div>` : ""}
            ${d.governance_decision_id ? `<div><span class="k">decision PID</span> ${pidCell}</div>` : ""}
            ${d.reputation_snapshot ? `<div><span class="k">reputation snapshot</span> ${escapeHtml(d.reputation_snapshot)}</div>` : ""}
            ${d.ledger_anchor ? `<div><span class="k">ledger anchor</span> ${escapeHtml(d.ledger_anchor)}</div>` : ""}
            ${/* TODO(ADR-006): render the gfen:challengeWindowEnd countdown
                once the ADR lands (BACKLOG: "Flow 2 widget: SSE real-time
                status + gfen:challengeWindowEnd"). The predicate is
                "proposed, not yet applied" in the ontology and the
                status-api must expose it first (_PREDICATE_KEYS) — gated,
                never faked. */ ""}
          </div>` : "";
        body = `
          <div class="badge" id="toggle" title="click for decision details">
            <span class="dot" style="background:${color}"></span>
            <span class="label">${escapeHtml(status)}</span>
            <span class="hint">${this._expanded ? "▲" : "▼"}</span>
          </div>
          ${details}`;
      }
      this.shadowRoot.innerHTML = `
        <style>${this._style()}</style>
        <div class="card">${body}</div>`;
      const toggle = this.shadowRoot.getElementById("toggle");
      if (toggle) toggle.onclick = () => { this._expanded = !this._expanded; this._render(); };
      const retry = this.shadowRoot.getElementById("retry");
      if (retry) retry.onclick = (e) => { e.preventDefault(); this._load(); };
    }
  }

  customElements.define("fen-status", FenStatusWidget);
})();
