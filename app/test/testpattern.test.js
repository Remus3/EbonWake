'use strict';
// Plan 175: overlay test pattern - a separate EW window, click-through and
// always-on-top like the overlay, shown for 10 s on the operator's press.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const TP = require('../shared/testpattern');
const C = require('../shared/ewcore');

const APP = path.join(__dirname, '..');
const read = (p) => fs.readFileSync(path.join(APP, p), 'utf8');

test('window config keeps ignoreMouseEvents true and always-on-top', () => {
  const c = TP.config({ x: 10, y: 20, width: 2560, height: 1440 });
  assert.strictEqual(c.ignoreMouseEvents, true);
  assert.strictEqual(c.options.alwaysOnTop, true);
  assert.strictEqual(c.alwaysOnTopLevel, 'screen-saver');
  assert.strictEqual(c.options.transparent, true);
  assert.strictEqual(c.options.focusable, false);
  assert.strictEqual(c.options.frame, false);
  assert.strictEqual(c.options.skipTaskbar, true);
  assert.deepStrictEqual([c.options.x, c.options.y, c.options.width, c.options.height], [10, 20, 2560, 1440]);
  assert.strictEqual(c.durationMs, 10000);
  const wp = c.options.webPreferences;
  assert.ok(wp.contextIsolation && wp.sandbox && !wp.nodeIntegration && !('preload' in wp));
  // Junk bounds still give a click-through always-on-top window.
  const j = TP.config(null);
  assert.strictEqual(j.ignoreMouseEvents, true);
  assert.strictEqual(j.options.alwaysOnTop, true);
});

function fakeTimers() {
  const q = [];
  return { q: q, setTimeout: (fn, ms) => { q.push({ fn: fn, ms: ms }); return q.length; }, clearTimeout: () => {} };
}

function fakeWin(calls) {
  return {
    setIgnoreMouseEvents: (v, o) => calls.push(['ignore', v, o]),
    setAlwaysOnTop: (v, lvl) => calls.push(['top', v, lvl]),
    showInactive: () => calls.push(['show']),
    close: () => calls.push(['close']),
    isDestroyed: () => false,
    on: () => {}
  };
}

test('runner applies click-through + top level, one at a time, closes after 10 s', () => {
  const calls = [];
  const t = fakeTimers();
  let opened = 0;
  const r = TP.createRunner((c) => { opened++; calls.push(['open', c.page]); return fakeWin(calls); }, t);
  const res = r.start({ x: 0, y: 0, width: 100, height: 100 });
  assert.deepStrictEqual(res, { ok: true, already: false, ms: 10000 });
  assert.deepStrictEqual(calls.slice(0, 4), [['open', 'overlay/testpattern.html'], ['ignore', true, { forward: false }],
    ['top', true, 'screen-saver'], ['show']]);
  assert.strictEqual(r.start({ x: 0, y: 0, width: 100, height: 100 }).already, true);
  assert.strictEqual(opened, 1);
  assert.strictEqual(t.q[0].ms, 10000);
  t.q[0].fn();
  assert.deepStrictEqual(calls[calls.length - 1], ['close']);
  assert.strictEqual(r.active(), false);
});

test('runner reports a failed open', () => {
  const r = TP.createRunner(() => { throw new Error('x'); }, fakeTimers());
  assert.strictEqual(r.start({ x: 0, y: 0, width: 1, height: 1 }).ok, false);
});

test('main wires the test pattern through the runner, dashboard-only, never the game', () => {
  const m = read('main.js');
  assert.match(m, /require\('\.\/shared\/testpattern'\)/);
  const at = m.indexOf("ipcMain.handle('ew:overlay-test'");
  assert.ok(at > 0);
  assert.match(m.slice(at, at + 300), /function \(event\) \{\s*if \(!dashboard \|\| event\.sender !== dashboard\.webContents\)/);
  assert.match(m, /new BrowserWindow\(c\.options\)/);
  assert.doesNotMatch(m, /uiohook|iohook|robotjs|nut-js|SetWindowsHookEx|sendInputEvent|getNativeWindowHandle/);
  assert.match(read('preload.js'), /overlayTest: function \(\) \{ return ipcRenderer\.invoke\('ew:overlay-test'\); \}/);
});

test('test pattern page is static: no script, strict CSP, transparent root', () => {
  const html = read('overlay/testpattern.html');
  assert.doesNotMatch(html, /<script/i);
  assert.match(html, /default-src 'none'/);
  assert.match(html, /<html[^>]*class="ew-overlay"/);
  assert.match(html, /EBONWAKE OVERLAY TEST/);
});

test('settings body accepts the overlay test answer and its clear only', () => {
  assert.strictEqual(C.validPost('/api/settings', { overlay_test: { renderer: 'dx12', seen: true } }), true);
  assert.strictEqual(C.validPost('/api/settings', { overlay_test: { renderer: 'dx11', seen: false } }), true);
  assert.strictEqual(C.validPost('/api/settings', { clear: 'overlay.test_pattern' }), true);
  for (const b of [{ overlay_test: { renderer: 'dx9', seen: true } }, { overlay_test: { renderer: 'dx12' } },
    { overlay_test: { renderer: 'dx12', seen: 'yes' } }, { overlay_test: { renderer: 'dx12', seen: true, x: 1 } },
    { overlay_test: { renderer: 'dx12', seen: true }, set: {} }, { overlay_test: null }]) {
    assert.strictEqual(C.validPost('/api/settings', b), false, JSON.stringify(b));
  }
});

test('settings tab draws the test pattern card and posts through the toast bridge', () => {
  const s = read('dashboard/settings.js');
  assert.match(s, /b\.overlayTest\(\)/);
  assert.match(s, /overlay_test: \{ renderer: sel\.value, seen: o\[0\] \}/);
  assert.match(s, /window\.EWToast\.via\(b\)\.post\('\/api\/settings', body\)/);
  assert.match(s, /p\.appendChild\(testPatternCard\(\)\)/);
});
