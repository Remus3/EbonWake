'use strict';
// Plan 132: My Info (P) exact XP reads - the review / applied row value, its
// label, no fix body, and the absolute XP/h on the overlay leveling line.
// No network, no DOM.
const test = require('node:test');
const assert = require('node:assert');
const C = require('../shared/ewcore');

const V = { level: 66, xp: 1234567890, to_next: 3765432110, pct: 24.691 };

test('a myinfo_xp review item keeps its exact value and reads in full digits', () => {
  const a = C.normalizeOcrAuto({ review: [
    { id: 'r1', kind: 'myinfo_xp', name: 'myinfo_xp', value: V, conf: 0.9, file: 'a.jpg' },
    { id: 'r2', kind: 'myinfo_xp', name: 'myinfo_xp', value: Object.assign({}, V, { xp: -1 }) },
    { id: 'r3', kind: 'myinfo_xp', name: 'myinfo_xp', value: Object.assign({}, V, { extra: 1 }) }
  ] });
  assert.deepStrictEqual(a.review.map((r) => r.id), ['r1']);
  assert.deepStrictEqual(a.review[0].value, V);
  assert.strictEqual(C.ocrAutoLabel(a.review[0]),
    'Lv 66 XP 1,234,567,890 / 5,000,000,000 (24.691%) (90%)');
});

test('a myinfo_xp read is accept / discard only', () => {
  assert.strictEqual(C.ocrFixHint('myinfo_xp'), '');
  assert.strictEqual(C.ocrFixBody('r1', 'myinfo_xp', '66 1234'), null);
});

test('an auto-applied myinfo_xp row is listed with its label and Undo', () => {
  const a = C.normalizeOcrAuto({ applied: [
    { id: 'a1', kind: 'myinfo_xp', value: V, conf: 0.97, file: 'a.jpg', undone: false },
    { id: 'a2', kind: 'myinfo_xp', value: { level: 66, xp: 1, to_next: 0 } }
  ] });
  assert.deepStrictEqual(a.applied.map((r) => r.id), ['a1']);
  assert.strictEqual(C.ocrAppliedLabel(a.applied[0]),
    'Lv 66 XP 1,234,567,890 / 5,000,000,000 (24.691%) (97%)');
  assert.deepStrictEqual(C.ocrAppliedUndo(a.applied[0]), { undo: 'a1' });
});

const BODY = { level: 66, pct: 24.691, level_source: 'ocr', rate_pct_h: 10, eta_next_s: 3600,
  milestones: [70], hot: { active: [], next: null }, xp_stack_pct: 0, xp_parts: [] };

test('the leveling line adds the absolute XP/h when the server has one', () => {
  const at = Date.now();
  const line = C.levelingLine(Object.assign({}, BODY, { rate_xp_h: 512000000 }), at, at);
  assert.match(line, /10\.0 %\/h \| 512M XP\/h \| ETA/);
  assert.match(C.levelingLine(Object.assign({}, BODY, { rate_xp_h: 1250000000 }), at, at),
    /1\.25B XP\/h/);
  assert.match(C.levelingLine(Object.assign({}, BODY, { rate_xp_h: 40000 }), at, at),
    /40\.0K XP\/h/);
  assert.doesNotMatch(C.levelingLine(BODY, at, at), /XP\/h/);
  assert.doesNotMatch(C.levelingLine(Object.assign({}, BODY, { rate_xp_h: 1.5 }), at, at),
    /XP\/h/);
});
