'use strict';
// Plan 110 slice 2: the Leveling card's Zones table from GET /api/zones/xp
// (plan 088). zonesRows is the pure formatter; the static guards pin the
// fetch and the details table in leveling.js. No network, no DOM.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const C = require('../shared/ewcore');

const read = (p) => fs.readFileSync(path.join(__dirname, '..', p), 'utf8');
const NOW = Date.parse('2026-10-10T12:00:00Z');

const zone = (o) => Object.assign({ key: 'gyfin', zone_name: 'Gyfin Rhasia Temple', recommended_level: 62,
  read_at: '2026-10-07T12:00:00+00:00', current: true, reread_level: null, cap_bound: false,
  effective_pct: 0.0125, kills_to_level: 1830, next_level: 63, monsters: [] }, o);

test('zonesRows: sorted by recommended level (none last), then name', () => {
  const v = C.zonesRows({ zones: [zone({ zone_name: 'B', recommended_level: 62 }),
    zone({ zone_name: 'No level', recommended_level: null }),
    zone({ zone_name: 'A', recommended_level: 62 }), zone({ zone_name: 'Low', recommended_level: 56 })] }, NOW);
  assert.deepStrictEqual(v.rows.map((r) => r.name), ['Low', 'A', 'B', 'No level']);
  assert.strictEqual(v.rows[0].level, 'Lv 56');
  assert.strictEqual(v.rows[3].level, '-');
  assert.strictEqual(v.error, false);
});

test('zonesRows: EXP per kill, kills-to-level text and read age', () => {
  const r = C.zonesRows({ zones: [zone()] }, NOW).rows[0];
  assert.strictEqual(r.exp, '0.0125%/kill');
  assert.strictEqual(r.kills, '~1,830 kills to Lv 63');
  assert.strictEqual(r.age, '3d ago');
  assert.strictEqual(r.current, true);
  const old = C.zonesRows({ zones: [zone({ current: false, reread_level: 63, effective_pct: null,
    kills_to_level: null, read_at: 'junk' })] }, NOW).rows[0];
  assert.strictEqual(old.exp, '-');
  assert.strictEqual(old.kills, 're-read at Lv 63');
  assert.strictEqual(old.age, '-');
  assert.strictEqual(old.current, false);
});

test('zonesRows: cap-bound badge only when the server says so', () => {
  const rows = C.zonesRows({ zones: [zone({ cap_bound: true }), zone({ zone_name: 'x', cap_bound: 'yes' })] }, NOW).rows;
  assert.strictEqual(rows.find((r) => r.name === 'Gyfin Rhasia Temple').cap, 'cap-bound');
  assert.strictEqual(rows.find((r) => r.name === 'x').cap, '');
});

test('zonesRows: empty state, junk rows dropped, bad body is an error', () => {
  const e = C.zonesRows({ zones: [] }, NOW);
  assert.deepStrictEqual(e.rows, []);
  assert.strictEqual(e.empty, 'Take a screenshot of a Monster Zone Info panel to fill this');
  assert.strictEqual(e.empty, C.ZONES_EMPTY);
  assert.strictEqual(C.zonesRows({ zones: [null, zone({ zone_name: '' }), zone({ zone_name: 7 }), zone()] }, NOW).rows.length, 1);
  const bad = C.zonesRows(null, NOW);
  assert.strictEqual(bad.error, true);
  assert.deepStrictEqual(bad.rows, []);
  assert.strictEqual(C.zonesRows({ zones: 'x' }, NOW).error, true);
});

test('leveling.js: Zones details table reads /api/zones/xp, safe DOM', () => {
  const src = read('dashboard/leveling.js');
  assert.ok(src.includes("getJSON('/api/zones/xp')"));
  assert.ok(src.includes('C.zonesRows('));
  assert.ok(/el\('details', 'ew-ldet'\)[\s\S]{0,200}Zones/.test(src));
  assert.ok(!/innerHTML/.test(src));
});
