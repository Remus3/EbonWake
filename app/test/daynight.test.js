'use strict';
// Plan 131: the overlay night chip from GET /api/daynight, the gametime OCR
// review / applied rows and the drop card's clock / override via.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const C = require('../shared/ewcore');

const NOW = Date.parse('2026-10-15T12:00:00Z');
const at = (s) => new Date(NOW + s * 1000).toISOString().replace('.000Z', '+00:00');

test('nightChip: night counts down to the next change', () => {
  const d = { via: 'clock', night: true, next_change_utc: at(12 * 60) };
  assert.deepStrictEqual(C.nightChip(d, NOW), { text: 'night ends in 12m', cls: 'ok' });
  assert.strictEqual(C.nightChip(d, NOW + 11 * 60 * 1000 + 30000).text, 'night ends in 1m');
  assert.strictEqual(C.nightChip(d, NOW + 13 * 60 * 1000), null);  // stale until the next GET
});

test('nightChip: day shows only inside 15 minutes', () => {
  assert.strictEqual(C.nightChip({ via: 'clock', night: false, next_change_utc: at(3600) }, NOW), null);
  assert.deepStrictEqual(C.nightChip({ via: 'clock', night: false, next_change_utc: at(9 * 60) }, NOW),
    { text: 'night in 9m', cls: 'unknown' });
});

test('nightChip: typed override, uncalibrated and junk', () => {
  assert.deepStrictEqual(C.nightChip({ via: 'override', night: true, next_change_utc: null }, NOW),
    { text: 'night (typed)', cls: 'warn' });
  assert.strictEqual(C.nightChip({ via: 'override', night: false }, NOW), null);
  assert.strictEqual(C.nightChip({ via: null, night: false }, NOW), null);
  assert.strictEqual(C.nightChip({ via: 'clock', night: true, next_change_utc: 'x' }, NOW), null);
  assert.strictEqual(C.nightChip(null, NOW), null);
  assert.strictEqual(C.nightChip([], NOW), null);
});

test('gametime review and applied rows', () => {
  const a = C.normalizeOcrAuto({
    review: [{ id: 'r1', kind: 'gametime', name: 'game time', value: { game: '22:15' }, conf: 0.85 },
      { id: 'r2', kind: 'gametime', value: { game: '25:00' } }],
    commits: [],
    applied: [{ id: 'a1', kind: 'gametime', value: { game: '07:00' }, conf: 0.95 }]
  });
  assert.strictEqual(a.review.length, 1);
  assert.strictEqual(C.ocrAutoLabel(a.review[0]), 'game time 22:15 (night clock) (85%)');
  assert.strictEqual(C.ocrFixHint('gametime'), '');  // accept / discard only
  assert.strictEqual(C.ocrAppliedLabel(a.applied[0]), 'night clock set from game time 07:00 (95%)');
});

test('drop card keeps the clock / override via', () => {
  const v = C.dropView({ drops: { rate_capped: 10, cap_used: 300, rate_total: 10, wasted: 0,
    active: [{ id: 'night', name: 'Night time', via: 'clock', rate_pct: 10 },
      { id: 'luck', name: 'Luck', via: 'weird', rate_pct: 5 }], buffs: [] } });
  assert.deepStrictEqual(v.active.map((a) => a.via), ['clock', 'toggle']);
});

test('overlay wiring: the Grind row carries the night chip from /api/daynight', () => {
  const js = fs.readFileSync(path.join(__dirname, '..', 'overlay', 'overlay.js'), 'utf8');
  const html = fs.readFileSync(path.join(__dirname, '..', 'overlay', 'index.html'), 'utf8');
  assert.ok(js.indexOf("getJSON('/api/daynight')") >= 0);
  assert.ok(js.indexOf('C.nightChip(night, now)') >= 0);
  assert.ok(/id="ov-grind-row"[^\n]*id="ov-night"/.test(html));
});
