/* EW server watchdog (plan 135). Pure state machine, no Electron: main.js
   probes GET /api/health every POLL_MS and feeds next(state, probe, now);
   on 'restart' it calls its existing restartServer() (which kills only an
   EW-contract server). The dashboard loads this file too for statusLine().
   Touches only EW's own server on 127.0.0.1; never the game. */
(function (root) {
  'use strict';

  const MIN = 60000;
  const POLL_MS = 20000;
  const FAILS_TO_RESTART = 3;
  const BACKOFF_START_MS = MIN;
  const BACKOFF_MAX_MS = 30 * MIN;
  const BACKOFF_RESET_MS = 10 * MIN;
  const HOUR_MS = 60 * MIN;
  const MAX_PER_HOUR = 6;
  const LOG_CAP = 500;

  function initial() {
    return { fails: 0, restarts: [], lastRestart: null, backoffMs: 0, okSince: null, gaveUp: false };
  }

  function copy(s) {
    const b = s && typeof s === 'object' ? s : initial();
    return {
      fails: b.fails | 0, restarts: Array.isArray(b.restarts) ? b.restarts.slice() : [],
      lastRestart: typeof b.lastRestart === 'number' ? b.lastRestart : null,
      backoffMs: b.backoffMs | 0, okSince: typeof b.okSince === 'number' ? b.okSince : null,
      gaveUp: b.gaveUp === true
    };
  }

  function recent(restarts, now) {
    return restarts.filter(function (t) { return now - t < HOUR_MS; });
  }

  // probe: 'ok' or 'fail' (anything else counts as fail). opts.restarting:
  // a manual restart (tray / pill) is in flight, so do nothing at all.
  function next(state, probe, now, opts) {
    const s = copy(state);
    if (opts && opts.restarting) return { state: s, action: 'none' };
    if (probe === 'ok') {
      s.fails = 0;
      s.gaveUp = false;
      if (s.okSince === null) s.okSince = now;
      if (now - s.okSince >= BACKOFF_RESET_MS) s.backoffMs = 0;
      return { state: s, action: 'none' };
    }
    s.okSince = null;
    s.fails++;
    if (s.gaveUp || s.fails < FAILS_TO_RESTART) return { state: s, action: 'none' };
    if (s.lastRestart !== null && now - s.lastRestart < s.backoffMs) return { state: s, action: 'none' };
    s.restarts = recent(s.restarts, now);
    if (s.restarts.length >= MAX_PER_HOUR) {
      s.gaveUp = true;
      return { state: s, action: 'give-up' };
    }
    s.restarts.push(now);
    s.lastRestart = now;
    s.backoffMs = s.backoffMs ? Math.min(s.backoffMs * 2, BACKOFF_MAX_MS) : BACKOFF_START_MS;
    return { state: s, action: 'restart' };
  }

  function phase(state) {
    const s = copy(state);
    if (s.gaveUp) return 'gave-up';
    return s.fails >= FAILS_TO_RESTART ? 'restarting' : 'ok';
  }

  // What the dashboard sees over the ew:watchdog bridge.
  function summary(state, now) {
    const s = copy(state);
    return { state: phase(s), restartsLastHour: recent(s.restarts, now).length, lastRestart: s.lastRestart };
  }

  const LABEL = { ok: 'ok', restarting: 'restarting', 'gave-up': 'gave up' };

  function statusLine(sum, now) {
    if (!sum || !Object.prototype.hasOwnProperty.call(LABEL, sum.state)) return null;
    const n = sum.restartsLastHour | 0;
    let line = 'Watchdog: ' + LABEL[sum.state] + ' - ';
    line += n ? n + ' auto-restart' + (n === 1 ? '' : 's') + ' in the last hour'
      : 'no auto-restart in the last hour';
    if (n && typeof sum.lastRestart === 'number') {
      const m = Math.floor((now - sum.lastRestart) / MIN);
      line += ', last ' + (m < 1 ? '<1' : m) + ' min ago';
    }
    return line;
  }

  // ops/runtime/watchdog.jsonl: append one row, keep the last LOG_CAP rows.
  function capLog(text, row) {
    const lines = String(text || '').split('\n').filter(function (l) { return l.trim() !== ''; });
    lines.push(JSON.stringify(row));
    return lines.slice(-LOG_CAP).join('\n') + '\n';
  }

  const api = {
    POLL_MS: POLL_MS, FAILS_TO_RESTART: FAILS_TO_RESTART, BACKOFF_START_MS: BACKOFF_START_MS,
    BACKOFF_MAX_MS: BACKOFF_MAX_MS, BACKOFF_RESET_MS: BACKOFF_RESET_MS, MAX_PER_HOUR: MAX_PER_HOUR,
    LOG_CAP: LOG_CAP, initial: initial, next: next, phase: phase, summary: summary,
    statusLine: statusLine, capLog: capLog
  };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else if (root) root.EWWatchdog = api;
})(typeof window !== 'undefined' ? window : null);
