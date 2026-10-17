'use strict';
// Plan 110 slice 4: every GET route the server builds has a consumer in app/
// JS (a quoted '/api/...' literal outside app/test), or is named below with
// the reason it has none. A finished feature is then visible with no manual
// step. Python side: nothing new; this reads server/ew/app.py as text.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const APP = path.join(__dirname, '..');
const SERVER_APP = path.join(APP, '..', 'server', 'ew', 'app.py');

// route -> why no app/ JS reads it. Keep it short; an entry here is a debt.
const ALLOW = {};

function getRoutes() {
  const src = fs.readFileSync(SERVER_APP, 'utf8');
  const body = src.slice(src.indexOf('def do_GET('));
  const end = body.search(/\n    def /);
  const get = end > 0 ? body.slice(0, end) : body;
  const out = [];
  const re = /if path == "(\/api\/[a-z0-9_/-]+)"/g;
  let m;
  while ((m = re.exec(get)) !== null) out.push(m[1]);
  return out;
}

function appSources() {
  const out = [];
  (function walk(dir) {
    fs.readdirSync(dir, { withFileTypes: true }).forEach(function (d) {
      const p = path.join(dir, d.name);
      if (d.isDirectory()) {
        if (d.name !== 'node_modules' && d.name !== 'test') walk(p);
      } else if (/\.(js|html)$/.test(d.name)) {
        out.push(fs.readFileSync(p, 'utf8'));
      }
    });
  })(APP);
  return out.join('\n');
}

// A quoted literal: the route followed by its closing quote or a query.
function consumed(src, route) {
  const esc = route.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&');
  return new RegExp('[\'"`]' + esc + '[\'"`?]').test(src);
}

test('the GET route scan finds the server routes', () => {
  const routes = getRoutes();
  assert.ok(routes.length >= 30, 'found ' + routes.length);
  ['/api/health', '/api/events/currency', '/api/zones/xp', '/api/data/verdicts', '/api/loop'].forEach(function (r) {
    assert.ok(routes.indexOf(r) >= 0, r);
  });
});

test('every GET route has an app/ consumer or an allowlist reason', () => {
  const src = appSources();
  const missing = getRoutes().filter(function (r) { return !consumed(src, r) && !ALLOW[r]; });
  assert.deepStrictEqual(missing, [], 'GET routes with no dashboard / overlay consumer');
});

test('the allowlist carries reasons and no stale entries', () => {
  const routes = getRoutes();
  const src = appSources();
  Object.keys(ALLOW).forEach(function (r) {
    assert.ok(typeof ALLOW[r] === 'string' && ALLOW[r].length >= 10, r + ' needs a reason');
    assert.ok(routes.indexOf(r) >= 0, r + ' is no longer a GET route');
    assert.ok(!consumed(src, r), r + ' is consumed now; drop it from the allowlist');
  });
});

test('consumed(): a quoted literal counts, a comment mention or prefix does not', () => {
  assert.ok(consumed("getJSON('/api/zones/xp')", '/api/zones/xp'));
  assert.ok(consumed("'/api/market/search?q=' + q", '/api/market/search'));
  assert.ok(!consumed('reads /api/zones/xp here', '/api/zones/xp'));
  assert.ok(!consumed("'/api/progress/history'", '/api/progress'));
});
