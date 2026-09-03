/**
 * fenTheme — ONE light-palette + status→color source for JS-rendered UI
 * (TECH-DEBT P2 consolidation). The portal CSS variables in
 * web/portal/index.html / triadic.html keep the same hex values — keep this
 * file in sync with them (single place for JS callers). The Flow-2 widget
 * has its own dark/light ramp inside its shadow DOM and mirrors semantics.
 */
(function (global) {
  "use strict";

  var FEN_LIGHT = {
    bl: "#2d5a8e", // accent / pending
    gr: "#2e7d5b", // validated
    rd: "#b23a3a", // rejected
    gd: "#8b6914", // disputed
    hs: "#5b4e8a",
    ink: "#1c1b1f",
    mu: "#6b6560",
  };

  var STATUS_COLOR = {
    validated: FEN_LIGHT.gr,
    disputed: FEN_LIGHT.gd,
    rejected: FEN_LIGHT.rd,
    pending: FEN_LIGHT.bl,
    deciding: FEN_LIGHT.mu,
    unknown: FEN_LIGHT.mu,
  };

  function fenStatusColor(status) {
    return STATUS_COLOR[status] || FEN_LIGHT.mu;
  }

  var api = { FEN_LIGHT: FEN_LIGHT, STATUS_COLOR: STATUS_COLOR, fenStatusColor: fenStatusColor };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.fenTheme = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
