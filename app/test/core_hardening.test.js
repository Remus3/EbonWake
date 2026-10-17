'use strict';
// Plan 147 hardening audit of app/shared/core/*.part.js: regressions for the
// findings in docs/audit/20261017-app-core.md. Each test failed before its fix.
const test = require('node:test');
const assert = require('node:assert');
const C = require('../shared/ewcore');

// Names an operator can type (a buff, a Today item) or OCR can read that are
// also Object.prototype members: a lookup in a plain {} sees them as present.
const PROTO_NAMES = ['constructor', 'toString', 'valueOf', 'hasOwnProperty', '__proto__'];

// ---- fake DOM: just what reconcile touches (as bus.test.js) ----
class Node {
  constructor(name) { this.name = name; this.parentNode = null; this.children = []; }
  insertBefore(n, ref) {
    if (n.parentNode) n.parentNode.removeChild(n);
    const i = ref ? this.children.indexOf(ref) : -1;
    if (i < 0) this.children.push(n); else this.children.splice(i, 0, n);
    n.parentNode = this;
    return n;
  }
  appendChild(n) { return this.insertBefore(n, null); }
  removeChild(n) {
    const i = this.children.indexOf(n);
    if (i >= 0) this.children.splice(i, 1);
    n.parentNode = null;
    return n;
  }
}

test('APP-CORE-01: reconcile renders a row whose key is an Object.prototype name', () => {
  // grind.js keys the buff list by the lowercased buff name the operator typed.
  const c = new Node('list');
  const rows = ['xp scroll'].concat(PROTO_NAMES).map((k) => ({ id: k }));
  const render = (r) => new Node(r.id);
  C.reconcile(c, rows, (r) => r.id, render);
  assert.deepStrictEqual(c.children.map((n) => n.name), rows.map((r) => r.id));
  // A second pass keeps every node (identity), none rebuilt.
  const before = c.children.slice();
  const out = C.reconcile(c, rows, (r) => r.id, render);
  assert.deepStrictEqual(out, { added: 0, updated: 0, moved: 0, removed: 0 });
  before.forEach((n, i) => assert.strictEqual(c.children[i], n));
});

test('APP-CORE-02: an OCR loot row named like an Object.prototype member is reported, not filled', () => {
  const rows = PROTO_NAMES.map((n) => ({ name: n, count: 5, confidence: 1 }))
    .concat([{ name: 'gorgath tooth', count: 3, confidence: 1 }]);
  const imp = C.lootImportCounts(rows, ['Gorgath Tooth']);
  assert.deepStrictEqual(imp.counts, { 'Gorgath Tooth': '3' });
  assert.strictEqual(imp.filled, 1);
  assert.deepStrictEqual(imp.missing, PROTO_NAMES);
  // A spot item really named so still fills.
  const own = C.lootImportCounts([{ name: 'Constructor', count: 2, confidence: 1 }], ['constructor']);
  assert.deepStrictEqual(own.counts, { constructor: '2' });
  assert.strictEqual(own.filled, 1);
});

test('APP-CORE-03: a claim window whose notice title is an Object.prototype name is listed', () => {
  const now = Date.UTC(2026, 9, 17, 12);
  const until = '2026-10-20T00:00:00Z';
  const items = PROTO_NAMES.map((t, i) => ({ id: 'e' + (i + 1), title: t, kind: 'event', claim_until: until }));
  const rows = C.claimRows(items, now, now);
  assert.deepStrictEqual(rows.map((r) => r.title), PROTO_NAMES);
  // One per notice still holds for a real duplicate.
  const dup = C.claimRows(items.concat([{ id: 'e9', title: 'toString', kind: 'event', claim_until: until }]), now, now);
  assert.strictEqual(dup.length, PROTO_NAMES.length);
});

test('APP-CORE-04: the palette tells apart two Today items titled like an Object.prototype name', () => {
  // Names are counted lowercased, so the lowercase member `constructor` is the trap.
  const cat = { today: { items: [
    { id: 'a', title: 'Constructor', kind: 'daily' },
    { id: 'b', title: 'Constructor', kind: 'daily' }
  ] } };
  const r = C.parseCommand('tick constructor (b)', cat);
  assert.strictEqual(r.ok, true, JSON.stringify(r));
  assert.deepStrictEqual(r.body, { tick: 'b' });
  const s = C.paletteSuggest('tick constr', cat).map((x) => x.text);
  assert.deepStrictEqual(s, ['tick Constructor (a)', 'tick Constructor (b)']);
});
