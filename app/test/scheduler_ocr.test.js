'use strict';
// Plan 127: a Black Spirit's Scheduler shot - the auto-applied Today tick row
// (label + Undo body) and the "unknown scheduler row" review item (accept /
// discard only). No network, no DOM.
const test = require('node:test');
const assert = require('node:assert');
const C = require('../shared/ewcore');

test('applied today row: label, Undo body, defensive value', () => {
  const a = C.normalizeOcrAuto({ applied: [
    { id: 'a5', kind: 'today', conf: 0.96, file: 's.jpg', undone: false,
      value: { row: 'guild-mission', title: 'Guild mission' } },
    { id: 'a4', kind: 'today', value: { row: '', title: 'x' } },
    { id: 'a3', kind: 'today', value: 'Guild mission' }
  ] });
  assert.deepStrictEqual(a.applied.map((r) => r.id), ['a5']);
  assert.strictEqual(C.ocrAppliedLabel(a.applied[0]), 'Guild mission ticked (Scheduler) (96%)');
  assert.deepStrictEqual(C.ocrAppliedUndo(a.applied[0]), { undo: 'a5' });
  const undone = Object.assign({}, a.applied[0], { undone: true });
  assert.match(C.ocrAppliedLabel(undone), / - undone$/);
  assert.strictEqual(C.ocrAppliedUndo(undone), null);
});

test('unknown scheduler row review item: label, no fix', () => {
  const a = C.normalizeOcrAuto({ review: [
    { id: 'r7', kind: 'scheduler_row', name: 'Margoria Sea Patrol', conf: null, file: 's.jpg',
      why: 'unknown scheduler row: accept adds a weekly Today row',
      value: { cadence: 'weekly', state: 'open', remaining_s: 187200 } },
    { id: 'r6', kind: 'scheduler_row', name: 'X', value: { cadence: 'monthly', state: 'open' } },
    { id: 'r5', kind: 'scheduler_row', name: 'Y', value: { cadence: 'daily', state: 'maybe' } }
  ] });
  assert.deepStrictEqual(a.review.map((r) => r.id), ['r7']);
  assert.deepStrictEqual(a.review[0].value, { cadence: 'weekly', state: 'open', remaining_s: 187200 });
  assert.strictEqual(C.ocrAutoLabel(a.review[0]),
    'unknown scheduler row Margoria Sea Patrol (weekly, open) - accept adds it to Today');
  assert.strictEqual(C.ocrFixHint('scheduler_row'), '');
});
