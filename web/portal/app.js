/**
 * FEN Community DAO portal (Flow 1) — zero-build demo UI against
 * mock_fen_api. Contract in web/api.md. The same contract is expected from
 * the real FEN backend in production (ADR-002: DAO lives outside this repo).
 */
"use strict";

const $ = (id) => document.getElementById(id);

let autoTimer = null;

function statusBadge(status) {
  return '<span class="badge b-' + (status || "unknown") + '">' + (status || "unknown") + "</span>";
}

function renderCandidates(data) {
  const rows = $("rows");
  const list = (data && data.candidates) || [];
  if (!list.length) {
    rows.innerHTML = '<tr><td colspan="6" class="note">no candidates yet — submit one above</td></tr>';
    return;
  }
  rows.innerHTML = list.map((c) => {
    const q = c.quorum || { votes: 0, required: 0 };
    const pct = q.required ? Math.min(100, Math.round((q.votes / q.required) * 100)) : 0;
    const voteBtns =
      c.status === "pending"
        ? '<div class="vote">' +
          ["validated", "disputed", "rejected"].map(
            (o) => '<button data-vote="' + c.annotation_id + '" data-outcome="' + o + '">' + o + "</button>"
          ).join("") +
          "</div>"
        : '<span class="note">—</span>';
    return (
      "<tr>" +
      "<td><code>" + c.annotation_id + "</code><br><span class='note'>" + (c.document_id || "") + "</span></td>" +
      "<td>" + (c.entity_label || "—") + "</td>" +
      "<td>" + statusBadge(c.status) + "</td>" +
      "<td>v:" + (c.votes.validated || 0) + " d:" + (c.votes.disputed || 0) + " r:" + (c.votes.rejected || 0) + "</td>" +
      '<td><div class="bar"><div style="width:' + pct + '%"></div></div><span class="note">' + q.votes + "/" + q.required + "</span></td>" +
      "<td>" + voteBtns + "</td>" +
      "</tr>"
    );
  }).join("");
}

async function loadCandidates() {
  const base = $("mock_base").value.replace(/\/+$/, "");
  try {
    const resp = await fetch(base + "/candidates");
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    renderCandidates(await resp.json());
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
      $("mode_note").textContent = "vote rejected: enable community mode (FEN_MOCK_VOTING=community) or the candidate is already decided";
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
    if (autoTimer) { clearInterval(autoTimer); autoTimer = null; this.textContent = "Auto-refresh: OFF"; }
    else { autoTimer = setInterval(loadCandidates, 3000); this.textContent = "Auto-refresh: ON"; }
  };
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-vote]");
    if (btn) castVote(btn.dataset.vote, btn.dataset.outcome);
  });
}

bindEvents();
loadCandidates();
