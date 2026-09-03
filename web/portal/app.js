/**
 * FEN Community DAO portal (Flow 1) — zero-build demo UI against
 * mock_fen_api. Contract in web/api.md. The same contract is expected from
 * the real FEN backend in production (ADR-002: DAO lives outside this repo).
 */
"use strict";

// Escaping lives in web/shared/escape.js (TECH-DEBT P2 consolidation) —
// keep ONE implementation; local helpers are aliases only.
const escapeHtml = window.fenEscapeHtml;

const $ = (id) => document.getElementById(id);

// Live updates via the shared SSE helper (web/shared/live.js, TECH-DEBT
// P1): unified semantics — fallback ticker while the stream is down,
// catch-up reload on every (re)open. The "Live updates" toggle starts and
// stops it; manual Refresh always stays available.
let liveUpdates = null;

function stopLiveUpdates() {
  if (liveUpdates) { liveUpdates.stop(); liveUpdates = null; }
}

function startLiveUpdates() {
  stopLiveUpdates();  // idempotent (re)connect
  const base = $("mock_base").value.replace(/\/+$/, "");
  liveUpdates = fenLive({
    url: base + "/events",
    events: ["vote", "decision", "candidates"],
    onEvent: () => loadCandidates(),
    onOpen: () => loadCandidates(),   // catch-up after any gap
    fallback: () => loadCandidates(), // 15s ticker while the stream is down
  });
  liveUpdates.start();
}

let currentFilter = "all";
let cachedList = [];
let reputation = {};            // actor -> points (current totals)
let reputationHistory = [];      // newest first, last 50, validated only
let llmAccuracy = {};           // { agreements, total, accuracy }

const VALID_STATUSES = ["pending", "deciding", "validated", "disputed", "rejected", "unknown"];

function statusBadge(status) {
  // Enum-validate + escape (TECH-DEBT P1): status is server-controlled and
  // lands in the class attribute AND the text — never interpolate it raw.
  const safe = VALID_STATUSES.indexOf(status) !== -1 ? status : "unknown";
  return '<span class="badge b-' + escapeHtml(safe) + '">' + escapeHtml(safe) + "</span>";
}

function renderCandidates(data) {
  const rows = $("rows");
  cachedList = (data && data.candidates) || [];
  const counts = { all: cachedList.length };
  cachedList.forEach((c) => { counts[c.status] = (counts[c.status] || 0) + 1; });
  $("summary").textContent =
    "total " + counts.all +
    " · pending " + (counts.pending || 0) +
    " · deciding " + (counts.deciding || 0) +
    " · validated " + (counts.validated || 0) +
    " · disputed " + (counts.disputed || 0) +
    " · rejected " + (counts.rejected || 0);

  const list = currentFilter === "all" ? cachedList : cachedList.filter((c) => c.status === currentFilter);
  if (!list.length) {
    rows.innerHTML = '<tr><td colspan="8" class="note">no candidates' +
      (currentFilter !== "all" ? " with status " + escapeHtml(currentFilter) : "") +
      " — submit one above</td></tr>";
    return;
  }
  const expBase = $("status_base").value.replace(/\/+$/, "");
  rows.innerHTML = list.map((c) => {
    const q = c.quorum || { votes: 0, required: 0 };
    const pct = q.required ? Math.min(100, Math.round((q.votes / q.required) * 100)) : 0;
    // TECH-DEBT P1: c.votes is server-controlled and may be absent — guard
    // and coerce before interpolating into innerHTML.
    const votes = c.votes || {};
    const nv = Number(votes.validated) || 0, dv = Number(votes.disputed) || 0, rv = Number(votes.rejected) || 0;
    const rec = c.llm_recommendation
      ? '<span class="note" style="color:var(--amber)">' + escapeHtml(c.llm_recommendation) + " (support)</span>"
      : "—";
    const voteBtns =
      c.status === "pending"
        ? '<div class="vote">' +
          ["validated", "disputed", "rejected"].map(
            (o) => '<button data-vote="' + escapeHtml(c.annotation_id) + '" data-outcome="' + o + '">' + o + "</button>"
          ).join("") +
          "</div>"
        : '<span class="note">—</span>';
    const exportLinks = ["ttl", "jsonld", "nt", "crate"].map((f) =>
      '<a class="exp" href="' + expBase + "/api/v1/export/" + encodeURIComponent(c.annotation_id) + "?format=" + f +
      '" target="_blank" rel="noopener" title="export as ' + f + '">' + f + "</a>"
    ).join("");
    return (
      "<tr>" +
      "<td><code>" + escapeHtml(c.annotation_id) + "</code><br><span class='note'>" + escapeHtml(c.document_id || "") + "</span></td>" +
      "<td>" + escapeHtml(c.entity_label || "—") + "</td>" +
      "<td>" + statusBadge(c.status) + "</td>" +
      "<td>" + rec + "</td>" +
      "<td>v:" + nv + " d:" + dv + " r:" + rv + "</td>" +
      '<td><div class="bar"><div style="width:' + pct + '%"></div></div><span class="note">' + Number(q.votes) + "/" + Number(q.required) + "</span></td>" +
      "<td>" + voteBtns + "</td>" +
      '<td class="exports">' + exportLinks + "</td>" +
      "</tr>"
    );
  }).join("");
}

