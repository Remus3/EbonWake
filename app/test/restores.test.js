'use strict';
// Plan 158: restorePill (ewcore.js) turns the signals digest `restores`
// section into the Home `restored <domain> from last-good` pill. Static guard
// on the Home wiring. No network, no DOM.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const C = require('../shared/ewcore');

const APP = path.join(__dirname, '..');
const read = (p) => fs.readFileSync(path.join(APP, p), 'utf8');

test('restorePill: one line per restore, null when none', () => {
  assert.strictEqual(C.restorePill(null), null);
  assert.strictEqual(C.restorePill({ rows: [] }), null);
  assert.strictEqual(C.restorePill({ restores: { count: 0, items: [] } }), null);
  assert.strictEqual(C.restorePill({ restores: { items: ['junk', { domain: 5 }] } }), null);
  const one = C.restorePill({ restores: { count: 1, items: [{ domain: 'notes', source: 'good' }] } });
  assert.strictEqual(one.text, 'restored notes from last-good');
  assert.strictEqual(one.tab, 'system');
  assert.match(one.cls, /warn/);
  const two = C.restorePill({ restores: { items: [{ domain: 'notes' }, { domain: 'grind' }] } });
  assert.strictEqual(two.text, '2 docs restored from last-good');
  assert.strictEqual(two.title, 'restored notes from last-good\nrestored grind from last-good');
});

test('wiring: Home reads the digest restores section', () => {
  assert.match(read('dashboard/home.js'), /C\.restorePill\(S\.snap\.signals\)/);
});
