'use strict';
// Plan 118: enhancement window OCR kinds (enh_fs / enh_crons / enh_agris) in
// the OCR card (labels, fix bodies) and the Stacks card "(OCR)" tags. No network, no DOM.
const test = require('node:test');
const assert = require('node:assert');
const C = require('../shared/ewcore');

function auto(rows) {
  return C.normalizeOcrAuto({ review: rows, commits: [], applied: [] });
}

test('OCR kinds: enhancement reads normalise and label', () => {
  const a = auto([
    { id: 'r1', kind: 'enh_fs', name: 'fs', value: 45, conf: 0.97, why: 'failstack label' },
    { id: 'r2', kind: 'enh_crons', name: 'crons', value: 1234, conf: 0.97, why: '' },
    { id: 'r3', kind: 'enh_agris', name: 'sovereign TET',
      value: { family: 'sovereign', step: 'TET', stacks: 3 }, conf: 0.5, why: '' },
    { id: 'r4', kind: 'enh_agris', name: 'x', value: { family: 'Bad!', step: 'TET', stacks: 3 } },
    { id: 'r5', kind: 'enh_agris', name: 'x', value: { family: 'sovereign', step: 'TET', stacks: 1001 } }
  ]);
  assert.deepStrictEqual(a.review.map((r) => r.id), ['r1', 'r2', 'r3']);
  assert.strictEqual(C.ocrAutoLabel(a.review[0]), 'failstack +45 (97%)');
  assert.strictEqual(C.ocrAutoLabel(a.review[1]), 'crons 1,234 (97%)');
  assert.strictEqual(C.ocrAutoLabel(a.review[2]), 'Agris sovereign TET: 3 stacks (50%)');
});

test('OCR fix: enhancement hints and bounded bodies', () => {
  assert.strictEqual(C.ocrFixHint('enh_fs'), 'failstack 0-999');
  assert.strictEqual(C.ocrFixHint('enh_crons'), 'crons owned');
  assert.strictEqual(C.ocrFixHint('enh_agris'), 'Agris stacks');
  assert.deepStrictEqual(C.ocrFixBody('r1', 'enh_fs', '45'),
    { review: { id: 'r1', action: 'fix', value: 45 } });
  assert.strictEqual(C.ocrFixBody('r1', 'enh_fs', '1000'), null);
  assert.deepStrictEqual(C.ocrFixBody('r2', 'enh_crons', '1,234'),
    { review: { id: 'r2', action: 'fix', value: 1234 } });
  assert.deepStrictEqual(C.ocrFixBody('r3', 'enh_agris', '4'),
    { review: { id: 'r3', action: 'fix', value: 4 } });
  assert.strictEqual(C.ocrFixBody('r3', 'enh_agris', '1001'), null);
});

test('fmtStacks: OCR tags, failstack now, EV default', () => {
  const f = C.fmtStacks({
    agris: [{ family: 'sovereign', step: 'TET', stacks: 3, threshold: 20, fails_to_guarantee: 17,
      source: 'ocr:enh.png', read_at: '2026-10-10T12:00:00+00:00' },
    { family: 'kharazad', step: 'PRI', stacks: 1, threshold: 3, fails_to_guarantee: 2 }],
    fs_now: { value: 45, at: '2026-10-10T12:00:00+00:00', source: 'ocr:enh.png' },
    reads: { crons: { source: 'ocr:enh.png', read_at: '2026-10-10T12:00:00+00:00' } },
    budget: { needed: 0, owned: 1234, gap: 0, weeks: 0, unknown: [] }
  });
  assert.strictEqual(f.agris[0].text, 'sovereign TET: 3 stacks, guaranteed in 17 fails (OCR)');
  assert.strictEqual(f.agris[1].text, 'kharazad PRI: 1 stacks, guaranteed in 2 fails');
  assert.strictEqual(f.fsNow, 'failstack now +45 (OCR)');
  assert.strictEqual(f.fsNowValue, 45);
  assert.strictEqual(f.budget, 'crons 1,234 owned (OCR) / 0 expected, covered');
  const none = C.fmtStacks({ fs_now: null, reads: { crons: null } });
  assert.strictEqual(none.fsNow, '');
  assert.strictEqual(none.fsNowValue, null);
  assert.strictEqual(C.fmtStacks({ fs_now: { value: 1000 } }).fsNowValue, null);
});
