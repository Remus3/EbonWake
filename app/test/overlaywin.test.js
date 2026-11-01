'use strict';
// MAIN ORDER Nee58d0 items 5-7 (2026-10-31 UI/UX round): overlay follows
// the game's foreground (EW-OVERLAY-FOCUS), placement by display ID
// (EW-DISPLAY-BY-ID) and optional content protection (EW-CAPTURE-OPT).
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const W = require('../shared/overlaywin');

const APP = path.join(__dirname, '..');
const read = (f) => fs.readFileSync(path.join(APP, f), 'utf8');

function fakeSource() {
  // A fake foreground source: the test pushes what the poller would report.
  const s = { listener: null, on(fn) { s.listener = fn; }, emit(line) { s.listener(W.parseForeground(line)); } };
  return s;
}

function gateWith(src) {
  const shown = [];
  const g = W.createFocusGate({ apply: (v) => shown.push(v) });
  src.on((fg) => g.onForeground(fg));
  return { g, shown };
}

test('EW-OVERLAY-FOCUS: game loses the foreground -> hide; regains it -> show', () => {
  const src = fakeSource();
  const { g, shown } = gateWith(src);
  g.setWanted(true);
  assert.deepStrictEqual(shown, [true]);
  src.emit('fg=BlackDesert64|game=1');
  assert.strictEqual(g.visible(), true);
  src.emit('fg=chrome|game=1');
  assert.strictEqual(g.visible(), false);
  src.emit('fg=BlackDesert64|game=1');
  assert.strictEqual(g.visible(), true);
  assert.deepStrictEqual(shown, [true, false, true]);
});

test('EW-OVERLAY-FOCUS: a minimised game (foreground elsewhere / none) hides it', () => {
  const src = fakeSource();
  const { g } = gateWith(src);
  g.setWanted(true);
  src.emit('fg=BlackDesert64|game=1');
  src.emit('fg=|game=1');
  assert.strictEqual(g.visible(), false);
  src.emit('fg=explorer|game=1');
  assert.strictEqual(g.visible(), false);
});

test('EW-OVERLAY-FOCUS: the hotkey toggle still rules; game closed = old behaviour', () => {
  const src = fakeSource();
  const { g, shown } = gateWith(src);
  src.emit('fg=BlackDesert64|game=1');
  assert.strictEqual(g.visible(), false);           // not wanted
  g.setWanted(true);
  assert.strictEqual(g.visible(), true);
  g.setWanted(false);
  assert.strictEqual(g.visible(), false);
  src.emit('fg=notepad|game=0');                    // no game: toggle only
  g.setWanted(true);
  assert.strictEqual(g.visible(), true);
  assert.deepStrictEqual(shown, [true, false, true]);
});

test('EW-OVERLAY-FOCUS: no source, a garbled line or the gate off never hides it', () => {
  const g = W.createFocusGate({ apply() {} });
  g.setWanted(true);
  assert.strictEqual(g.visible(), true);
  g.onForeground(W.parseForeground('garbage'));
  assert.strictEqual(g.visible(), true);
  const off = W.createFocusGate({ apply() {}, enabled: false });
  off.setWanted(true);
  off.onForeground(W.parseForeground('fg=chrome|game=1'));
  assert.strictEqual(off.visible(), true);
});

test('parseForeground: exact shape only', () => {
  assert.deepStrictEqual(W.parseForeground('fg=BlackDesert64|game=1'), { name: 'BlackDesert64', game: true });
  assert.deepStrictEqual(W.parseForeground('fg=|game=0'), { name: '', game: false });
  for (const bad of ['', 'fg=x', 'fg=x|game=2', 'x|game=1', null, 7]) assert.strictEqual(W.parseForeground(bad), null);
  assert.strictEqual(W.isGameProcess('BlackDesert64'), true);
  assert.strictEqual(W.isGameProcess('blackdesert64'), true);
  assert.strictEqual(W.isGameProcess('chrome'), false);
});

test('EW-OVERLAY-FOCUS: main wires the gate, never under EW_SELFTEST; poller reads only the foreground', () => {
  const m = read('main.js');
  assert.match(m, /require\('\.\/shared\/overlaywin'\)/);
  assert.match(m, /createFocusGate\(/);
  assert.match(m, /!process\.env\.EW_SELFTEST[^\n]*startForeground/);
  const ps = read('shared/foreground.ps1');
  assert.match(ps, /GetForegroundWindow/);
  assert.doesNotMatch(ps, /SetWindowsHookEx|SendInput|keybd_event|mouse_event|PostMessage|SendMessage|ReadProcessMemory|OpenProcess/);
  assert.ok(/^[\x00-\x7f]*$/.test(ps) && !ps.includes('\r'), 'ASCII + LF');
});

const DISPLAYS = [{ id: 11, workArea: { x: 0, y: 0, width: 1920, height: 1040 } },
  { id: 22, workArea: { x: 1920, y: 0, width: 2560, height: 1400 } }];
const PRIMARY = DISPLAYS[0];

test('EW-DISPLAY-BY-ID: a picked index is saved as its display ID and followed after a reorder', () => {
  const first = W.resolveDisplay(DISPLAYS, PRIMARY, 1, null);
  assert.strictEqual(first.display.id, 22);
  assert.deepStrictEqual(first.saved, { index: 1, id: 22 });
  const reordered = [DISPLAYS[1], DISPLAYS[0]];       // monitors reconnected
  const again = W.resolveDisplay(reordered, PRIMARY, 1, first.saved);
  assert.strictEqual(again.display.id, 22);
  assert.deepStrictEqual(again.saved, first.saved);
});

test('EW-DISPLAY-BY-ID: the saved display missing lands on primary, silently', () => {
  const r = W.resolveDisplay([PRIMARY], PRIMARY, 1, { index: 1, id: 22 });
  assert.strictEqual(r.display, PRIMARY);
  assert.deepStrictEqual(r.saved, { index: 1, id: 22 });  // kept: it may come back
  assert.strictEqual(W.resolveDisplay([PRIMARY], PRIMARY, 5, null).display, PRIMARY);
});

test('EW-DISPLAY-BY-ID: null index = primary; a changed index re-saves', () => {
  assert.deepStrictEqual(W.resolveDisplay(DISPLAYS, PRIMARY, null, { index: 1, id: 22 }),
    { display: PRIMARY, saved: null });
  const r = W.resolveDisplay(DISPLAYS, PRIMARY, 0, { index: 1, id: 22 });
  assert.deepStrictEqual(r, { display: PRIMARY, saved: { index: 0, id: 11 } });
  assert.strictEqual(W.validSaved({ index: 1, id: 22 }), true);
  for (const bad of [null, {}, { index: 1 }, { index: '1', id: 2 }, []]) assert.strictEqual(W.validSaved(bad), false);
});

test('EW-CAPTURE-OPT: content protection is opt-in, default off', () => {
  for (const cfg of [undefined, null, {}, { overlay: {} }, { overlay: { content_protection: 'yes' } },
    { overlay: { content_protection: 1 } }, { overlay: { content_protection: false } }]) {
    assert.strictEqual(W.contentProtection(cfg), false, JSON.stringify(cfg));
  }
  assert.strictEqual(W.contentProtection({ overlay: { content_protection: true } }), true);
  const m = read('main.js');
  assert.match(m, /if \(W\.contentProtection\(cfg\)\) overlay\.setContentProtection\(true\)/);
  const ex = JSON.parse(read('../config/local.example.json'));
  assert.strictEqual(ex.overlay.content_protection, false);
  assert.strictEqual(ex.overlay.focus_hide, true);
});
