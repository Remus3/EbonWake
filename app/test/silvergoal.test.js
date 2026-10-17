'use strict';
// Plan 140: the Grind tab "This week" card's pure render helpers
// (app/dashboard/silvergoal.js) and their wiring into grind.js / index.html.
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const G = require('../dashboard/silvergoal.js');

const APP = path.join(__dirname, '..');
const read = (p) => fs.readFileSync(path.join(APP, p), 'utf8');

const VIEW = {
  hidden: false, earned: 120000000, goal: 300000000, goal_source: 'history', running: true,
  week: { start: '2026-10-15T00:00:00+00:00', end: '2026-10-22T00:00:00+00:00' },
  pace: { days_left: 5, needed_per_day: 36000000, rate_per_day: 20000000,
    projection: 210000000, on_track: false }
};

test('silver: K / M / B with one decimal; small numbers as is', () => {
  assert.strictEqual(G.silver(950), '950');
  assert.strictEqual(G.silver(1500), '1.5K');
  assert.strictEqual(G.silver(36000000), '36.0M');
  assert.strictEqual(G.silver(1234567890), '1.2B');
  assert.strictEqual(G.silver(null), '?');
});

test('card: bar, needed per day, projection, behind', () => {
  const c = G.card(VIEW);
  assert.strictEqual(c.earned, '120.0M / 300.0M');
  assert.strictEqual(c.pct, 40);
  assert.strictEqual(c.bar, '40%');
  assert.strictEqual(c.needed, 'need 36.0M/day for 5 days');
  assert.strictEqual(c.projection, 'on pace for 210.0M (20.0M/day, last 7 days)');
  assert.strictEqual(c.cls, 'warn');
  assert.strictEqual(c.pill, 'behind');
  assert.strictEqual(c.source, 'median of the last full weeks + 10%');
});

test('card: on track, goal met, typed goal, one day', () => {
  const on = G.card(Object.assign({}, VIEW, { goal_source: 'override',
    pace: Object.assign({}, VIEW.pace, { on_track: true, days_left: 1 }) }));
  assert.strictEqual(on.pill, 'on track');
  assert.strictEqual(on.cls, 'ok');
  assert.strictEqual(on.needed, 'need 36.0M/day for 1 day');
  assert.strictEqual(on.source, 'typed goal, until the weekly reset');
  const met = G.card(Object.assign({}, VIEW, { earned: 400000000 }));
  assert.strictEqual(met.pct, 100);
  assert.strictEqual(met.needed, 'goal met');
  assert.strictEqual(met.pill, 'goal met');
  assert.strictEqual(met.cls, 'ok');
});

test('card: hidden or malformed -> null', () => {
  assert.strictEqual(G.card(null), null);
  assert.strictEqual(G.card({ hidden: true, goal: null }), null);
  assert.strictEqual(G.card(Object.assign({}, VIEW, { goal: 0 })), null);
  assert.strictEqual(G.card(Object.assign({}, VIEW, { earned: 'x' })), null);
  const nopace = G.card(Object.assign({}, VIEW, { pace: null }));
  assert.strictEqual(nopace.projection, '');
  assert.strictEqual(nopace.needed, '');
  assert.strictEqual(nopace.pill, 'behind');
});

test('goalBody: digits, suffixes, blank clears, bad input errors', () => {
  assert.deepStrictEqual(G.goalBody('300M'), { body: { week_goal: 300000000 } });
  assert.deepStrictEqual(G.goalBody('1.2b'), { body: { week_goal: 1200000000 } });
  assert.deepStrictEqual(G.goalBody('250,000,000'), { body: { week_goal: 250000000 } });
  assert.deepStrictEqual(G.goalBody(' 5k '), { body: { week_goal: 5000 } });
  assert.deepStrictEqual(G.goalBody(''), { body: { week_goal: null } });
  assert.deepStrictEqual(G.goalBody(null), { body: { week_goal: null } });
  assert.ok(G.goalBody('-5').error);
  assert.ok(G.goalBody('lots').error);
  assert.ok(G.goalBody('0').error);
  assert.ok(G.goalBody('99999T').error);
});

test('wiring: index.html loads silvergoal.js before grind.js; grind.js reads the route', () => {
  const html = read('dashboard/index.html');
  const a = html.indexOf('<script src="silvergoal.js"></script>');
  assert.ok(a > 0 && a < html.indexOf('<script src="grind.js"></script>'));
  const g = read('dashboard/grind.js');
  assert.ok(g.includes("'/api/silvergoal'"));
  assert.ok(g.includes('EWSilverGoal'));
  assert.ok(g.includes("card('This week')"));
  assert.ok(g.includes('week_goal'));
});
