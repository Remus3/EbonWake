# Plan 162 - code-scanning alert #4 (py/http-response-splitting)

ROADMAP row 159 (MAIN ORDER nc266c6, GitHub Security findings).

## Triage

The only response-header sink fed by request data in `server/ew/app.py` is
`Handler._cors_headers`: plan 153 wrote the request's own `Origin` value into
`Access-Control-Allow-Origin` after an allow-list check. CodeQL does not treat
set membership (`origin in own`) as a sanitizer, so the tainted value reached
`send_header` - the alert is that line. Not exploitable in practice (the
stdlib header parser never yields CR/LF inside a value, and the value had to
equal an allow-listed origin), but the fix is cheap and removes the flow.
Other `send_header` calls write constants (`_redirect` gets `DASHBOARD_PAGE`).

## Fix (TDD)

- Test first: `tests/test_cors_origins.py::test_allow_origin_value_is_server_built_not_request_echo`
  hands `_cors_headers` an Origin that is a `str` subclass (the "request" value)
  and requires the emitted header value to be a plain server-built `str`.
  Red before the fix (2 failures), green after.
- Code: `_cors_headers` iterates the server's allow list (`"null"` plus its
  own loopback origins) and writes the matching allow-list string, never the
  request value. Behaviour is unchanged (plan 153 tests all green).

## As-built deviations

1. Alert read / dismiss / read-back via `gh` not done in this lane.
   Decision: fix in code, leave the alert to auto-close on the next CodeQL run
   of main; the session reads it back (`gh api .../code-scanning/alerts/4`)
   and records before -> after (before: code scanning 1, Dependabot 0, secret
   scanning 0; expected after: 0 / 0 / 0). Alternatives: dismiss as
   false-positive (needs gh, and the flow was real per CodeQL's model).
   Why: `gh` is outside the lane allow list (denied in this run). Reverses if:
   lanes get `gh`, or alert #4 is still open after the CodeQL run of the
   merged fix (then re-triage from the alert's own location).
2. Correction ANSWER to MAIN (TERMINAL, HOP: 2) not sent from the lane.
   Decision: the session / loop sends it after merge and read-back, since it
   must carry the read-back counts. Why: the counts need `gh`; sending blanks
   again would repeat the 2319 defect. Reverses if: lanes get `gh`.
3. Stale "## Order Nc266c6 / Na7e421 / N7e0676 - blocked items" sections at
   the end of `docs/plans/ROADMAP.md` not deleted in the lane. Decision: the
   session deletes them when it flips row 159. Why: the lane order forbids
   editing ROADMAP.md (parallel lanes collided). Reverses if: the lane order
   permits ROADMAP edits.
4. Progress file `ops/loop/control/progress/H07118c.json` not written: the
   write to the main checkout was denied by this run's permissions (same as
   Neba23f / Nc266c6).
