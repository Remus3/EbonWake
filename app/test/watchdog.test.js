'use strict';
// Plan 135: server watchdog state machine (pure) plus static guards on how
// main.js, preload.js and the dashboard wire it.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const W = require('../shared/watchdog');

const APP = path.join(__dirname, '..');
const read = (p) => fs.readFileSync(path.join(APP, p), 'utf8');
const MIN = 60000;

// Feed one probe every POLL_MS from t0; returns { state, actions: [[t, action]] }.
function run(state, probes, t0, busy) {
  const actions = [];
  let t = t0;
  for (const p of probes) {
    const r = W.next(state, p, t, busy ? { restarting: true } : undefined);
    state = r.state;
    if (r.action !== 'none') actions.push([t, r.action]);
    t += W.POLL_MS;
  }
  return { state, actions, t };
}
const fails = (n) => Array(n).fill('fail');
const oks = (n) => Array(n).fill('ok');

test('constants match the plan: 20 s poll, 3 fails, 1 min..30 min backoff, 6 an hour', () => {
  assert.strictEqual(W.POLL_MS, 20000);
  assert.strictEqual(W.FAILS_TO_RESTART, 3);
  assert.strictEqual(W.BACKOFF_START_MS, MIN);
  assert.strictEqual(W.BACKOFF_MAX_MS, 30 * MIN);
  assert.strictEqual(W.BACKOFF_RESET_MS, 10 * MIN);
  assert.strictEqual(W.MAX_PER_HOUR, 6);
  assert.strictEqual(W.LOG_CAP, 500);
});

test('three consecutive fails -> restart; fewer do nothing', () => {
  const r2 = run(W.initial(), fails(2), 0);
  assert.deepStrictEqual(r2.actions, []);
  const r3 = run(W.initial(), fails(3), 0);
  assert.deepStrictEqual(r3.actions, [[2 * W.POLL_MS, 'restart']]);
  assert.strictEqual(W.phase(r3.state), 'restarting');
});

test('one ok probe resets the fail count', () => {
  const r = run(W.initial(), ['fail', 'fail', 'ok', 'fail', 'fail'], 0);
  assert.deepStrictEqual(r.actions, []);
  assert.strictEqual(r.state.fails, 2);
});

test('unknown probe values count as fail; next never mutates its input', () => {
  const s = W.initial();
  const snap = JSON.stringify(s);
  const r = W.next(s, 'bogus', 0);
  assert.strictEqual(r.state.fails, 1);
  assert.strictEqual(JSON.stringify(s), snap);
  assert.strictEqual(W.next(null, 'ok', 0).action, 'none');
});

test('backoff between restarts: 1, 2, 4, 8, 16 min, then capped at 30', () => {
  // Server stays down: restart times are spaced by the doubling backoff.
  let st = W.initial();
  const at = [];
  for (let t = 0; t <= 200 * MIN; t += W.POLL_MS) {
    const r = W.next(st, 'fail', t);
    st = r.state;
    if (r.action === 'restart') at.push(t);
    if (r.action === 'give-up') break;
  }
  const gaps = at.slice(1).map((t, i) => (t - at[i]) / MIN);
  assert.deepStrictEqual(gaps.slice(0, 5), [1, 2, 4, 8, 16]);
  gaps.slice(5).forEach((g) => assert.ok(g >= 30 && g < 30.5, 'gap ' + g));
});

test('backoff resets after 10 min of ok probes, not before', () => {
  let r = run(W.initial(), fails(3), 0); // restart 1, backoff now 1 min
  r = run(r.state, fails(6), r.t); // restart 2 after 1 min, backoff 2 min
  assert.strictEqual(r.state.backoffMs, 2 * MIN);
  const short = run(r.state, oks(29), r.t); // 9 min 40 s ok
  assert.strictEqual(short.state.backoffMs, 2 * MIN);
  const long = run(r.state, oks(31), r.t); // past 10 min ok
  assert.strictEqual(long.state.backoffMs, 0);
  // With the backoff reset the next outage restarts at the third fail again.
  const again = run(long.state, fails(3), long.t);
  assert.deepStrictEqual(again.actions.map((a) => a[1]), ['restart']);
});

test('at most 6 restarts a rolling hour, then give-up once until an ok probe', () => {
  let st = W.initial();
  let t = 0;
  const acts = [];
  // Each outage is followed by a long recovery (backoff reset), so only the
  // hourly cap limits: 7 crashes inside the hour.
  for (let i = 0; i < 7; i++) {
    st.backoffMs = 0;
    const r = run(st, fails(5), t);
    r.actions.forEach((a) => acts.push(a[1]));
    st = r.state;
    t = r.t;
    const ok = run(st, ['ok'], t);
    st = ok.state;
    t = ok.t + 2 * MIN;
  }
  assert.deepStrictEqual(acts, ['restart', 'restart', 'restart', 'restart', 'restart', 'restart', 'give-up']);
  // The ok probe after the 7th outage cleared gave-up; a new outage inside
  // the same hour is still capped: one give-up, then silence while down.
  const down = run(st, fails(20), t);
  assert.deepStrictEqual(down.actions.map((a) => a[1]), ['give-up']);
  assert.strictEqual(W.phase(down.state), 'gave-up');
  // An ok probe clears gave-up.
  const up = run(down.state, ['ok'], down.t);
  assert.strictEqual(W.phase(up.state), 'ok');
  assert.strictEqual(up.state.gaveUp, false);
});

