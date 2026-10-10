'use strict';
// Plan 108: the Settings fame row shows the derived value with its source and
// age; the number input is an override behind a disclosure. No DOM, no network.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const C = require('../shared/ewcore');

const read = (p) => fs.readFileSync(path.join(__dirname, '..', p), 'utf8');

test('fame row: derived value, source and age', () => {
  assert.deepStrictEqual(C.derivedSettingLine('market.fame_pct',
    { value: 1.25, source: 'ocr', age_s: 2 * 86400, stale: false }),
  { text: 'Family fame bonus: 1.25 % (from screenshot, 2d ago)', stale: false, override: false });
  const p = C.derivedSettingLine('market.fame_pct',
    { value: 1, source: 'profile', age_s: 3600, stale: false, note: 'estimated from profile fame' });
  assert.strictEqual(p.text, 'Family fame bonus: 1 % (from profile, 1h ago - estimated from profile fame)');
  const t = C.derivedSettingLine('market.fame_pct', { value: 0.5, source: 'typed', age_s: null });
  assert.strictEqual(t.text, 'Family fame bonus: 0.5 % (typed)');
  assert.strictEqual(t.override, true);
  assert.strictEqual(C.derivedSettingLine('market.fame_pct', { value: 0, source: 'default' }).text,
    'Family fame bonus: 0 % (no screenshot read yet)');
  assert.strictEqual(C.derivedSettingLine('market.fame_pct', null).text, 'Family fame bonus: -');
  assert.strictEqual(C.derivedSettingLine('ui.theme', { value: 'dark', source: 'ocr' }), null);
});

test('fame row: the input sits behind the override disclosure, clear returns to derived', () => {
  const f = C.SETTINGS_FIELDS['market.fame_pct'];
  assert.strictEqual(f.derived, 'Family fame bonus');
  assert.strictEqual(f.type, 'number');
  assert.ok(C.validSettingsBody({ clear: 'market.fame_pct' }));
  const js = read('dashboard/settings.js');
  assert.match(js, /f\.derived \? derivedField\(f\) : field\(f\)/);
  assert.match(js, /el\('details', 'ew-soverride'\)[\s\S]*det\.appendChild\(field\(f\)\)/);
  assert.match(js, /post\('\/api\/settings', \{ clear: key \}\)/);
});
