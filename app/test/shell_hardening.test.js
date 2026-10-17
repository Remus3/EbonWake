'use strict';
// Plan 148 (audit app-shell): regressions for the findings fixed in the
// Electron shell - main.js local HTTP (shared/localhttp.js), overlay.js GETs,
// selftest.js result write and shared/ew.css class collisions.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const http = require('http');
const os = require('os');
const path = require('path');
const vm = require('vm');
const C = require('../shared/ewcore');
const L = require('../shared/localhttp');

const APP = path.join(__dirname, '..');
const read = (p) => fs.readFileSync(path.join(APP, p), 'utf8');

// ---- APP-SHELL-01: a reply cut off mid-body settles ----

function withServer(handler, fn) {
  return new Promise((resolve, reject) => {
    const srv = http.createServer(handler);
    srv.listen(0, '127.0.0.1', async () => {
      try {
        resolve(await fn('http://127.0.0.1:' + srv.address().port));
      } catch (e) {
        reject(e);
      } finally {
        srv.closeAllConnections();
        srv.close();
      }
    });
  });
}

function within(p, ms) {
  return Promise.race([p, new Promise((r) => setTimeout(() => r('PENDING'), ms))]);
}

function cutOff(req, res) {
  req.resume();
  res.writeHead(200, { 'Content-Type': 'application/json', 'Content-Length': '100', Server: 'Ebonwake' });
  res.write('{"status":');
  setTimeout(() => res.socket.destroy(), 30);
}

test('APP-SHELL-01: a GET whose reply is cut off mid-body resolves null, never hangs', async () => {
  const v = await withServer(cutOff, (base) => within(L.get(base, '/api/health', 5000), 2000));
  assert.strictEqual(v, null);
});

