/**
 * Validation Commons — Triadic view (zero-build).
 * Talks to the mock FEN API only (web/api.md): /scaffold, /candidates,
 * /candidates/{id}/vote. Generic framework framing — any dataset type.
 */
"use strict";

const $ = (id) => document.getElementById(id);
const MOCK = (localStorage.getItem("fen_mock_base") || "http://localhost:8100").replace(/\/+$/, "");

const THRESHOLD_DEFAULT = 10;
const EXAMPLES = [
  { label: "Place · tradition", text: "In the local oral tradition, the hill Koshary marks the old trade route" },
  { label: "Artefact · culture", text: "The bronze buckle with the spiral motif is attributed to the Vistula culture" },
  { label: "Fact · community", text: "The biennial fair of St. Michael's was held on the first Sunday after Michaelmas" },
];

const C = { bl: "#2d5a8e", gr: "#2e7d5b", rd: "#b23a3a", gd: "#8b6914", hs: "#5b4e8a", ink: "#1c1b1f", mu: "#6b6560" };
const OUTCOME_STYLE = { validated: C.gr, disputed: C.gd, rejected: C.rd };
const OUTCOME_BG = { validated: "#e6f4ee", disputed: "#faf3e0", rejected: "#fae8e8" };

let state = { candidates: [], reputation: {}, mode: "auto", qv_threshold: THRESHOLD_DEFAULT };
let intensities = {};
let comments = {};

