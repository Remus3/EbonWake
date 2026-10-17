/* EW main-process HTTP to the local EW server only (plan 148 APP-SHELL-01).
   Moved out of main.js so node --test covers it. Each call settles exactly
   once: on the full reply, on a socket timeout, on a request error, and on
   a reply cut off mid-body (server killed or crashed while answering) -
   an aborted reply emits neither 'end' nor a request 'error', which used to
   leave the promise pending forever and wedge the watchdog (wdBusy) and the
   tray restart (restarting). Replies are capped at 64 KiB. */
'use strict';

const http = require('http');

const MAX_BODY = 65536;

function readBody(res, done) {
  const chunks = [];
  let size = 0;
  res.on('data', function (c) { size += c.length; if (size <= MAX_BODY) chunks.push(c); });
  res.on('end', function () {
    let parsed = null;
    try { parsed = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch (e) { /* non-JSON */ }
    done(null, parsed);
  });
  res.on('error', function (e) { done(e || new Error('aborted'), null); });
  res.on('close', function () { if (!res.complete) done(new Error('aborted'), null); });
}

// GET a local EW server route: resolves { status, server, doc } or null.
function get(server, route, timeoutMs) {
  const base = new URL(server);
  return new Promise(function (resolve) {
    let settled = false;
    function settle(v) { if (!settled) { settled = true; resolve(v); } }
    const req = http.get({ hostname: base.hostname, port: base.port, path: route, timeout: timeoutMs },
      function (res) {
        readBody(res, function (err, doc) {
          settle(err ? null : { status: res.statusCode, server: res.headers.server, doc: doc });
        });
      });
    req.on('timeout', function () { req.destroy(new Error('timeout')); });
    req.on('error', function () { settle(null); });
  });
}

// POST JSON to a local EW server route: resolves { ok, status, data } or
// { ok: false, status?, error }.
function post(server, route, body, timeoutMs) {
  const base = new URL(server);
  const data = Buffer.from(JSON.stringify(body), 'utf8');
  return new Promise(function (resolve) {
    let settled = false;
    function settle(v) { if (!settled) { settled = true; resolve(v); } }
    const req = http.request({
      hostname: base.hostname, port: base.port, path: route, method: 'POST', timeout: timeoutMs,
      headers: { 'Content-Type': 'application/json', 'Content-Length': data.length }
    }, function (res) {
      readBody(res, function (err, parsed) {
        if (err) { settle({ ok: false, error: 'server offline (' + err.message + ')' }); return; }
        const ok = res.statusCode >= 200 && res.statusCode < 300;
        settle(ok ? { ok: true, status: res.statusCode, data: parsed }
          : { ok: false, status: res.statusCode,
            error: (parsed && typeof parsed.error === 'string' ? parsed.error : 'HTTP ' + res.statusCode) });
      });
    });
    req.on('timeout', function () { req.destroy(new Error('timeout')); });
    req.on('error', function (e) { settle({ ok: false, error: 'server offline (' + e.message + ')' }); });
    req.end(data);
  });
}

module.exports = { get: get, post: post, MAX_BODY: MAX_BODY };