function renderReputation() {
  const acc = llmAccuracy || {};
  const accTxt = acc.total
    ? "LLM judge vs community decisions: " + acc.agreements + "/" + acc.total +
      " (" + Math.round((acc.accuracy || 0) * 100) + "%)"
    : "LLM judge vs community decisions: no decisions yet";
  $("llm_accuracy").textContent = accTxt;

  const top = Object.entries(reputation || {}).sort((a, b) => b[1] - a[1]).slice(0, 10);
  $("rep_leader").innerHTML = top.length
    ? top.map(([actor, pts]) =>
        '<div style="display:flex;gap:8px;justify-content:space-between">' +
          "<span>" + escapeHtml(actor) + ' <span class="note">· </span><b>' +
            escapeHtml(String(pts)) + '</b> <span class="note">points</span></span>' +
        "</div>"
      ).join("")
    : '<div class="note">no reputation yet</div>';

  const rows = (reputationHistory || []).slice(0, 20).map((h) => {
    const d = Number(h.delta) || 0;
    return '<div style="display:flex;gap:8px;justify-content:space-between">' +
      "<span>" + escapeHtml(h.actor) + ' <span class="note">· ' + escapeHtml(h.reason) +
        " · " + escapeHtml(String(h.annotation_id || "").slice(-6)) + "</span></span>" +
      '<b style="color:' + (d > 0 ? "var(--green)" : "var(--red)") + '">' +
        (d > 0 ? "+" : "") + d + "</b>" +
    "</div>";
  }).join("");
  $("rep_history").innerHTML = rows || '<div class="note">no reputation events yet</div>';
}

async function loadCandidates() {
  const base = $("mock_base").value.replace(/\/+$/, "");
  try {
    const resp = await fetch(base + "/candidates");
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const data = await resp.json();
    renderCandidates(data);
    reputation = data.reputation || {};
    reputationHistory = data.reputation_history || [];
    llmAccuracy = data.llm_accuracy || {};
    renderReputation();
    $("mode_note").textContent = "";
  } catch (err) {
    $("mode_note").textContent = "cannot reach " + base + " — start docker compose (mock-fen-api) first";
  }
}

async function submitCandidate() {
  const err = $("submit_err");
  err.textContent = "";
  const label = $("entity_label").value.trim();
  if (!label) { err.textContent = "entity_label is required"; return; }
  let annotationId = $("annotation_id").value.trim();
  if (!annotationId) annotationId = "annotation_" + Date.now();
  const candidate = {
    annotation_id: annotationId,
    document_id: $("document_id").value.trim() || null,
    entity_label: label,
    entity_type: $("entity_type").value.trim() || null,
  };
  const base = $("mock_base").value.replace(/\/+$/, "");
  try {
    const resp = await fetch(base + "/candidates", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidates: [candidate] }),
    });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const body = await resp.json();
    $("annotation_id").value = annotationId;
    err.textContent = "accepted: " + body.accepted + " candidate(s) — " + annotationId;
    loadCandidates();
  } catch (e) {
    err.textContent = "submit failed: " + e.message;
  }
}

async function castVote(annotationId, outcome) {
  const base = $("mock_base").value.replace(/\/+$/, "");
  try {
    const resp = await fetch(base + "/candidates/" + encodeURIComponent(annotationId) + "/vote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ outcome: outcome }),
    });
    if (resp.status === 409) {
      let detail = "vote rejected";
      try {
        const body = await resp.json();
        if (body && body.detail) detail = body.detail;
      } catch (e) { /* non-JSON error body */ }
      $("mode_note").textContent = detail;
    } else if (!resp.ok) {
      $("mode_note").textContent = "vote failed: HTTP " + resp.status;
    } else {
      const body = await resp.json();
      $("mode_note").textContent = body.outcome
        ? "quorum reached → outcome: " + body.outcome + " (decision being delivered)"
        : "vote recorded: " + body.quorum.votes + "/" + body.quorum.required;
    }
    loadCandidates();
  } catch (e) {
    $("mode_note").textContent = "vote failed: " + e.message;
  }
}

function bindEvents() {
  $("submit").onclick = submitCandidate;
  $("refresh").onclick = loadCandidates;
  $("auto_toggle").onclick = function () {
    if (liveUpdates) { stopLiveUpdates(); this.textContent = "Live updates: OFF"; }
    else { startLiveUpdates(); this.textContent = "Live updates: ON"; }
  };
  document.addEventListener("click", (e) => {
    const vote = e.target.closest("[data-vote]");
    if (vote) castVote(vote.dataset.vote, vote.dataset.outcome);
    const filter = e.target.closest("[data-filter]");
    if (filter) {
      currentFilter = filter.dataset.filter;
      document.querySelectorAll("#filters button").forEach((b) => {
        b.classList.toggle("primary", b === filter);
      });
      renderCandidates({ candidates: cachedList });
    }
  });
}

// Vercel/remote deployments: allow overriding the API bases from the URL
// (?fen_mock_base=...&fen_status_base=...), persisted to localStorage — the
// shared fenApiBase convention (web/shared/api-base.js, TECH-DEBT P2). The
// inputs stay editable; the fields just get sensible defaults.
(function applyApiBases() {
  [["fen_mock_base", "mock_base"], ["fen_status_base", "status_base"]].forEach(([key, id]) => {
    $(id).value = window.fenApiBase(key, $(id).value);
  });
})();

bindEvents();
loadCandidates();
startLiveUpdates();