async function api(path, opts) {
  const resp = await fetch(MOCK + path, opts);
  if (!resp.ok) {
    let detail = "HTTP " + resp.status;
    try {
      const body = await resp.json();
      if (body && body.detail) detail = body.detail;
    } catch (e) { /* non-JSON error body */ }
    throw new Error(detail);
  }
  return resp.json();
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Escaping for values embedded in INLINE JS handlers inside double-quoted
// attributes: JS-string escaping first (backslash, single quote), then HTML
// entity escaping for the attribute. (HTML entity decoding happens before JS
// parsing, so esc() alone would NOT stop quote breakout in that context.)
function jsAttr(s) {
  return esc(String(s == null ? "" : s).replace(/\\/g, "\\\\").replace(/'/g, "\\'"));
}

// ---------------------------------------------------------------- scaffold
let stepsEl = null;
async function runScaffold() {
  const text = $("text").value.trim();
  if (!text) return;
  $("run").disabled = true;
  $("scaffoldErr").textContent = "";
  $("steps").innerHTML = "";
  try {
    const res = await api("/scaffold", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    renderSteps(res);
  } catch (e) {
    $("scaffoldErr").textContent = "scaffold failed: " + e.message + " (is mock-fen-api up?)";
  }
  $("run").disabled = false;
}

function renderSteps(res) {
  const s = [];
  if ((res.schema_hints || []).length) s.push({ c: C.bl, bg: "#e8eff7", icon: "▦", t: "Schema guidance", items: res.schema_hints });
  if ((res.relationships || []).length) s.push({ c: C.gr, bg: "#e6f4ee", icon: "⊸", t: "Semantic relationships", items: res.relationships });
  const amb = (res.ambiguities || []).filter((a) => a && a.trim());
  if (amb.length) s.push({ c: C.gd, bg: "#faf3e0", icon: "!", t: "Ambiguities flagged", items: amb });

  stepsEl = { steps: s, triple: res.triple, vis: 0 };
  const paint = () => {
    let html = "";
    s.forEach((st, i) => {
      if (stepsEl.vis <= i) return;
      html += '<div class="step" style="border:1px solid ' + st.c + "44;background:" + st.bg + '">' +
        '<div class="t" style="color:' + st.c + '">' + st.icon + " " + esc(st.t) + "</div>" +
        st.items.map((it) => '<div class="i" style="border-color:' + st.c + "55;color:" + C.ink + '">' + esc(it) + "</div>").join("") +
        "</div>";
    });
    if (stepsEl.triple && stepsEl.vis > s.length) {
      html += '<div style="animation:fadeSlide .3s ease">' + tripleBox(stepsEl.triple) +
        '<button class="btn green" onclick="submitTriple()">Submit for DAO Vote →</button></div>';
    }
    $("steps").innerHTML = html;
  };
  paint();
  for (let i = 1; i <= s.length + 1; i++) {
    setTimeout(() => { stepsEl.vis = i; paint(); }, 380 * i);
  }
}

function tripleBox(t) {
  const rows = [["Subject", t.subject], ["Predicate", t.predicate], ["Object", t.object], ["Context", t.context], ["Domain", t.language_or_domain]];
  return '<div class="triple"><div class="grid">' +
    rows.map(([k, v]) => '<span class="k">' + esc(k) + "</span><span>" + esc(v) + "</span>").join("") +
    '<span class="k">Evidence</span><span class="badge b-gd">' + esc(t.evidence_type || "") + "</span>" +
    "</div></div>";
}

async function submitTriple() {
  const t = stepsEl.triple;
  const annotationId = "annotation_" + Date.now();
  await api("/candidates", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidates: [{
      annotation_id: annotationId,
      document_id: "doc_" + Date.now(),
      entity_label: t.subject,
      entity_type: t.predicate,
      submitter: $("name").value.trim() || "contributor_1",
      triple: t,
    }] }),
  });
  $("text").value = ""; $("steps").innerHTML = "";
  stepsEl = null;
  load();
}

// --------------------------------------------------------------- consensus
function scoreOf(c) {
  const qv = c.qv || {};
  return qv.scores || { validated: 0, disputed: 0, rejected: 0 };
}

function renderConsensus() {
  const pending = state.candidates.filter((c) => c.status === "pending");
  const el = $("consensus");
  if (!pending.length) {
    el.innerHTML = '<div class="note">No proposals yet.<br>Submit one from Scaffold →</div>';
    return;
  }
  el.innerHTML = pending.map((c) => {
    const scores = scoreOf(c);
    const qv = c.qv || {};
    const threshold = qv.threshold || state.qv_threshold || THRESHOLD_DEFAULT;
    const maxScore = Math.max(0, ...Object.values(scores));
    const pct = Math.min(100, (maxScore / threshold) * 100);
    const intens = intensities[c.annotation_id] || 3;
    const votes = qv.votes || [];
    const reviews = votes.filter((v) => v.comment);
    const voted = votes.some((v) => v.voter === $("voter").value.trim());

    const scoreRow = Object.keys(OUTCOME_STYLE).map((o) =>
      '<span style="color:' + OUTCOME_STYLE[o] + ';font-weight:700">' + o + " " + (scores[o] || 0) + "</span>").join(" · ");

    return '<div class="item">' +
      '<div style="font-size:12px;margin-bottom:3px"><b>' + esc((c.triple || {}).subject || c.entity_label) + "</b> — " +
      esc((c.triple || {}).predicate || "") + " — <b>" + esc((c.triple || {}).object || "") + "</b></div>" +
      '<div class="meta">#' + esc(c.annotation_id).slice(-5) + " · by " + esc(c.submitter || "?") + " · " + esc((c.triple || {}).language_or_domain || "") + "</div>" +
      '<div class="bar"><div style="width:' + pct + '%"></div></div>' +
      '<div class="prow"><span style="color:' + C.mu + '">' + scoreRow + '</span><span style="color:' + C.mu + '">threshold ' + threshold + "</span></div>" +
      (reviews.length ? '<div style="border-top:1px solid #e3ded2;padding-top:7px;margin-bottom:8px"><div class="lbl">① Peer reviews</div>' +
        reviews.map((v) => '<div style="font-size:11px;margin-bottom:5px;background:#f7f5f0;border-radius:6px;padding:5px 8px">' +
          '<b style="color:' + (v.dir === "for" ? C.gr : C.rd) + '">' + esc(v.voter) + "</b> <span class='badge b-gr'>Rep " + (state.reputation[v.voter] || 0) + "</span>" +
          "<div style='line-height:1.35'>" + esc(v.comment) + "</div></div>").join("") + "</div>" : "") +
      (voted
        ? '<div style="font-size:10.5px;color:' + C.mu + '">✓ Voted as ' + esc($("voter").value.trim()) + "</div>"
        : '<div class="lbl" style="margin-bottom:3px">① Peer review (optional)</div>' +
          '<textarea style="width:100%;border:1px solid #e3ded2;border-radius:6px;padding:6px 8px;font-size:12px;resize:none;min-height:44px;box-sizing:border-box" placeholder="Share your assessment…" onchange="comments[\'' + jsAttr(c.annotation_id) + '\']=this.value"></textarea>' +
          '<div class="lbl" style="margin-bottom:4px;margin-top:6px">② Cast QV vote</div>' +
          '<div class="vote-row">' +
          '<button class="step-btn" onclick="adjIntensity(\'' + jsAttr(c.annotation_id) + '\',-1)">−</button>' +
          '<span style="font-size:10px;color:' + C.mu + ';min-width:22px;text-align:center">×' + intens + "</span>" +
          '<button class="step-btn" onclick="adjIntensity(\'' + jsAttr(c.annotation_id) + '\',1)">+</button>' +
          Object.keys(OUTCOME_STYLE).map((o) =>
            '<button class="vote-btn" style="background:' + OUTCOME_STYLE[o] + '" onclick="vote(\'' + jsAttr(c.annotation_id) + '\',\'' + jsAttr(o) + '\')">' + o + "</button>").join("") +
          "</div>" +
          '<div class="cost">Cost: ' + intens + "² = <b>" + (intens * intens) + "</b> credits · Your Rep: " + (state.reputation[$("voter").value.trim()] || 0) + "</div>") +
      "</div>";
  }).join("");
}

function adjIntensity(id, d) {
  intensities[id] = Math.min(5, Math.max(1, (intensities[id] || 3) + d));
  renderConsensus();
}

async function vote(annotationId, outcome) {
  const voter = $("voter").value.trim() || "validator_1";
  try {
    const res = await api("/candidates/" + encodeURIComponent(annotationId) + "/vote", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ outcome, intensity: intensities[annotationId] || 3, voter, comment: comments[annotationId] || "" }),
    });
    $("modeBanner").textContent = res.outcome
      ? "Threshold reached → outcome: " + res.outcome + " (decision being delivered)"
      : "Vote recorded · " + (res.qv ? "scores: " + JSON.stringify(res.qv.scores) : "count " + res.quorum.votes + "/" + res.quorum.required);
    $("modeBanner").style.display = "block";
  } catch (e) {
    $("modeBanner").textContent = "vote failed: " + e.message;
    $("modeBanner").style.display = "block";
  }
  load();
}

