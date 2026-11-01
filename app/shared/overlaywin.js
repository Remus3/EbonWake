'use strict';
/* MAIN ORDER Nee58d0 items 5-7 (2026-10-31 UI/UX round). Pure overlay-window
   logic for main.js, testable without Electron:
   - EW-OVERLAY-FOCUS: the overlay shows only while wanted (hotkey toggle) AND,
     while the game runs, only while the game is the foreground window (hidden
     on alt-tab and on minimise). The foreground source is a hidden poller
     (shared/foreground.ps1) that reads the OS foreground window's process
     name - it never touches the game process, its memory or its input.
   - EW-DISPLAY-BY-ID: the operator's display index is saved as that
     display's ID, so a monitor reconnect (index reorder) keeps the overlay
     on the same screen; a missing display falls back silently to primary.
   - EW-CAPTURE-OPT: optional setContentProtection, default OFF (the desktop
     self-test captures the overlay). */

const GAME_PROCESSES = ['blackdesert64'];
const FG_RX = /^fg=([^|\r\n]*)\|game=([01])$/;

function isGameProcess(name) {
  return typeof name === 'string' && GAME_PROCESSES.indexOf(name.toLowerCase()) !== -1;
}

// One poller line -> {name, game} or null.
function parseForeground(line) {
  if (typeof line !== 'string') return null;
  const m = FG_RX.exec(line.trim());
  return m ? { name: m[1], game: m[2] === '1' } : null;
}

// visible = wanted && (gate off || game not running || game is foreground).
// apply(visible) runs on every change only. No foreground report yet = the
// old toggle-only behaviour (fails open, never hides on a missing source).
function createFocusGate(opts) {
  const apply = opts && typeof opts.apply === 'function' ? opts.apply : function () {};
  const enabled = !(opts && opts.enabled === false);
  let wanted = false;
  let fg = null;
  let last = false;
  function visible() {
    if (!wanted) return false;
    if (!enabled || !fg || !fg.game) return true;
    return isGameProcess(fg.name);
  }
  function update(force) {
    const v = visible();
    if (v !== last || force) { last = v; apply(v); }
  }
  return {
    visible: visible,
    wanted: function () { return wanted; },
    setWanted: function (b) { wanted = !!b; update(false); },
    onForeground: function (report) { if (report) { fg = report; update(false); } },
    reapply: function () { last = visible(); apply(last); }
  };
}

function validSaved(s) {
  return !!s && typeof s === 'object' && !Array.isArray(s) &&
    Number.isInteger(s.index) && s.index >= 0 && Number.isInteger(s.id);
}

// all = screen.getAllDisplays(), index = config overlay.display (null = auto),
// saved = {index, id} from runtime state. Returns {display, saved}: the saved
// ID is followed while the configured index is unchanged; a new index is
// bound to the display at that index now; a missing display = primary.
function resolveDisplay(all, primary, index, saved) {
  const list = Array.isArray(all) ? all : [];
  if (!Number.isInteger(index) || index < 0) return { display: primary, saved: null };
  if (validSaved(saved) && saved.index === index) {
    const hit = list.find(function (d) { return d && d.id === saved.id; });
    return { display: hit || primary, saved: saved };
  }
  const d = list[index];
  if (d && Number.isInteger(d.id)) return { display: d, saved: { index: index, id: d.id } };
  return { display: primary, saved: null };
}

function contentProtection(cfg) {
  return !!(cfg && cfg.overlay && typeof cfg.overlay === 'object' && cfg.overlay.content_protection === true);
}

function focusHide(cfg) {
  return !(cfg && cfg.overlay && typeof cfg.overlay === 'object' && cfg.overlay.focus_hide === false);
}

// The hidden foreground poller: powershell.exe 5.1, no window, one line per
// change on stdout. onReport gets parseForeground() results; the poller is
// restarted after RESTART_MS if it exits. Returns stop().
const RESTART_MS = 30000;
function startForeground(spawn, script, onReport, timers) {
  const t = timers || { setTimeout: setTimeout, clearTimeout: clearTimeout };
  let child = null;
  let timer = null;
  let stopped = false;
  function run() {
    timer = null;
    if (stopped) return;
    try {
      child = spawn('powershell.exe', ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
        '-File', script], { windowsHide: true, stdio: ['ignore', 'pipe', 'ignore'] });
    } catch (e) { child = null; }
    if (!child) { timer = t.setTimeout(run, RESTART_MS); return; }
    let buf = '';
    child.stdout.on('data', function (chunk) {
      buf += String(chunk);
      let i;
      while ((i = buf.indexOf('\n')) !== -1) {
        const r = parseForeground(buf.slice(0, i));
        buf = buf.slice(i + 1);
        if (r) onReport(r);
      }
      if (buf.length > 4096) buf = '';
    });
    child.on('error', function () { /* exit follows or never: restart below */ });
    child.on('exit', function () {
      child = null;
      onReport({ name: '', game: false });   // fail open: toggle-only
      if (!stopped) timer = t.setTimeout(run, RESTART_MS);
    });
  }
  run();
  return function stop() {
    stopped = true;
    if (timer) t.clearTimeout(timer);
    if (child) { try { child.kill(); } catch (e) { /* gone */ } }
  };
}

module.exports = {
  GAME_PROCESSES: GAME_PROCESSES, RESTART_MS: RESTART_MS,
  isGameProcess: isGameProcess, parseForeground: parseForeground,
  createFocusGate: createFocusGate, validSaved: validSaved, resolveDisplay: resolveDisplay,
  contentProtection: contentProtection, focusHide: focusHide, startForeground: startForeground
};
