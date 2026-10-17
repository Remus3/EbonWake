/* EW loop status (plan 136): pure render helpers for the GET /api/loop
   summary. The System tab's "Loop" card (dashboard.js) and Home's one quiet
   line (home.js, only while the loop is stale, halted or has stuck items) read
   these. Loaded as a plain script (window.EWLoop) and by node --test via
   require(). No DOM here: callers build nodes with DOM APIs. States use the
   kit tokens.json vocabulary (word + status token); colour never carries a
   state alone. */
(function (root) {
  'use strict';

  // loop state -> [kit word, ew-pill class]. Kit tokens: running / idle / warn /
  // bad / halted / unknown; the dashboard pill classes are ok / warn / bad /
  // unknown / off.
  const STATES = {
    running: ['running', 'ok'],
    idle: ['idle', 'off'],
    halted: ['halted', 'warn'],
    stale: ['STALE', 'bad'],
    backoff: ['backoff', 'warn'],
    limit: ['limit', 'warn'],
    refused: ['refused', 'bad'],
    unknown: ['unknown', 'unknown']
  };
  const STUCK_MAX = 8;

  function age(s) {
    if (typeof s !== 'number' || !isFinite(s) || s < 0) return '?';
    if (s < 120) return Math.round(s) + 's';
    if (s < 7200) return Math.round(s / 60) + 'm';
    if (s < 172800) return Math.round(s / 3600) + 'h';
    return Math.round(s / 86400) + 'd';
  }

  function pill(doc) {
    const st = doc && typeof doc.state === 'string' &&
      Object.prototype.hasOwnProperty.call(STATES, doc.state) ? doc.state : 'unknown';
    return { state: st, text: 'loop ' + STATES[st][0], cls: STATES[st][1] };
  }

  function localTime(iso) {
    const t = Date.parse(iso || '');
    if (!isFinite(t)) return '';
    return new Date(t).toLocaleString();
  }

  // The card body: {pill, tick, halt, inflight: [text], stuck: [{id, text, title}], more}.
  function card(doc) {
    const p = pill(doc);
    const d = doc && typeof doc === 'object' ? doc : {};
    let tick = 'no tick recorded';
    if (typeof d.tick_age_s === 'number') {
      tick = 'last tick ' + age(d.tick_age_s) + ' ago';
      if (typeof d.fire === 'number') tick += ', fire ' + d.fire;
      if (typeof d.tick_s === 'number') tick += ', took ' + age(d.tick_s);
      if (d.stale) tick += ' (stale: over ' + age(2 * (d.eta_s || 900)) + ')';
    } else if (d.stale) {
      tick = 'last tick time unreadable (stale)';
    }
    const halt = [];
    if (d.halted) halt.push('HALT file present: no new lanes start');
    if (d.backoff_until) {
      halt.push('usage backoff until ' + (localTime(d.backoff_until) || d.backoff_until) +
        (d.backoff_reason ? ' (' + d.backoff_reason + ')' : ''));
    }
    const inflight = (Array.isArray(d.in_flight) ? d.in_flight : []).map(function (f) {
      const lane = f.lane === undefined || f.lane === null ? '' : 'lane ' + f.lane + ': ';
      return lane + f.id + (f.title ? ' ' + f.title : '') + ' - ' + (f.line || f.state);
    });
    const all = Array.isArray(d.stuck) ? d.stuck : [];
    const stuck = all.slice(0, STUCK_MAX).map(function (s) {
      let why = s.state;
      if (s.state === 'blocked' && Array.isArray(s.needs) && s.needs.length) why += ' on ' + s.needs.join(', ');
      return { id: s.id, text: s.id + ' ' + why + (s.title ? ' - ' + s.title : ''),
        title: (s.since ? 'since ' + (localTime(s.since) || s.since) : '') + (s.error ? ' ' + s.error : '') };
    });
    return { pill: p, tick: tick, halt: halt, inflight: inflight, stuck: stuck,
      more: all.length > STUCK_MAX ? '+' + (all.length - STUCK_MAX) + ' more' : '' };
  }

  // Home's one quiet line, or null while the loop needs no attention.
  function homeLine(doc) {
    if (!doc || typeof doc !== 'object') return null;
    const stuck = Array.isArray(doc.stuck) ? doc.stuck : [];
    const bits = [];
    if (doc.halted) bits.push('halted');
    else if (doc.stale) bits.push('stale');
    if (stuck.length) bits.push(stuck.length + ' stuck');
    if (!bits.length) return null;
    const p = pill(doc);
    return { text: 'loop ' + bits.join(', '), cls: doc.stale && !doc.halted ? 'bad' : 'warn',
      title: stuck.map(function (s) { return s.id + ' ' + s.state; }).join('; ') || p.text, tab: 'system' };
  }

  const api = { STATES: STATES, age: age, pill: pill, card: card, homeLine: homeLine };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.EWLoop = api;
})(typeof self !== 'undefined' ? self : this);