test('restarts older than an hour fall out of the cap', () => {
  const st = W.initial();
  st.restarts = [0, 1, 2, 3, 4, 5].map((i) => i * MIN);
  st.lastRestart = 5 * MIN;
  st.backoffMs = 0;
  const r = run(st, fails(3), 61 * MIN);
  assert.deepStrictEqual(r.actions.map((a) => a[1]), ['restart']);
  assert.strictEqual(W.summary(r.state, r.t - W.POLL_MS).restartsLastHour, 5);
});

test('a manual restart in flight: the watchdog does nothing and counts nothing', () => {
  const r = run(W.initial(), fails(10), 0, true);
  assert.deepStrictEqual(r.actions, []);
  assert.strictEqual(r.state.fails, 0);
});

test('summary and status line', () => {
  assert.deepStrictEqual(W.summary(W.initial(), 0),
    { state: 'ok', restartsLastHour: 0, lastRestart: null });
  assert.strictEqual(W.statusLine(W.summary(W.initial(), 0), 0), 'Watchdog: ok - no auto-restart in the last hour');
  const r = run(W.initial(), fails(3), 0);
  const s = W.summary(r.state, r.t);
  assert.strictEqual(s.state, 'restarting');
  assert.strictEqual(s.restartsLastHour, 1);
  assert.strictEqual(s.lastRestart, 2 * W.POLL_MS);
  const line = W.statusLine(s, s.lastRestart + 5 * MIN);
  assert.strictEqual(line, 'Watchdog: restarting - 1 auto-restart in the last hour, last 5 min ago');
  assert.match(W.statusLine({ state: 'gave-up', restartsLastHour: 6, lastRestart: 0 }, 30 * 1000),
    /^Watchdog: gave up - 6 auto-restarts in the last hour, last <1 min ago/);
  assert.strictEqual(W.statusLine(null, 0), null);
  assert.strictEqual(W.statusLine({ state: 'x' }, 0), null);
});

test('log rows: one JSON line appended, tail capped at 500', () => {
  const one = W.capLog('', { at: 't', reason: 'r', n: 1 });
  assert.strictEqual(one, '{"at":"t","reason":"r","n":1}\n');
  let text = '';
  for (let i = 1; i <= 505; i++) text = W.capLog(text, { at: 't', reason: 'r', n: i });
  const lines = text.trim().split('\n');
  assert.strictEqual(lines.length, 500);
  assert.strictEqual(JSON.parse(lines[0]).n, 6);
  assert.strictEqual(JSON.parse(lines[499]).n, 505);
  assert.strictEqual(W.capLog(null, { n: 1 }), '{"n":1}\n');
});

test('main.js wiring: one interval, getLocal health probe, existing restartServer, no new spawn', () => {
  const src = read('main.js');
  assert.match(src, /require\('\.\/shared\/watchdog'\)/);
  assert.match(src, /setInterval\(watchdogTick, watchdog\.POLL_MS\)/);
  assert.match(src, /getLocal\('\/api\/health'\)/);
  assert.match(src, /watchdog\.next\(/);
  assert.match(src, /await restartServer\(\)/);
  assert.strictEqual((src.match(/childProcess\.spawn\(/g) || []).length, 1);
  assert.match(src, /'ops', 'runtime', 'watchdog\.jsonl'/);
  assert.match(src, /ipcMain\.handle\('ew:watchdog'/);
  assert.doesNotMatch(src, /8940/);
});

test('preload and dashboard: read-only watchdog bridge, System card line, gave-up toast', () => {
  assert.match(read('preload.js'), /watchdog: function \(\) \{ return ipcRenderer\.invoke\('ew:watchdog'\); \}/);
  const html = read('dashboard/index.html');
  const iW = html.indexOf('<script src="../shared/watchdog.js"></script>');
  assert.ok(iW > 0 && iW < html.indexOf('<script src="dashboard.js"></script>'));
  const dash = read('dashboard/dashboard.js');
  assert.match(dash, /sys-watchdog/);
  assert.match(dash, /EWWatchdog\.statusLine/);
  assert.match(dash, /'gave-up'/);
  assert.match(dash, /EWToast\.toast\('bad'/);
});

test('module also installs window.EWWatchdog in a browser-like context', () => {
  const vm = require('vm');
  const ctx = { window: {} };
  vm.createContext(ctx);
  vm.runInContext(read('shared/watchdog.js'), ctx);
  assert.strictEqual(typeof ctx.window.EWWatchdog.statusLine, 'function');
});
