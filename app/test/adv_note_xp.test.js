'use strict';
// Plan 133: Adventurer's Note (F2) exact XP reads - the review / applied row
// value, its "F2" label and no fix body. No network, no DOM.
const test = require('node:test');
const assert = require('node:assert');
const C = require('../shared/ewcore');

const V = { level: 66, xp: 1234567890, to_next: 3765432110, pct: 24.691 };

test('an adv_note_xp review item keeps its exact value and is labelled F2', () => {
  const a = C.normalizeOcrAuto({ review: [
    { id: 'r1', kind: 'adv_note_xp', name: 'adv_note_xp', value: V, conf: 0.9, file: 'a.jpg' },
    { id: 'r2', kind: 'adv_note_xp', name: 'adv_note_xp', value: Object.assign({}, V, { xp: -1 }) }
  ] });
  assert.deepStrictEqual(a.review.map((r) => r.id), ['r1']);
  assert.deepStrictEqual(a.review[0].value, V);
  assert.strictEqual(C.ocrAutoLabel(a.review[0]),
    'F2 Lv 66 XP 1,234,567,890 / 5,000,000,000 (24.691%) (90%)');
});

test('an adv_note_xp read is accept / discard only', () => {
  assert.strictEqual(C.ocrFixHint('adv_note_xp'), '');
  assert.strictEqual(C.ocrFixBody('r1', 'adv_note_xp', '66 1234'), null);
});

test('an auto-applied adv_note_xp row is listed with its label and Undo', () => {
  const a = C.normalizeOcrAuto({ applied: [
    { id: 'a1', kind: 'adv_note_xp', value: V, conf: 0.97, file: 'a.jpg', undone: false }
  ] });
  assert.deepStrictEqual(a.applied.map((r) => r.id), ['a1']);
  assert.strictEqual(C.ocrAppliedLabel(a.applied[0]),
    'F2 Lv 66 XP 1,234,567,890 / 5,000,000,000 (24.691%) (97%)');
  assert.deepStrictEqual(C.ocrAppliedUndo(a.applied[0]), { undo: 'a1' });
});
