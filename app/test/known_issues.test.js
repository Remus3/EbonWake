'use strict';
// Plan 130: known-issue chips. knownIssueChips is the pure formatter over
// GET /api/known-issues?area=; the static guards pin that the Leveling,
// Deadeye (enhancement plan) and Market cards read their area and render it,
// and that a suspect XP sample is greyed. No network, no DOM.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const C = require('../shared/ewcore');

const APP = path.join(__dirname, '..');
const read = (p) => fs.readFileSync(path.join(APP, p), 'utf8');

function row(o) {
  return Object.assign({ id: 'x', title: 'Lv 59 at 99.99% cannot level from quest EXP', affects: ['leveling'],
    from: '2026-10-08T00:00:00+00:00', until: null, source: 'NA/EU Known Issues notice 184, read 2026-10-14',
    verified: true, kind: 'defect', state: 'active' }, o);
}

test('knownIssueChips: defect chip text, class and hover title', () => {
  const v = C.knownIssueChips({ area: 'leveling', issues: [row({ note: 'only Lv 59 samples' })], error: null }, 'leveling');
  assert.strictEqual(v.error, null);
  assert.strictEqual(v.chips.length, 1);
  const c = v.chips[0];
  assert.strictEqual(c.text, 'known issue: Lv 59 at 99.99% cannot level from quest EXP');
  assert.match(c.cls, /ew-pill warn/);
  assert.match(c.title, /only Lv 59 samples/);
  assert.match(c.title, /notice 184/);
  assert.match(c.title, /from 2026-10-08, no end date yet/);
});

test('knownIssueChips: a change flips from pending to applied', () => {
  const agris = { id: 'agris', title: 'Agris Fever cost change', affects: ['enhance'], kind: 'change',
    from: '2026-10-15T00:00:00+00:00', until: '2026-10-29T00:00:00+00:00' };
  const p = C.knownIssueChips({ issues: [row(Object.assign({ state: 'pending' }, agris))] }, 'enhance').chips[0];
  assert.strictEqual(p.text, 'pending: Agris Fever cost change (2026-10-15)');
  assert.match(p.cls, /unknown/);
  const a = C.knownIssueChips({ issues: [row(Object.assign({ state: 'applied' }, agris))] }, 'enhance').chips[0];
  assert.strictEqual(a.text, 'applied: Agris Fever cost change');
  assert.match(a.cls, /ok/);
  assert.match(a.title, /until 2026-10-29/);
});

test('knownIssueChips: area filter, junk rows dropped, unverified marked', () => {
  const d = { issues: [row({ id: 'a' }), row({ id: 'm', affects: ['market'] }), null, 5,
    row({ id: 'e', state: 'ended' }), row({ id: 't', title: '' }), row({ id: 'u', verified: false })] };
  assert.deepStrictEqual(C.knownIssueChips(d, 'leveling').chips.map((c) => c.id), ['a', 'u']);
  assert.deepStrictEqual(C.knownIssueChips(d, 'market').chips.map((c) => c.id), ['m']);
  assert.deepStrictEqual(C.knownIssueChips(d).chips.map((c) => c.id), ['a', 'm', 'u']);
  assert.match(C.knownIssueChips(d, 'leveling').chips[1].title, /\(unverified\)/);
});

test('knownIssueChips: error states', () => {
  for (const bad of [null, [], 'x', { issues: 'x' }]) {
    const v = C.knownIssueChips(bad, 'leveling');
    assert.deepStrictEqual(v.chips, []);
    assert.strictEqual(v.error, 'known issues unavailable');
  }
  assert.match(C.knownIssueChips({ issues: [], error: 'bad row' }).error, /unreadable: bad row/);
});

test('cards read their area and render the chips', () => {
  const cards = { 'dashboard/leveling.js': 'leveling', 'dashboard/deadeye.js': 'enhance', 'dashboard/market.js': 'market' };
  for (const [file, area] of Object.entries(cards)) {
    const src = read(file);
    assert.ok(src.includes("'/api/known-issues?area=" + area + "'"), file);
    assert.ok(src.includes("C.knownIssueChips(S.issues, '" + area + "')"), file);
    assert.ok(src.includes("'ew-kissues'"), file);
  }
});

test('a suspect sample is greyed and labelled on the Leveling card', () => {
  const src = read('dashboard/leveling.js');
  assert.match(src, /s\.suspect/);
  assert.match(src, /'suspect'/);
  assert.match(read('shared/ew.css'), /\.ew-kissues \{/);
});