test('APP-SHELL-01: a POST whose reply is cut off mid-body resolves not-ok, never hangs', async () => {
  const v = await withServer(cutOff, (base) => within(L.post(base, '/api/today', { a: 1 }, 5000), 2000));
  assert.notStrictEqual(v, 'PENDING');
  assert.strictEqual(v.ok, false);
  assert.match(v.error, /^server offline \(/);
});

test('APP-SHELL-01: a stalled body times out; full replies still parse', async () => {
  const stall = (req, res) => { res.writeHead(200, { 'Content-Length': '100' }); res.write('{'); };
  const v = await withServer(stall, (base) => within(L.get(base, '/x', 200), 2000));
  assert.strictEqual(v, null);
  const okH = (req, res) => {
    let b = '';
    req.on('data', (c) => { b += c; });
    req.on('end', () => {
      res.writeHead(req.method === 'POST' ? 201 : 200, { 'Content-Type': 'application/json', Server: 'Ebonwake 1' });
      res.end(JSON.stringify({ method: req.method, body: b }));
    });
  };
  const g = await withServer(okH, (base) => L.get(base, '/api/version', 1500));
  assert.deepStrictEqual(g, { status: 200, server: 'Ebonwake 1', doc: { method: 'GET', body: '' } });
  const p = await withServer(okH, (base) => L.post(base, '/api/today', { a: 1 }, 1500));
  assert.deepStrictEqual(p, { ok: true, status: 201, data: { method: 'POST', body: '{"a":1}' } });
  const bad = (req, res) => { req.resume(); res.writeHead(400); res.end('{"error":"nope"}'); };
  const e = await withServer(bad, (base) => L.post(base, '/api/today', {}, 1500));
  assert.deepStrictEqual(e, { ok: false, status: 400, error: 'nope' });
  const off = await L.get('http://127.0.0.1:1', '/x', 500);
  assert.strictEqual(off, null);
});

test('APP-SHELL-01: main.js reaches the server only through shared/localhttp', () => {
  const m = read('main.js');
  assert.match(m, /require\('\.\/shared\/localhttp'\)/);
  assert.doesNotMatch(m, /(^|[^\w])https?\.(get|request)\(/);
  assert.doesNotMatch(m, /require\('http'\)/);
});

// ---- APP-SHELL-02: an overlay GET that never answers times out ----

class El {
  constructor(id, hidden) {
    this.id = id;
    this.hidden = hidden;
    this.textContent = '';
    this.className = '';
    this.title = '';
    this.children = [];
    this.parent = null;
    this.style = { setProperty() {} };
  }
  get firstChild() { return this.children[0] || null; }
  appendChild(c) {
    if (c.parent) c.parent.children.splice(c.parent.children.indexOf(c), 1);
    c.parent = this;
    this.children.push(c);
    return c;
  }
  removeChild(c) {
    this.children.splice(this.children.indexOf(c), 1);
    c.parent = null;
    return c;
  }
}

function hungOverlay() {
  const html = read('overlay/index.html');
  const els = {};
  for (const m of html.matchAll(/<(\w+)[^>]*\bid="([^"]+)"([^>]*)>/g)) {
    els[m[2]] = new El(m[2], /\bhidden\b/.test(m[0]));
  }
  const calls = { fetch: [], timers: [] };
  function FakeES() { this.listeners = {}; }
  FakeES.prototype.addEventListener = function (n, fn) { this.listeners[n] = fn; };
  FakeES.prototype.close = function () {};
  const sandbox = {
    window: { location: { search: '' }, EWCore: C, ewOverlay: { reportSize() {} } },
    document: {
      getElementById: (id) => els[id] || null,
      createElement: () => new El(null, false),
      createTextNode: (t) => { const e = new El(null, false); e.textContent = t; return e; },
      body: { getBoundingClientRect: () => ({ height: 100 }) },
      documentElement: { style: { setProperty() {} } }
    },
    // A server that accepts and never answers: only an abort settles a GET.
    fetch: (url, opts) => {
      calls.fetch.push({ url, opts });
      return new Promise((resolve, reject) => {
        if (opts && opts.signal) opts.signal.addEventListener('abort', () => reject(new Error('aborted')));
      });
    },
    AbortController,
    EventSource: FakeES,
    setInterval: () => 0,
    setTimeout: (fn, ms) => { calls.timers.push({ fn, ms }); return calls.timers.length; },
    clearTimeout: () => {},
    Date, JSON, Math, Object, Promise, URLSearchParams
  };
  vm.createContext(sandbox);
  vm.runInContext(read('overlay/overlay.js'), sandbox);
  return { els, calls };
}

const settle = () => new Promise((r) => setImmediate(r));

test('APP-SHELL-02: an overlay GET to a server that never answers times out and reads offline', async () => {
  const r = hungOverlay();
  await settle();
  assert.strictEqual(r.els['ov-today'].textContent, '-');
  const today = r.calls.fetch.find((f) => f.url.endsWith('/api/today'));
  assert.ok(today && today.opts && today.opts.signal, 'the GET carries an abort signal');
  assert.ok(r.calls.fetch.every((f) => !f.opts.method), 'still read-only GETs');
  const aborts = r.calls.timers.filter((t) => t.ms >= 1000 && t.ms <= 30000);
  assert.ok(aborts.length >= r.calls.fetch.length, 'one bounded timer per GET');
  aborts.forEach((t) => t.fn());
  await settle();
  await settle();
  assert.strictEqual(r.els['ov-today'].textContent, 'offline');
  assert.strictEqual(r.els['ov-today'].className, 'ew-stale');
});

// ---- APP-SHELL-03: the self-test result is written tmp-then-rename ----

test('APP-SHELL-03: selftest writes its result JSON atomically (tmp then rename)', async () => {
  const selftest = require('../selftest');
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ewst-'));
  const out = path.join(dir, 'out.json');
  const renames = [];
  const realRename = fs.renameSync;
  fs.renameSync = function (a, b) { renames.push([a, b]); return realRename.apply(fs, arguments); };
  process.env.EW_SELFTEST_STAY = '1';
  try {
    // A dashboard that fails at once: the result is still written.
    await selftest.run({
      app: { quit() {} }, out: out, wait: () => Promise.resolve(),
      dashboard: { webContents: { isLoading: () => { throw new Error('boom'); } } },
      overlay: null, keys: {}
    });
    const res = JSON.parse(fs.readFileSync(out, 'utf8'));
    assert.match(res.error, /boom/);
    assert.ok(renames.some((x) => x[1] === out && x[0] !== out), JSON.stringify(renames));
    assert.deepStrictEqual(fs.readdirSync(dir), ['out.json'], 'no tmp left behind');
  } finally {
    fs.renameSync = realRename;
    delete process.env.EW_SELFTEST_STAY;
    fs.rmSync(dir, { recursive: true, force: true, maxRetries: 3 });
  }
});

// ---- APP-SHELL-04 / 05: one display per element class combination ----

// A tiny cascade over ew.css: rules whose selectors are class compounds
// (optionally with ancestor compounds); the winner is highest class count,
// then last in the file. Enough to see one class's rule clobber another's.
function cssRules() {
  const css = read('shared/ew.css').replace(/\/\*[\s\S]*?\*\//g, '');
  const rules = [];
  for (const m of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const d = /(?:^|;)\s*display:\s*([a-z-]+)/.exec(m[2]);
    if (!d) continue;
    for (const sel of m[1].split(',').map((s) => s.trim())) {
      if (!/^[.a-z0-9_ -]+$/i.test(sel)) continue;
      const parts = sel.split(/\s+/).map((p) => p.split('.').filter(Boolean));
      rules.push({ sel, parts, display: d[1], order: rules.length });
    }
  }
  return rules;
}

function displayOf(classes, ancestors) {
  const has = (set, comp) => comp.every((c) => set.indexOf(c) >= 0);
  let best = null;
  for (const r of cssRules()) {
    const last = r.parts[r.parts.length - 1];
    if (!has(classes, last)) continue;
    if (!r.parts.slice(0, -1).every((p) => has(ancestors || [], p))) continue;
    const spec = r.parts.reduce((n, p) => n + p.length, 0);
    if (!best || spec > best.spec || (spec === best.spec && r.order > best.order)) best = { spec, order: r.order, r };
  }
  return best ? best.r.display : null;
}

test('APP-SHELL-04: Grind .ew-srow rows keep their grid; Settings rows are flex', () => {
  assert.strictEqual(displayOf(['ew-srow'], ['ew-grind', 'ew-card']), 'grid');
  assert.strictEqual(displayOf(['ew-srow'], ['ew-card', 'ew-sgroup']), 'flex');
});

test('APP-SHELL-05: Market watch rows (ew-mrow ew-wrow) keep the plan 027 grid; This week rows flex', () => {
  assert.strictEqual(displayOf(['ew-mrow', 'ew-wrow'], ['ew-list']), 'grid');
  assert.strictEqual(displayOf(['ew-trow', 'ew-wrow', 'done'], ['ew-list']), 'flex');
});
