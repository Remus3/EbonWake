'use strict';
// Plan 169: Reward Seal ledger helpers (ewcore.js) over GET /api/imperial
// `seals`, the /api/imperial bridge guard for the seal ops, and a static
// guard on the Imperial card. No network, no DOM.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const C = require('../shared/ewcore');

const APP = path.join(__dirname, '..');
const read = (p) => fs.readFileSync(path.join(APP, p), 'utf8');

function view(o) {
  return { seals: Object.assign({
    categories: [
      { id: 'cooking', name: 'Cooking', count: 12 },
      { id: 'fishing', name: 'Fishing', count: null },
      { id: 'mining', name: 'Mining', count: 3 }
    ],
    totals: { total: 12, known: 1, unknown: ['fishing'] },
    exchange: [
      { id: 'cooking-box-a', category: 'cooking', item: 'Box A', cost: 10, afford: true, times: 1, short: 0 },
      { id: 'cooking-big', category: 'cooking', item: 'Big', cost: 15, afford: false, times: 0, short: 3 }
    ],
    nearest: { cooking: { ready: 'cooking-box-a', next: 'cooking-big' }, fishing: { ready: null, next: null } },
    golden: { date: '2026-12-03', held: 4, warn: true, passed: false, rate_text: 'conversion rate not announced',
      text: '4 Golden Seals convert to Reward Seals at the 2026-12-03 maintenance - conversion rate not announced; spend or plan them before' }
  }, o || {}) };
}

test('sealRows: held, ready and next per category; untyped says so; unknown category dropped', () => {
  const r = C.sealRows(view());
  assert.deepStrictEqual(r.map((x) => [x.id, x.text]), [
    ['cooking', '12 held - ready: Box A (10) - next: Big needs 3 more'],
    ['fishing', 'count not typed']]);
  assert.deepStrictEqual(C.sealRows({}), []);
  assert.deepStrictEqual(C.sealRows({ seals: null }), []);
});

test('sealGolden: warning line carries the unknown-rate wording; null without data', () => {
  const g = C.sealGolden(view());
  assert.strictEqual(g.warn, true);
  assert.strictEqual(g.cls, 'ew-err');
  assert.match(g.text, /conversion rate not announced/);
  assert.match(g.text, /2026-12-03/);
  const calm = C.sealGolden(view({ golden: { text: 'Golden Seals converted at the 2026-12-03 maintenance', warn: false } }));
  assert.strictEqual(calm.cls, 'ew-muted');
  assert.strictEqual(C.sealGolden(view({ golden: null })), null);
});

test('parseSealCount / parseSealExchange bodies pass the bridge guard', () => {
  const a = C.parseSealCount('cooking', '1,200');
  assert.deepStrictEqual(a.body, { seal_count: { category: 'cooking', count: 1200 } });
  assert.ok(C.validPost('/api/imperial', a.body));
  assert.deepStrictEqual(C.parseSealCount('golden', ' ').body, { seal_count: { category: 'golden', count: null } });
  assert.strictEqual(C.parseSealCount('mining', '3').ok, false);
  assert.strictEqual(C.parseSealCount('cooking', '-3').ok, false);
  const e = C.parseSealExchange({ category: 'alchemy', item: ' Elixir box ', cost: '25' });
  assert.deepStrictEqual(e.body, { seal_ex_add: { category: 'alchemy', item: 'Elixir box', cost: 25 } });
  assert.ok(C.validPost('/api/imperial', e.body));
  assert.strictEqual(C.parseSealExchange({ category: 'alchemy', item: 'x', cost: '0' }).ok, false);
  assert.strictEqual(C.parseSealExchange({ category: 'alchemy', item: '', cost: '5' }).ok, false);
});

test('validImperialBody: seal ops bounded like the server', () => {
  const ok = [{ seal_count: { category: 'work-supervisor', count: 0 } },
    { seal_count: { category: 'golden', count: null } },
    { seal_ex_add: { category: 'fishing', item: 'Rod', cost: 5 } },
    { seal_ex_del: 'fishing-rod' }];
  ok.forEach((b) => assert.ok(C.validImperialBody(b), JSON.stringify(b)));
  const bad = [{ seal_count: { category: 'mining', count: 1 } },
    { seal_count: { category: 'cooking', count: 1000001 } },
    { seal_count: { category: 'cooking' } },
    { seal_ex_add: { category: 'golden', item: 'x', cost: 5 } },
    { seal_ex_add: { category: 'fishing', item: 'x', cost: 0 } },
    { seal_ex_del: 'mining-x' }];
  bad.forEach((b) => assert.ok(!C.validImperialBody(b), JSON.stringify(b)));
  assert.deepStrictEqual(C.SEAL_CATS, ['cooking', 'fishing', 'subjugation', 'training', 'work-supervisor', 'alchemy']);
});

test('the Imperial card renders the seal section via textContent only', () => {
  const src = read('dashboard/imperial.js');
  assert.match(src, /C\.sealRows\(S\.data\)/);
  assert.match(src, /C\.sealGolden\(S\.data\)/);
  assert.doesNotMatch(src, /innerHTML/);
});
