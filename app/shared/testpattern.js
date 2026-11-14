'use strict';
/* Plan 175: overlay test pattern. Pure window config + a one-at-a-time runner
   for main.js, testable without Electron. The operator presses a Settings
   button; EW opens a SEPARATE window of its own over the overlay display: a
   labelled border for DURATION_MS, transparent, click-through, focus-less and
   always-on-top, exactly like the overlay. The operator then confirms by eye
   whether it drew above the client (DX11 and DX12 renderers) and records the
   answer. Game ToS floor: no game input, no window handle, hook or injection -
   only EW's own BrowserWindow. */

const DURATION_MS = 10000;
const TOP_LEVEL = 'screen-saver';
const PAGE = 'overlay/testpattern.html';

function rect(b) {
  return !!b && typeof b === 'object' && [b.x, b.y, b.width, b.height].every(Number.isInteger) &&
    b.width > 0 && b.height > 0;
}

// bounds = the overlay display's full bounds (a borderless client covers it).
function config(bounds) {
  const b = rect(bounds) ? bounds : { x: 0, y: 0, width: 800, height: 600 };
  return {
    options: {
      x: b.x, y: b.y, width: b.width, height: b.height,
      transparent: true, frame: false, resizable: false, movable: false,
      focusable: false, skipTaskbar: true, hasShadow: false, show: false,
      alwaysOnTop: true,
      webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true }
    },
    ignoreMouseEvents: true,
    alwaysOnTopLevel: TOP_LEVEL,
    durationMs: DURATION_MS,
    page: PAGE
  };
}

// open(cfg) -> a window-like {setIgnoreMouseEvents, setAlwaysOnTop, showInactive,
// close, isDestroyed, on}. start(bounds) opens at most one; a second press while
// one shows is a no-op ({ok: true, already: true}). The window closes itself
// after durationMs.
function createRunner(open, timers) {
  const t = timers || { setTimeout: setTimeout, clearTimeout: clearTimeout };
  let win = null;
  let timer = null;
  function done() {
    if (timer) t.clearTimeout(timer);
    timer = null;
    const w = win;
    win = null;
    if (w && !(typeof w.isDestroyed === 'function' && w.isDestroyed())) {
      try { w.close(); } catch (e) { /* already gone */ }
    }
  }
  return {
    active: function () { return win !== null; },
    start: function (bounds) {
      if (win) return { ok: true, already: true, ms: DURATION_MS };
      const c = config(bounds);
      let w;
      try { w = open(c); } catch (e) { w = null; }
      if (!w) return { ok: false, error: 'could not open the test pattern' };
      win = w;
      w.setIgnoreMouseEvents(c.ignoreMouseEvents, { forward: false });
      w.setAlwaysOnTop(true, c.alwaysOnTopLevel);
      if (typeof w.on === 'function') w.on('closed', function () { if (win === w) { win = null; } });
      w.showInactive();
      timer = t.setTimeout(done, c.durationMs);
      return { ok: true, already: false, ms: c.durationMs };
    },
    stop: done
  };
}

module.exports = { DURATION_MS: DURATION_MS, TOP_LEVEL: TOP_LEVEL, PAGE: PAGE,
  config: config, createRunner: createRunner };
