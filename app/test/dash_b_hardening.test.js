'use strict';
// Plan 146 (audit app-dash-b): regressions for the findings fixed in
// app/dashboard/ toast.js, pets.js and progress.js. Each module runs in a vm
// against a minimal fake DOM (no Electron, no network).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const C = require('../shared/ewcore');

const APP = path.join(__dirname, '..');
const read = (p) => fs.readFileSync(path.join(APP, p), 'utf8');

// ---- fake DOM ----

class El {
  constructor(tag) {
    this.tagName = String(tag || 'div').toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.className = '';
    this.dataset = {};
    this.style = {};
    this.attrs = {};
    this.listeners = {};
    this.hidden = false;
    this.disabled = false;
    this.checked = false;
    this.value = '';
    this.title = '';
    this._text = '';
    this.root = false;
    const self = this;
    this.classList = {
      add(c) { if (!self.classList.contains(c)) self.className = (self.className + ' ' + c).trim(); },
      remove(c) { self.className = self.className.split(/\s+/).filter((x) => x && x !== c).join(' '); },
      contains(c) { return self.className.split(/\s+/).indexOf(c) >= 0; }
    };
  }
  get textContent() { return this._text + this.children.map((c) => c.textContent).join(''); }
  set textContent(v) {
    this.children.forEach((c) => { c.parentNode = null; });
    this.children = [];
    this._text = String(v);
  }
  get isConnected() {
    let n = this;
    while (n) { if (n.root) return true; n = n.parentNode; }
    return false;
  }
  get firstChild() { return this.children[0] || null; }
  get previousSibling() {
    const p = this.parentNode;
    if (!p) return null;
    return p.children[p.children.indexOf(this) - 1] || null;
  }
  get options() { return this.children; }
  appendChild(c) { return this.insertBefore(c, null); }
  insertBefore(c, ref) {
    if (c.parentNode) c.parentNode.removeChild(c);
    c.parentNode = this;
    const i = ref ? this.children.indexOf(ref) : -1;
    if (i < 0) this.children.push(c); else this.children.splice(i, 0, c);
    return c;
  }
  removeChild(c) {
    this.children.splice(this.children.indexOf(c), 1);
    c.parentNode = null;
    return c;
  }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  contains(n) {
    while (n) { if (n === this) return true; n = n.parentNode; }
    return false;
  }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  removeAttribute(k) { delete this.attrs[k]; }
  addEventListener(n, fn) { (this.listeners[n] = this.listeners[n] || []).push(fn); }
  fire(n) { (this.listeners[n] || []).forEach((fn) => fn({ preventDefault() {}, stopPropagation() {}, target: this })); }
  focus() {}
  all() { return this.children.reduce((a, c) => a.concat([c], c.all()), []); }
  querySelectorAll(sel) {
    const m = sel.charAt(0) === '.' ? (n) => n.classList.contains(sel.slice(1)) : (n) => n.tagName === sel.toUpperCase();
    return this.all().filter(m);
  }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
}

function sandbox(win, extra) {
  const body = new El('body');
  body.root = true;
  const ctx = Object.assign({
    window: Object.assign({ EWCore: C }, win),
    document: {
      body: body,
      activeElement: null,
      hidden: false,
      visibilityState: 'visible',
      createElement: (t) => new El(t),
      createElementNS: (ns, t) => new El(t),
      createTextNode: (t) => { const e = new El('#text'); e.textContent = t; return e; },
      getElementById: () => null,
      querySelectorAll: (s) => body.querySelectorAll(s),
      addEventListener() {},
      contains: (n) => body.contains(n)
    },
    setInterval: () => 0,
    clearInterval() {},
    setTimeout: () => 0,
    clearTimeout() {},
    Date, JSON, Math, Object, Promise, Array, String, Number, Error, TypeError, isFinite
  }, extra || {});
  vm.createContext(ctx);
  return ctx;
}

const settle = () => new Promise((r) => setImmediate(r));
async function settleAll() { for (let i = 0; i < 6; i++) await settle(); }

function okFetch(bodies) {
  return (url) => {
    const p = url.slice(C.SERVER.length);
    const b = p in bodies ? bodies[p] : null;
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(b) });
  };
}

// A dashboard preload whose POSTs stay pending until the test answers them.
function heldBridge() {
  const calls = [];
  return {
    calls,
    api: {
      post(route, body) {
        return new Promise((resolve) => { calls.push({ route, body, resolve }); });
      }
    }
  };
}

function loadWithToast(ctx, file) {
  vm.runInContext(read('dashboard/toast.js'), ctx, { filename: 'toast.js' });
  vm.runInContext(read('dashboard/' + file), ctx, { filename: file });
}

// ---- APP-DASH-B-01: toast.js notify rounds never overlap ----

