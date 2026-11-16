### Performance Review

Scope: BL-B118 (operator altimeter QNH sync at mission start), batch = Stages 1-3, reviewed
before DoD. Address: `feature/bl16-qnh-mission-start`, tip `d12c6f24` (fast-forwarded from
`a7bea50d`, which was a strict ancestor; tree clean). Diff reviewed: `276fdce8..f9e084ad` against
`5f57b54a`. No hard real-time budget applies yet (Petrobrain Runtime has not started) — the
applicable bar is the standing hot-path rules (no per-request allocation, prefer batching/
precomputation, offload blocking work), not a latency SLA. No live DCS run performed (static
review); timeouts/bounds below are read from code constants and the plan's own table, cross-
checked against measured baselines for the sibling mechanisms this one mirrors
(`project_body_layer_poll_loop_serial_unpooled_gets`, `project_brain_layer_poll_thread_stall`,
and `plans/effector-sequences/performance-stage4.md`'s "Synchronous `read_args` inside
`effector_engine.advance`" finding) — said explicitly per finding below.

### Findings

#### One `read_args` + at most one `write_cockpit_switch` on the shared poll thread, per poll, while running
- **Location:** `body-layer/src/body.py:4221-4242` (`_run_crew_text_poll_loop`'s poll body) calls
  `advance_altimeter_qnh_sync` once per poll, unconditionally, right after
  `_check_for_new_mission` and **before** `runner.run_once()` (the perception/belief tick) and
  the attack-run/sight-lock bookkeeping that follows it (confirmed by reading the comment at
  `body.py:4243-4252`, which anchors `sight_lock_seen_before_poll` to run *after* this call). This
  is the same single daemon thread that `effector_engine.advance`, `drain_events`, `drain_brain`
  and every callout live on — there is only one poll thread in this process
  (`body-layer/CLAUDE.md`, "The crew pipeline is the only thing `body.py` does").
- **Risk:** yes, the loop can be mid-convergence while an attack-run or threat callout needs the
  same poll. The run is armed at both `_maybe_switch_theatre` adoption sites — the first-event-
  adopted site fires on **any** mission the process first sees, including an air start where the
  player may already be engaged (confirmed: `body.py:3355`/`3391`, same two sites
  `body-layer/CLAUDE.md`'s own `altimeter_qnh_sync` entry names). So the window is not confined to
  a safe pre-flight moment.
- **How long one poll can block, measured vs. inferred:** `aircraft_client.read_args` is a
  synchronous `urlopen` with client-side `timeout_s=2.0` (`aircraft_client.py:179`,
  `_DEFAULT_TIMEOUT_S`). The collector's own `ArgReadBroker.read` (what answers
  `POST /query/read_args`) bounds its *own* wait at `ARG_READ_TIMEOUT_S = 0.25` s
  (`aircraft-layer/src/collector/arg_read_broker.py:38`) and always replies — success or a bounded
  error — within that window, confirmed by code (not re-measured live here; this is the same
  constant `plans/effector-sequences/performance-stage4.md` already measured/verified for the
  identical mechanism). `write_cockpit_switch` is a fire-and-forget UDP command send
  (`command_sender.send_cockpit_switch`), not a round-trip wait, so it never contributes to the
  blocking figure. So: **typical case ≈ 0.25 s added to that one poll's wall time** (an Export.lua
  that hasn't answered yet, the broker's own designed timeout); **pathological case ≈ 2.0 s**
  (the aircraft-layer HTTP server itself unreachable/wedged at the TCP/HTTP level, not just a slow
  `Export.lua` — the broker's 0.25 s bound only covers the "Export.lua hasn't replied" case). The
  2.0 s figure is a code constant read directly, not re-measured under load here, but it matches
  the same client default already measured elsewhere in this codebase
  (`project_brain_layer_poll_thread_stall`: an up-but-wedged peer consumes exactly its configured
  timeout, no backoff, on this project's analogous brain-poll call).
- **Iterations and wall time to converge:** the plan's own bounds are
  `ALTIMETER_QNH_MAX_ITERATIONS = 20` (5–60) and `ALTIMETER_QNH_MAX_DURATION_S = 15.0` s (5.0–60.0),
  with `ALTIMETER_QNH_SETTLE_S = 0.3` s (0.05–2.0) gating each step. At the project's
  `_DEFAULT_POLL_INTERVAL_S = 1.0` s, the settle gate never skips a poll at default settings
  (0.3 s < 1.0 s), so the loop advances roughly one iteration per poll and the realistic
  convergence envelope is **bounded at ~15-20 s of wall time after any mission (re)start**,
  whichever bound bites first — this is the plan's own stated sizing (120 mmHg worst-case window
  span ÷ the calibration step), not independently re-derived here. During that window, every poll
  costs its normal work **plus** ≈0.25 s typical / ≈2.0 s pathological for the one blocking read —
  i.e. up to a ~25% (typical) or up to a ~200% (pathological, one-poll-only) stretch of that one
  poll's period, for as long as the run stays `"running"`. This delays that poll's `run_once()`,
  attack-run alignment derivation, and any callout drain by the same amount, every poll, for the
  whole convergence window — concretely reachable at an air start already in combat, not just a
  cold mission start.
- **Whether reads/writes are rate-limited per poll:** yes, strictly — `advance_altimeter_qnh_sync`
  issues **at most one `read_args` and at most one `write_cockpit_switch` per call**, and `body.py`
  calls it **at most once per poll**. This is a tighter bound than the sibling mechanism it
  explicitly mirrors: `effector_engine.advance`'s one-shot reads can issue up to N sequential
  blocking `read_args` calls in a single `advance()` (one per concurrently-running trigger needing
  a fresh snapshot), reviewed and accepted at MONITOR in
  `plans/effector-sequences/performance-stage4.md`. This mechanism's single-call-per-poll shape is
  strictly cheaper than that already-accepted N-per-poll shape.
- **Cost after completion or failure:** confirmed none. `advance_altimeter_qnh_sync`'s first line
  (`if state.phase != "running": return state`) is an immediate return with no I/O once terminal
  (`succeeded`/`failed_no_response`/`failed_timeout`), and `body.py` keeps calling it every poll
  regardless — that call is a single attribute check plus a dataclass return, not measurable
  against the rest of the poll body.
- **The hook's extra `net.dostring_in` calls:** confirmed one-time. `resolveQnh()`/
  `resolveAtmosphereType()` (`petrobrain-mission-start-hook.lua`) each add one
  `net.dostring_in("scripting", ...)` round trip, mirroring the existing `resolveTheatre()` call
  exactly, and all three run only inside the mission-start hook — fired once per DCS mission
  (re)start, never per poll, never per frame. Not a hot-path concern at any realistic mission-
  change frequency.
- **Action:** MONITOR, not NOW. The mechanism is bounded on every axis that matters (one read, at
  most one write, per poll; iteration- and wall-clock-capped overall; zero cost once terminal) and
  is strictly cheaper than the already-accepted `effector_engine` one-shot-read pattern it was
  deliberately built to mirror (module docstring says so explicitly, and the plan cites the same
  "blocks briefly, not indefinitely" posture). The real, named risk — a ~0.25 s (typical) to ~2.0 s
  (pathological, aircraft-layer-down) stretch of the shared poll thread's period, recurring for up
  to ~15-20 s right after any mission (re)start including an already-engaged air start — is the
  same order of magnitude and the same architectural shape as the pre-existing, already-reviewed
  "5 aircraft-layer GETs per poll, 2.0 s timeout each" risk
  (`project_body_layer_poll_loop_serial_unpooled_gets`), not a new cost class. Revisit only if a
  future change makes this run concurrently with another one-shot-read consumer on the same poll,
  or if `ALTIMETER_QNH_MAX_DURATION_S`/`ALTIMETER_QNH_SETTLE_S` get tuned toward their `hi` bounds
  in a way that meaningfully lengthens the convergence window.

#### No per-request allocation beyond the existing dataclass `replace()` shape
- **Location:** `body-layer/src/belief/altimeter_qnh_sync.py`, every branch of
  `advance_altimeter_qnh_sync`.
- **Risk:** none. One `AltimeterQnhSyncState` (frozen, `slots=True`) `replace()` call per poll
  while running — the same cost class every other frozen-dataclass belief state in this codebase
  already pays once per poll (`GuidanceUnitState`, `SightHead`, etc.). No collections built, no
  per-poll allocation that scales with contact count or scene size.
- **Action:** none needed.

#### `_maybe_start_altimeter_qnh_sync` / arming
- **Location:** `body-layer/src/body.py:3044` area, called at both mission-adoption sites inside
  `_check_for_new_mission`.
- **Risk:** none at realistic scale. Fires only on a genuine mission (re)start detection — already
  a rare, gated event in this codebase (BL-15's own mechanism) — and does O(1) work (clamp, log,
  construct one state). Not a hot-path call.
- **Action:** none needed.

### Verdict
APPROVED — MONITOR
