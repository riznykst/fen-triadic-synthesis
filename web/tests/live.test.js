// Node tests for web/shared/live.js fenLive semantics (TECH-DEBT P3).
// Run: node --test web/tests/
"use strict";
const { test } = require("node:test");
const assert = require("node:assert");
const fenLive = require("../shared/live.js");

// Minimal EventSource stand-in: records listeners, exposes onopen/onerror
// as plain properties the helper assigns, lets tests fire events.
class FakeEventSource {
  constructor(url) {
    this.url = url;
    this.listeners = {};
    this.onopen = null;
    this.onerror = null;
    this.closed = false;
  }
  addEventListener(name, fn) {
    (this.listeners[name] = this.listeners[name] || []).push(fn);
  }
  close() {
    this.closed = true;
  }
  fire(name, data) {
    for (const fn of this.listeners[name] || []) fn({ data: JSON.stringify(data) });
  }
}

const realEventSource = global.EventSource;
const realSetInterval = global.setInterval;
const realClearInterval = global.clearInterval;

function withFakes(run) {
  return () => {
    const created = [];
    global.EventSource = class extends FakeEventSource {
      constructor(url) {
        super(url);
        created.push(this);
      }
    };
    const intervals = new Set();
    global.setInterval = (fn, ms) => { const id = { fn, ms }; intervals.add(id); return id; };
    global.clearInterval = (id) => intervals.delete(id);
    try {
      return run({ created, intervals });
    } finally {
      global.EventSource = realEventSource;
      global.setInterval = realSetInterval;
      global.clearInterval = realClearInterval;
    }
  };
}

test("fenLive.start creates an EventSource with the given url", withFakes(({ created }) => {
  const live = fenLive({ url: "http://x/events", events: [], onOpen() {}, fallback() {} });
  live.start();
  assert.strictEqual(created.length, 1);
  assert.strictEqual(created[0].url, "http://x/events");
  live.stop();
  assert.strictEqual(created[0].closed, true);
}));

test("fenLive.start is idempotent (replaces the stream)", withFakes(({ created }) => {
  const live = fenLive({ url: "http://x/events", events: [], onOpen() {}, fallback() {} });
  live.start();
  live.start();
  assert.strictEqual(created.length, 2);
  assert.strictEqual(created[0].closed, true);
  assert.strictEqual(created[1].closed, false);
  live.stop();
}));

test("named event frames stop the fallback and dispatch onEvent", withFakes(({ created, intervals }) => {
  const events = [];
  const live = fenLive({
    url: "u", events: ["vote", "decision"],
    onEvent: (name, payload) => events.push([name, payload]),
    onOpen() {}, fallback() {},
  });
  live.start();
  const es = created[0];
  es.onerror(); // transport down -> fallback ticker registers
  assert.strictEqual(intervals.size, 1);
  es.fire("vote", { annotation_id: "a1" });
  assert.deepStrictEqual(events, [["vote", { annotation_id: "a1" }]]);
  assert.strictEqual(intervals.size, 0); // event frame stopped the ticker
  live.stop();
}));

test("onopen stops the fallback and calls onOpen (catch-up)", withFakes(({ created }) => {
  const opens = [];
  const live = fenLive({
    url: "u", events: [], onOpen: () => opens.push(1), fallback() {},
  });
  live.start();
  created[0].onerror();
  created[0].onopen();
  assert.strictEqual(opens.length, 1);
  live.stop();
}));

test("server-sent error frames surface via onServerError", withFakes(({ created }) => {
  const errs = [];
  const live = fenLive({ url: "u", events: [], onServerError: (m) => errs.push(m), onOpen() {}, fallback() {} });
  live.start();
  created[0].fire("error", { error: "RDF store unavailable" });
  assert.deepStrictEqual(errs, ["RDF store unavailable"]);
  live.stop();
}));

test("unavailable EventSource degrades to the fallback ticker", withFakes(({ created }) => {
  global.EventSource = class { constructor() { throw new Error("CSP blocked EventSource"); } };
  const fallbacks = [];
  const live = fenLive({ url: "u", events: [], onOpen() {}, fallback: () => fallbacks.push(1) });
  live.start();
  assert.strictEqual(created.length, 0);
  live.stop();
  assert.strictEqual(fallbacks.length, 0); // ticker started but not yet fired
}));