test('APP-DASH-B-01: a notify round still in flight is not started again', async () => {
  const fetches = [];
  let tick = null;
  const ctx = sandbox({ ewApi: { post: () => Promise.resolve({ ok: true }) } }, {
    fetch: (url) => { fetches.push(url); return new Promise(() => {}); }, // a hung server
    setInterval: (fn) => { tick = fn; return 1; }
  });
  vm.runInContext(read('dashboard/toast.js'), ctx, { filename: 'toast.js' });
  const first = fetches.length;
  assert.ok(first >= 2, 'the first round fetched');
  assert.strictEqual(typeof tick, 'function');
  tick();
  tick();
  await settle();
  assert.strictEqual(fetches.length, first, 'no new GETs pile up while the round is pending');
});

test('APP-DASH-B-01: the next round runs once the previous one has settled', async () => {
  const fetches = [];
  let tick = null;
  const ctx = sandbox({ ewApi: { post: () => Promise.resolve({ ok: true }) } }, {
    fetch: (url) => { fetches.push(url); return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) }); },
    setInterval: (fn) => { tick = fn; return 1; }
  });
  vm.runInContext(read('dashboard/toast.js'), ctx, { filename: 'toast.js' });
  await settleAll();
  const first = fetches.length;
  tick();
  await settleAll();
  assert.ok(fetches.length > first, 'a settled round lets the next one fetch');
  const failing = [];
  let tick2 = null;
  const ctx2 = sandbox({ ewApi: { post: () => Promise.resolve({ ok: true }) } }, {
    fetch: (url) => { failing.push(url); return Promise.reject(new TypeError('offline')); },
    setInterval: (fn) => { tick2 = fn; return 1; }
  });
  vm.runInContext(read('dashboard/toast.js'), ctx2, { filename: 'toast.js' });
  await settleAll();
  const n = failing.length;
  tick2();
  await settleAll();
  assert.ok(failing.length > n, 'an offline server never wedges the loop');
});

// ---- APP-DASH-B-02: pets.js goal toggles never drop each other ----

const PETS = {
  roster: [], goals: [], coverage: { out: 0, max_out: 5 },
  goal_options: [{ id: 'gather', title: 'Gathering' }, { id: 'xp', title: 'Combat XP' }]
};

test('APP-DASH-B-02: a second goal ticked before the first save answers keeps both', async () => {
  const br = heldBridge();
  const ctx = sandbox({ ewApi: br.api }, { fetch: okFetch({ '/api/pets': JSON.parse(JSON.stringify(PETS)) }) });
  loadWithToast(ctx, 'pets.js');
  const panel = new El('div');
  ctx.document.body.appendChild(panel);
  ctx.window.EWPets.mount(panel);
  await settleAll();
  const boxes = panel.querySelector('.ew-bticks').querySelectorAll('input');
  assert.strictEqual(boxes.length, 2);
  boxes[0].checked = true;
  boxes[0].fire('change');
  boxes[1].checked = true;
  boxes[1].fire('change');
  assert.strictEqual(br.calls.length, 2);
  assert.deepStrictEqual(Array.from(br.calls[0].body.goals), ['gather']);
  assert.deepStrictEqual(Array.from(br.calls[1].body.goals).sort(), ['gather', 'xp'],
    'the second save carries the first tick too');
  // Unticking one keeps the other.
  boxes[0].checked = false;
  boxes[0].fire('change');
  assert.deepStrictEqual(Array.from(br.calls[2].body.goals), ['xp']);
});

// ---- APP-DASH-B-03: progress.js claim button re-enables on a failed save ----

const ISO = '2026-10-10T00:00:00Z';
const PROGRESS = {
  character: {}, profile: null, lifeskill: null, seeds: [],
  tracks: [{ id: 's1', title: 'Season', kind: 'season', objectives: [
    { id: 'o1', title: 'Reach 60', kind: 'level', target: 60, done_at: ISO, claimed_at: null }
  ] }]
};

test('APP-DASH-B-03: a claim that fails leaves its button usable again', async () => {
  const br = heldBridge();
  const ctx = sandbox({ ewApi: br.api }, { fetch: okFetch({ '/api/progress': JSON.parse(JSON.stringify(PROGRESS)) }) });
  loadWithToast(ctx, 'progress.js');
  const panel = new El('div');
  ctx.document.body.appendChild(panel);
  ctx.window.EWProgress.mount(panel);
  await settleAll();
  const claimBtn = () => panel.querySelectorAll('button').filter((b) => b.textContent === 'claim')[0];
  const b = claimBtn();
  assert.ok(b, 'a claim button for the done objective');
  b.fire('click');
  assert.strictEqual(b.disabled, true, 'disabled while the save runs');
  assert.strictEqual(br.calls.length, 1);
  assert.strictEqual(br.calls[0].route, '/api/progress');
  br.calls[0].resolve({ ok: false, error: 'server said no' });
  await settleAll();
  const now = claimBtn();
  assert.ok(now, 'the claim button is still there');
  assert.strictEqual(now.disabled, false, 'a failed claim can be retried');
});
