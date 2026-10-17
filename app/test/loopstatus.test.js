'use strict';
// Plan 136: the loop status card's pure render helpers (app/dashboard/loopstatus.js)
// and their wiring into the System tab (Loop card) and Home (one quiet line).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const L = require('../dashboard/loopstatus.js');

const APP = path.join(__dirname, '..');
const read = (p) => fs.readFileSync(path.join(APP, p), 'utf8');

const BASE = { state: 'running', fire: 41, last_tick_utc: '2026-10-17T10:00:00+00:00',
  tick_age_s: 120, tick_s: 8.5, eta_s: 900, stale: false, halted: false, backoff_until: null,
  backoff_reason: null, in_flight: [], stuck: [], counts: {} };

test('pill: kit vocabulary word + pill class; anything else is unknown', () => {
  assert.deepStrictEqual(L.pill(BASE), { state: 'running', text: 'loop running', cls: 'ok' });
  assert.deepStrictEqual(L.pill({ state: 'halted' }), { state: 'halted', text: 'loop halted', cls: 'warn' });
  assert.deepStrictEqual(L.pill({ state: 'stale' }), { state: 'stale', text: 'loop STALE', cls: 'bad' });
  assert.strictEqual(L.pill({ state: 'idle' }).cls, 'off');
  assert.strictEqual(L.pill({ state: 'backoff' }).text, 'loop backoff');
  assert.strictEqual(L.pill(null).state, 'unknown');
  assert.strictEqual(L.pill({ state: 'weird' }).text, 'loop unknown');
  assert.strictEqual(L.pill({ state: 'toString' }).state, 'unknown');
});

test('age: s / m / h / d', () => {
  assert.strictEqual(L.age(5), '5s');
  assert.strictEqual(L.age(600), '10m');
  assert.strictEqual(L.age(7200), '2h');
  assert.strictEqual(L.age(259200), '3d');
  assert.strictEqual(L.age(null), '?');
  assert.strictEqual(L.age(-1), '?');
});

test('card: tick line, fresh', () => {
  const c = L.card(BASE);
  assert.strictEqual(c.tick, 'last tick 2m ago, fire 41, took 9s');
  assert.deepStrictEqual(c.halt, []);
  assert.deepStrictEqual(c.inflight, []);
  assert.deepStrictEqual(c.stuck, []);
  assert.strictEqual(c.more, '');
});

test('card: halted shows "halted" and the HALT line', () => {
  const c = L.card(Object.assign({}, BASE, { state: 'halted', halted: true }));
  assert.strictEqual(c.pill.text, 'loop halted');
  assert.ok(c.halt[0].indexOf('HALT') === 0);
});

test('card: loop.json older than 2x eta shows "stale"', () => {
  const c = L.card(Object.assign({}, BASE, { state: 'stale', stale: true, tick_age_s: 2400 }));
  assert.strictEqual(c.pill.text, 'loop STALE');
  assert.match(c.tick, /last tick 40m ago.*\(stale: over 30m\)/);
  assert.strictEqual(L.card({ state: 'stale', stale: true }).tick, 'last tick time unreadable (stale)');
});

test('card: backoff line carries the reason', () => {
  const c = L.card(Object.assign({}, BASE, { state: 'backoff', backoff_until: '2026-10-17T11:00:00+00:00',
    backoff_reason: 'usage limit' }));
  assert.match(c.halt[0], /^usage backoff until .+ \(usage limit\)$/);
});

test('card: in-flight lanes with their checklist line; stuck items listed by id', () => {
  const c = L.card(Object.assign({}, BASE, {
    in_flight: [{ id: 'P136', state: 'dispatched', lane: 1, title: 'Loop card', line: 'builder running, ~4m' },
      { id: 'P137', state: 'ran', lane: null, title: '', line: '' }],
    stuck: [{ id: 'P130', state: 'adjudicate', since: '2026-10-17T09:00:00+00:00', title: 'X' },
      { id: 'P133', state: 'blocked', needs: ['120', '121'], title: '' }]
  }));
  assert.deepStrictEqual(c.inflight, ['lane 1: P136 Loop card - builder running, ~4m', 'P137 - ran']);
  assert.strictEqual(c.stuck[0].id, 'P130');
  assert.strictEqual(c.stuck[0].text, 'P130 adjudicate - X');
  assert.match(c.stuck[0].title, /^since /);
  assert.strictEqual(c.stuck[1].text, 'P133 blocked on 120, 121');
});

test('card: stuck list capped with a "+N more" line', () => {
  const stuck = [];
  for (let i = 0; i < 11; i++) stuck.push({ id: 'P' + (200 + i), state: 'gave-up' });
  const c = L.card(Object.assign({}, BASE, { stuck: stuck }));
  assert.strictEqual(c.stuck.length, 8);
  assert.strictEqual(c.more, '+3 more');
});

test('card: missing / unknown body never throws', () => {
  [null, undefined, {}, { state: 'unknown' }, 'x'].forEach(function (d) {
    const c = L.card(d);
    assert.strictEqual(c.pill.state, 'unknown');
    assert.strictEqual(c.tick, 'no tick recorded');
  });
});

test('homeLine: quiet unless stale, halted or stuck', () => {
  assert.strictEqual(L.homeLine(BASE), null);
  assert.strictEqual(L.homeLine(null), null);
  assert.strictEqual(L.homeLine(Object.assign({}, BASE, { state: 'backoff', backoff_until: 'x' })), null);
  const h = L.homeLine(Object.assign({}, BASE, { state: 'halted', halted: true }));
  assert.deepStrictEqual([h.text, h.cls, h.tab], ['loop halted', 'warn', 'system']);
  const s = L.homeLine(Object.assign({}, BASE, { state: 'stale', stale: true,
    stuck: [{ id: 'P130', state: 'adjudicate' }] }));
  assert.deepStrictEqual([s.text, s.cls, s.title], ['loop stale, 1 stuck', 'bad', 'P130 adjudicate']);
  const k = L.homeLine(Object.assign({}, BASE, { stuck: [{ id: 'P131', state: 'gave-up' }] }));
  assert.deepStrictEqual([k.text, k.cls], ['loop 1 stuck', 'warn']);
});

test('wiring: System Loop card from /api/loop, Home line, page script, safe DOM', () => {
  const d = read('dashboard/dashboard.js');
  assert.match(d, /card\('Loop', lp\)/);
  assert.match(d, /getJSON\('\/api\/loop'\)/);
  assert.ok(d.indexOf("card('Loop'") > d.indexOf("card('Signal health'"), 'Loop sits under Signal health');
  const h = read('dashboard/home.js');
  assert.match(h, /loop: '\/api\/loop'/);
  assert.match(h, /EWLoop\.homeLine/);
  const html = read('dashboard/index.html');
  const i = html.indexOf('<script src="loopstatus.js"></script>');
  assert.ok(i > 0 && i < html.indexOf('<script src="home.js"></script>') &&
    i < html.indexOf('<script src="dashboard.js"></script>'));
  const src = read('dashboard/loopstatus.js');
  assert.ok(!/innerHTML|insertAdjacentHTML|document\./.test(src), 'pure helpers, no DOM');
  const body = d.slice(d.indexOf('function paintLoop'), d.indexOf('function getJSON'));
  assert.ok(body.length > 0 && !/innerHTML/.test(body), 'Loop card builds nodes with DOM APIs');
});
