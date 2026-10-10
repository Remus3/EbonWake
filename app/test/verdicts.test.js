'use strict';
// Plan 110 slice 3: the System Signal health card's "Data checks" list from
// GET /api/data/verdicts (plan 085). verdictRows is the pure formatter; the
// static guards pin the fetch and the details list in dashboard.js.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const C = require('../shared/ewcore');

const read = (p) => fs.readFileSync(path.join(__dirname, '..', p), 'utf8');
const URL = 'https://www.naeu.playblackdesert.com/en-US/News/Detail?groupContentNo=9001';

const body = (o) => Object.assign({
  verdicts: {
    'bosses.kzarka': { verdict: 'confirmed', evidence: 'Kzarka 23:00 listed', notice_no: 9001, url: URL,
      date: '2026-10-08', checked_at: '2026-10-09T00:00:00+00:00' },
    'events.seals': { verdict: 'contradicted', evidence: 'notice says 80 seals, row has 60', notice_no: 9001,
      url: URL, date: '2026-10-08', checked_at: '2026-10-09T00:00:00+00:00' },
    'leveling.cap': { verdict: 'silent', evidence: '', notice_no: null, url: null, date: null, checked_at: null },
    'a.first': { verdict: 'confirmed', evidence: 'ok', notice_no: 9001, url: 'http://evil.example/x',
      date: '2026-10-08', checked_at: '2026-10-09T00:00:00+00:00' }
  },
  unchecked: ['grind.loot', 'pets.tiers', 'mounts.odds'],
  last_notice: { notice_no: 9001, title: 'Patch Notes - Oct 8', url: URL, date: '2026-10-08' },
  error: null
}, o);

test('verdictRows: contradicted first, silent dropped, confirmed after (key order)', () => {
  const v = C.verdictRows(body());
  assert.deepStrictEqual(v.rows.map((r) => r.key), ['events.seals', 'a.first', 'bosses.kzarka']);
  assert.strictEqual(v.rows[0].cls, 'bad');
  assert.strictEqual(v.rows[0].pill, 'contradicted');
  assert.strictEqual(v.rows[0].text, 'events.seals: notice says 80 seals, row has 60 (2026-10-08)');
  assert.strictEqual(v.rows[1].cls, 'ok');
  assert.strictEqual(v.error, null);
});

test('verdictRows: patch-notes link only for an allowlisted https host', () => {
  const v = C.verdictRows(body());
  assert.strictEqual(v.rows[0].url, URL);
  assert.strictEqual(v.rows[0].link, 'patch notes');
  assert.strictEqual(v.rows.find((r) => r.key === 'a.first').url, null);
});

test('verdictRows: counts line and last notice line', () => {
  const v = C.verdictRows(body());
  assert.strictEqual(v.counts, '1 contradicted, 2 confirmed, 3 unchecked');
  assert.strictEqual(v.last, 'last patch notes read: 2026-10-08 - Patch Notes - Oct 8');
  assert.strictEqual(C.verdictRows(body({ last_notice: null })).last, 'no patch notes read yet');
  assert.strictEqual(C.verdictRows(body({ verdicts: {}, unchecked: [] })).counts, '0 contradicted, 0 confirmed, 0 unchecked');
});

test('verdictRows: error states', () => {
  const e = C.verdictRows(body({ error: 'hint file bad' }));
  assert.strictEqual(e.error, 'data hints unreadable: hint file bad');
  const bad = C.verdictRows(null);
  assert.strictEqual(bad.error, 'data checks unavailable');
  assert.deepStrictEqual(bad.rows, []);
  assert.strictEqual(C.verdictRows({ verdicts: [], unchecked: 'x' }).error, 'data checks unavailable');
  const junk = C.verdictRows(body({ verdicts: { x: null, y: { verdict: 'maybe' } } }));
  assert.deepStrictEqual(junk.rows, []);
});

test('dashboard.js: Data checks details on Signal health, read from /api/data/verdicts, safe DOM', () => {
  const src = read('dashboard/dashboard.js');
  assert.ok(src.includes("getJSON('/api/data/verdicts')"));
  assert.ok(src.includes('C.verdictRows('));
  assert.ok(src.includes("'sys-verdicts'"));
  assert.ok(/el\('summary'[^)]*'Data checks/.test(src));
  assert.ok(src.includes('EWToast.linkButton('));
  assert.ok(!/innerHTML/.test(src));
});