// ---------------------------------------------------------------- registry
function renderRegistry() {
  const decided = state.candidates.filter((c) => c.decision);
  $("regCount").textContent = decided.length + " record" + (decided.length === 1 ? "" : "s");
  const el = $("registry");
  if (!decided.length) {
    el.innerHTML = '<div class="note">Registry is empty.<br>Approved entries appear automatically.</div>';
    return;
  }
  el.innerHTML = decided.map((c, idx) => {
    const d = c.decision;
    const pid = "https://w3id.org/fen/id/decision/" + d.decision_id;
    const scores = scoreOf(c);
    const qvVotes = (c.qv || {}).votes || [];
    const validators = [...new Set(qvVotes.map((v) => v.voter))];
    return '<div class="item reg">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">' +
      '<span style="font-weight:700;font-size:12px">Decision #' + (idx + 1) + "</span>" +
      '<span class="badge b-gr">' + esc(d.outcome) + "</span></div>" +
      '<div style="font-size:12px;margin-bottom:3px"><b>' + esc((c.triple || {}).subject || c.entity_label) + "</b> — " + esc((c.triple || {}).predicate || "") + " — <b>" + esc((c.triple || {}).object || "") + "</b></div>" +
      '<div class="meta">' + esc((c.triple || {}).language_or_domain || "") + " · " + esc((c.triple || {}).evidence_type || "") + "</div>" +
      '<div style="background:#f4f2ed;border-radius:6px;padding:8px 10px;font-size:11px">' +
      '<div style="display:grid;grid-template-columns:auto 1fr;gap:4px 10px">' +
      '<span style="color:' + C.mu + ';font-weight:600">Contributor</span><span>' + esc(c.submitter || "?") + "</span>" +
      '<span style="color:' + C.mu + ';font-weight:600">Decision ID</span><span><a href="' + esc(pid) + '" target="_blank" rel="noopener" style="color:' + C.hs + ';font-weight:700;font-family:monospace">' + esc(d.decision_id) + "</a></span>" +
      '<span style="color:' + C.mu + ';font-weight:600">Scores</span><span>' + Object.keys(OUTCOME_STYLE).map((o) => '<span style="color:' + OUTCOME_STYLE[o] + ';font-weight:700">' + o + " " + (scores[o] || 0) + "</span>").join(" · ") + "</span>" +
      '<span style="color:' + C.mu + ';font-weight:600">Validators</span><span>' + esc(validators.join(", ") || "—") + "</span>" +
      '<span style="color:' + C.mu + ';font-weight:600">Anchor</span><span class="mono">' + esc(d.ledger_anchor) + "</span>" +
      "</div></div></div>";
  }).join("");
}

// ------------------------------------------------------------------- load
async function load() {
  try {
    const data = await api("/candidates");
    state = { candidates: data.candidates || [], reputation: data.reputation || {}, mode: data.mode, qv_threshold: data.qv_threshold };
    const banner = $("modeBanner");
    if (state.mode !== "qv") {
      banner.textContent = "Mock is in '" + state.mode + "' mode — intensity/QV works with FEN_MOCK_VOTING=qv (threshold " + (state.qv_threshold || THRESHOLD_DEFAULT) + ")";
      banner.style.display = "block";
    } else {
      banner.style.display = "none";
    }
    $("repBadge").textContent = "Rep " + (state.reputation[$("voter").value.trim()] || 0);
  } catch (e) {
    $("modeBanner").textContent = "cannot reach " + MOCK + " — start the stack first";
    $("modeBanner").style.display = "block";
  }
  renderConsensus();
  renderRegistry();
}

function init() {
  $("run").onclick = runScaffold;
  const ex = $("examples");
  EXAMPLES.forEach((e) => {
    const b = document.createElement("button");
    b.className = "chip";
    b.textContent = e.label;
    b.title = e.text;
    b.onclick = () => { $("text").value = e.text; };
    ex.appendChild(b);
  });
  $("voter").addEventListener("input", () => {
    $("repBadge").textContent = "Rep " + (state.reputation[$("voter").value.trim()] || 0);
    renderConsensus();
  });
  setInterval(load, 3000);
  load();
}

init();
