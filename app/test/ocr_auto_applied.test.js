'use strict';
// Plan 111: auto-applied OCR rows (book use, zone read, boss loot tick) -
// the applied-list formatter, the Undo body and the ocrApplied toast rule.
// No network, no DOM.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const C = require('../shared/ewcore');

const read = (p) => fs.readFileSync(path.join(__dirname, '..', p), 'utf8');

const APPLIED = [
  { id: 'a3', at: '2026-10-10T01:00:00+00:00', kind: 'boss', value: { day: '2026-10-09', boss: 'Kzarka' },
    conf: 1, file: 'loot.jpg', undone: false },
  { id: 'a2', kind: 'zone_xp', conf: 0.97, file: 'z.jpg', undone: false,
    value: { zone_name: "Polly's Forest", recommended_level: 56,
      monsters: [{ name: 'A', xp_per_kill_pct: 0.1 }, { name: 'B', xp_per_kill_pct: 0.2 }] } },
  { id: 'a1', kind: 'book_use', conf: 0.962, file: 'b.jpg', undone: true,
    value: { size: 'large', pct_before: 10, pct_after: 17.5 } },
  { id: 'u1', kind: 'boss', value: { day: '2026-10-09', boss: 'Kzarka' } },
  { id: 'a9', kind: 'silver', value: 5 }, null,
  { id: 'a8', kind: 'book_use', value: { size: 'large', pct_before: 1, pct_after: 200 } }
];

test('normalizeOcrAuto: applied rows kept defensively, newest first, max 10', () => {
  const a = C.normalizeOcrAuto({ applied: APPLIED });
  assert.deepStrictEqual(a.applied.map((r) => r.id), ['a3', 'a2', 'a1']);
  assert.strictEqual(a.applied[1].value.monsters, 2);
  assert.deepStrictEqual(C.normalizeOcrAuto({}).applied, []);
  const many = Array.from({ length: 15 }, (_, i) => Object.assign({}, APPLIED[0], { id: 'a' + (20 - i) }));
  assert.strictEqual(C.normalizeOcrAuto({ applied: many }).applied.length, 10);
});

test('ocrAppliedLabel: one line per kind, conf, undone suffix', () => {
  const [boss, zone, book] = C.normalizeOcrAuto({ applied: APPLIED }).applied;
  assert.strictEqual(C.ocrAppliedLabel(boss), 'Kzarka loot ticked 2026-10-09 (100%)');
  assert.strictEqual(C.ocrAppliedLabel(zone), "zone Polly's Forest Lv 56, 2 monsters (97%)");
  assert.strictEqual(C.ocrAppliedLabel(book), 'large book used 10% -> 17.5% (96%) - undone');
});

test('ocrAppliedUndo: {undo: a<n>} for a live row, null once undone; the body validates', () => {
  const [boss, , book] = C.normalizeOcrAuto({ applied: APPLIED }).applied;
  const body = C.ocrAppliedUndo(boss);
  assert.deepStrictEqual(body, { undo: 'a3' });
  assert.strictEqual(C.validOcrBody(body), true);
  assert.strictEqual(C.validPost('/api/ocr', body), true);
  assert.strictEqual(C.ocrAppliedUndo(book), null);
  for (const bad of [null, {}, { id: 'u3' }, { id: 'a' }]) assert.strictEqual(C.ocrAppliedUndo(bad), null);
  for (const bad of [{ undo: 'a' }, { undo: 'b3' }, { undo: 'a3x' }]) assert.strictEqual(C.validOcrBody(bad), false);
});

test('ocrApplied rule: one toast per new live row, none on the baseline', () => {
  assert.strictEqual(C.notifyPrefs({}).ocrApplied, true);
  const t = Date.now();
  const prefs = { ocrApplied: true };
  const prev = { at: t, ocr: { applied: APPLIED.slice(1) } };
  const next = { at: t, ocr: { applied: APPLIED } };
  assert.deepStrictEqual(C.notifyRules(null, next, t, prefs), []);
  const hits = C.notifyRules(prev, next, t, prefs);
  assert.deepStrictEqual(hits.map((h) => [h.key, h.rule, h.title]),
    [['ocrApplied:a3', 'ocrApplied', 'Applied automatically']]);
  assert.match(hits[0].body, /Kzarka loot ticked/);
  // an undone row never toasts
  const gone = { at: t, ocr: { applied: [Object.assign({}, APPLIED[0], { undone: true })].concat(APPLIED.slice(1)) } };
  assert.deepStrictEqual(C.notifyRules(prev, gone, t, prefs), []);
});

test('game.js + toast.js: applied list with Undo above the review queue; toasts poll /api/ocr/auto', () => {
  const src = read('dashboard/game.js');
  assert.match(src, /Applied automatically/);
  assert.match(src, /C\.ocrAppliedLabel\(/);
  assert.match(src, /C\.ocrAppliedUndo\(/);
  assert.ok(src.indexOf('a.applied.forEach') < src.indexOf('a.review.forEach'));
  const toast = read('dashboard/toast.js');
  assert.ok(toast.indexOf("'/api/ocr/auto'") >= 0);
  assert.match(toast, /ocr: docs\.ocr/);
});
