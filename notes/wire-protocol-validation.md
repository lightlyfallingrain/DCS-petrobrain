# Wire protocol validation

- **A bounds dict iterated as a whitelist (`for field, (lo, hi) in BOUNDS.items(): if field not
  in input: continue`) silently drops any input key absent from that dict — it never raises, it
  just never forwards the field.** `aircraft-layer/src/api/server.py`'s
  `_FLIGHT_CONTROL_LIMITS_BOUNDS` is iterated this way by the `POST /command/flight_control`
  handler's own shape-validation loop; adding eight new wire keys to the Lua side and the
  body-layer sender without also adding them to this one dict would have meant every new `limits`
  field was silently never forwarded to `CommandSender`, while every *other* check in the same
  system (Lua's own bound table, body-layer's own tuning bounds) looked correct in isolation —
  only a test against the real `POST` endpoint end-to-end caught it; a test against
  `CommandSender` alone (which just forwards whatever dict it is handed) gave no signal. General
  shape: a validation dict that doubles as a field whitelist needs its own staleness check
  whenever a sibling layer's field list grows, the same way `test_export_lua_constants_parity.py`
  already checks one specific constant pair — "enumerate the containing unit before fixing" names
  this exact trap (BL-16 mode 1, Stage M2, `plans/flight-control/implementation.md`).

- **A reconciliation that only ever raises a received/restarted process's counter toward a peer's
  echoed value closes the self-inflicted desync case but can still walk the counter to its own
  representable ceiling and jam the channel permanently — it changes the failure's *shape*
  (a logged, explicit error) without reopening its *outcome* (channel dead for the rest of the
  session).** `flight_control`'s `wire_seq` reconciliation (`body._apply_flight_control`) fixed a
  body-layer restart silently desyncing against Lua's own monotonic `fc_last_cmd_seq`, by raising
  `wire_seq` to match Lua's echoed value whenever it lags. But nothing bounds how high the echoed
  value itself can climb over a long session; once it nears the wire format's own max
  (`2**31-1`), reconciliation now *actively* pushes `wire_seq` to that same max, and the next send
  (`wire_seq+1`) overflows the HTTP boundary's own sanity check — an explicit logged error instead
  of the old silent accept-and-ignore, but the channel is still dead for the rest of the session
  either way. The structural fix (bounding how far a single accepted message may advance the
  monotonic counter in the first place) is a different, independent decision from "reconcile a
  lagging local counter toward a peer's echo," and choosing the reconciliation fix for a restart
  case does not retroactively close the ceiling case — say so explicitly rather than let a reader
  assume one fix covers both (BL-16 mode 1, M1+M2 perf/security change-request round,
  `plans/flight-control/implementation.md`, `security-m1-m2.md` Finding A, `review-cr-m1-m2.md`).

- **A clamp written to hold a value "clean" on NaN input does not reliably do so once it feeds a
  downstream formula -- `min`/`max` in Python keep their first argument whenever the comparison
  that would replace it is a NaN comparison, so a chained `max(lo, min(hi, nan))` resolves to a
  concrete, in-range, plausible-looking number, not to NaN.** `BL-B124`'s `sun_elevation_deg`
  propagated a NaN `abs_time_s` (from an unguarded `float("nan")` wire parse) all the way to its
  final `sin_altitude = max(-1.0, min(1.0, sin_altitude))` clamp, which silently resolved to `1.0`
  -- `asin(1.0)` is exactly `90.0`, directly overhead, which then took the feature's own
  full-daylight branch. This is the same Python NaN-comparison mechanism as the "incidental guard"
  pattern already on file (`.claude/agent-memory/security/project_nan_comparison_incidental_
  guards.md`), but the opposite outcome: there, the incidental behaviour happened to be safe; here,
  it silently produced the one answer the feature's own design explicitly forbids. **Never trust
  "the clamp will hold it safe" without tracing what a NaN input actually resolves to through the
  specific clamp expression** -- a `min`/`max` chain is not a NaN filter, and the direction it
  resolves to is a coincidence of argument order, not a guarantee (`plans/bl-b124-light-level/
  security.md` Finding 1, `[[BL-B137]]`).
