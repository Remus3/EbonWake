/* EW weekly silver goal (plan 140): pure render helpers for GET
   /api/silvergoal. The Grind tab's "This week" card (grind.js) reads these:
   an earned / goal bar, the silver needed per remaining day and the
   projection at the trailing 7-day rate. The card hides itself while the
   server has no goal (no typed goal, no full week of history). Loaded as a
   plain script (window.EWSilverGoal) and by node --test via require(). No DOM
   here: callers build nodes with DOM APIs. */
(function (root) {
  'use strict';

  const UNITS = [[1e9, 'B'], [1e6, 'M'], [1e3, 'K']];
  const GOAL_MAX = 1e13; // = grind.MAX_SILVER
  const SOURCE_TEXT = {
    override: 'typed goal, until the weekly reset',
    history: 'median of the last full weeks + 10%'
  };

  function isNum(v) { return typeof v === 'number' && isFinite(v); }

  // 1234567 -> '1.2M'; under 1000 as is.
  function silver(n) {
    if (!isNum(n)) return '?';
    const a = Math.abs(n);
    for (let i = 0; i < UNITS.length; i++) {
      if (a >= UNITS[i][0]) return (n / UNITS[i][0]).toFixed(1) + UNITS[i][1];
    }
    return String(Math.round(n));
  }

  // The card body, or null while hidden / malformed:
  // {earned, goal, pct, bar, source, needed, projection, cls, pill}.
  function card(doc) {
    if (!doc || typeof doc !== 'object' || doc.hidden !== false) return null;
    if (!isNum(doc.goal) || doc.goal <= 0 || !isNum(doc.earned)) return null;
    const p = doc.pace && typeof doc.pace === 'object' ? doc.pace : {};
    const pct = Math.max(0, Math.min(100, Math.floor(doc.earned * 100 / doc.goal)));
    const met = doc.earned >= doc.goal;
    let needed = met ? 'goal met' : '';
    if (!met && isNum(p.needed_per_day) && isNum(p.days_left)) {
      needed = 'need ' + silver(p.needed_per_day) + '/day for ' + p.days_left +
        (p.days_left === 1 ? ' day' : ' days');
    }
    let projection = '';
    if (isNum(p.projection)) {
      projection = 'on pace for ' + silver(p.projection) +
        (isNum(p.rate_per_day) ? ' (' + silver(p.rate_per_day) + '/day, last 7 days)' : '');
    }
    const on = p.on_track === true || met;
    return {
      earned: silver(doc.earned) + ' / ' + silver(doc.goal),
      goal: doc.goal, pct: pct, bar: pct + '%',
      source: SOURCE_TEXT[doc.goal_source] || '',
      needed: needed, projection: projection,
      cls: on ? 'ok' : 'warn',
      pill: met ? 'goal met' : (on ? 'on track' : 'behind')
    };
  }

  // Typed goal text -> {body} for POST /api/grind or {error}. Accepts plain
  // digits (commas / spaces ignored) or a K / M / B suffix; blank clears.
  function goalBody(text) {
    const t = String(text === undefined || text === null ? '' : text).trim().replace(/[,\s]/g, '');
    if (t === '') return { body: { week_goal: null } };
    const m = /^(\d+(?:\.\d+)?)([kmbKMB]?)$/.exec(t);
    if (!m) return { error: 'goal: a silver amount like 300M or 1.2B' };
    const mult = { '': 1, k: 1e3, m: 1e6, b: 1e9 }[m[2].toLowerCase()];
    const v = Math.round(parseFloat(m[1]) * mult);
    if (!(v >= 1 && v <= GOAL_MAX)) return { error: 'goal: 1 .. 10T silver' };
    return { body: { week_goal: v } };
  }

  const api = { silver: silver, card: card, goalBody: goalBody, SOURCE_TEXT: SOURCE_TEXT };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.EWSilverGoal = api;
})(typeof self !== 'undefined' ? self : this);
