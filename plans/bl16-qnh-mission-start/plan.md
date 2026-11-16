### Goal

At every mission start — ground or air — Petrovich reads the mission's QNH and drives the
operator (copilot) barometric altimeter's pressure setting to match it, so ED's AI-pilot barometric
hold (`[[BL-16]]`'s parked-mode fix) is flying against a correct reference instead of whatever
pressure setting the mission left on the knob.

Goal-aligner skipped per the dispatching brief: the pilot stated the goal and its why verbatim
(`docs/acceptance/2026-11-16-bl16-batch-a-feedback.md`, "The barometric bug"), and the explore
round settled every open question (`1 use QNH for copilot / 2 set at mission start, both ground
start and air start / 3 moves steadily`). Plan-aligner runs after this plan.

### Why, and what is already known

`aircraft-layer/research/2026-11-16-mi24p-operator-altimeter-recon.md` (Windows-box file recon,
no live DCS read yet):

- Operator pressure **window** is arg 834, `pressure_mmhg = 670 + 120 * arg834`, display range
  670–790 mmHg.
- Operator **knob** is device 42 (`BAROALT_O`), `ALTIMETER-KNOB-OP-PTR`, command 3001
  (`default_axis`, arg 788 is the knob's own rotation, `relative = true`). **`performClickableAction
  (42, 3001, v)` rotates the knob by a delta `v`; it does not set an absolute pressure, and the
  mmHg-per-delta gain is unmeasured** (compiled C++, no device Lua). Command 3002 is the key-binding
  pair (±1, no release defined) and is **not** used here — 3001 is "cleanest for a closed loop on
  arg 834" per the research note.
- **Unverified, and the one real risk**: whether device 42 accepts the write at all when the human
  player is sitting in the pilot seat (operator crew access `{1}`), which is the common case.
- Mission QNH is `env.mission.weather.qnh`, mmHg, read exactly the way
  `petrobrain-mission-start-hook.lua` already reads `env.mission.theatre` — `net.dostring_in
  ("scripting", ...)`, best-effort, `null` on failure.
- The pilot explicitly declined a probe flight first (*"Skip the probe, just build setting
  QNH."*) — the first live flight is the test, so the design has to make that flight legible
  (what happened, what didn't, why) rather than relying on a dry run to have already answered the
  open questions.

No `investigator` dispatch needed beyond the recon already on file — the open items it leaves
(the knob's gain, and whether the write is honoured from the pilot seat) are not resolvable by
further file reading or forum research; they can only be answered by the closed loop itself,
live. Both are carried as named risks below, not silent assumptions.

### Existing mechanisms reused — nothing new in `Export.lua`

- **`write_cockpit_switch(device, cmd, value)`** (`AircraftLayerClient`, BL-B66) and
  **`read_args([...])`** (BL-B90 Stage 4) already exist and need no Lua-side change:
  `handle_cockpit_switch_command` validates shape only (finite `value`, no range clamp) and
  forwards straight to `performClickableAction`, so a negative or fractional delta passes through
  unmodified — confirmed by reading `aircraft-layer/dcs-export/Export.lua` lines 1184–1205 and
  `aircraft-layer/src/api/server.py`'s `/command/cockpit_switch` handler (400 only on
  missing/non-finite, no clamp).
- **`Export.lua` is at Lua 5.1's 200-local ceiling** (`aircraft-layer/ROADMAP/AC-B12.md`) until
  `feature/ac-b12-export-modules` merges. This feature adds zero `Export.lua` locals — the only
  aircraft-layer change is to the **Hook-state** mission-start script
  (`petrobrain-mission-start-hook.lua`), a separate chunk with its own budget, mirroring its
  existing `resolveTheatre()`.
- **The effector-sequences engine (`belief/effector_sequences.py`/`effector_engine.py`) is the
  wrong tool here and is deliberately not used.** Its row grammar is a fixed menu of named
  `values` per registered switch (a discrete on/off/position write with an implicit self-check);
  it has no row type for "drive a continuous arg to an externally-computed numeric target via an
  unknown-gain relative command, closed-loop." Forcing this into that grammar would mean adding a
  new row type and engine support for a one-off action — more machinery than the action itself.
  Named here per root `CLAUDE.md`'s "do not reinvent the wheel" (name what you depart from, and
  why).
- **The "when" is `_check_for_new_mission`'s existing theatre-adoption point, not
  `EffectorTrigger.MISSION_START`.** `MISSION_START` deliberately waits for a trusted *fresh
  ownship sample* before firing (to classify ground/air correctly) — up to
  `MISSION_START_RESOLVE_FALLBACK_S` (30 s default). The altimeter sync needs no ownship sample at
  all; tying it to that wait only adds latency for no benefit. `_maybe_switch_theatre` is called at
  exactly the two moments a mission's own facts (its theatre) become known — the first-event-adopted
  case (process started mid-mission) and a genuine (re)start — and QNH is the same kind of fact
  about the same event, learned at the same two moments. A new sibling function,
  `_maybe_start_altimeter_qnh_sync`, is called alongside `_maybe_switch_theatre` at both sites. This
  also satisfies "both ground start and air start" directly, with no branch on `on_ground` at all.

### Affected Modules / Files

- `aircraft-layer/src/schema/mission_start.py` — add `qnh: float | None` to `MissionStartEvent`
  (parse/validate in `from_dict`, emit in `to_dict`), docstring updated to describe it the same
  way `theatre` is described (best-effort, `null` on failure, body-layer decides what `null`
  means).
- `aircraft-layer/dcs-export/petrobrain-mission-start-hook.lua` — add `resolveQnh()` mirroring
  `resolveTheatre()` exactly (`net.dostring_in("scripting", "return env.mission.weather.qnh")`,
  `nil` on any failure/non-number result), include `qnh` in the UDP payload.
- `aircraft-layer/tests/test_mission_start_schema.py` — `qnh` present/absent/non-numeric cases.
- `aircraft-layer/CLAUDE.md` — one line in the mission-start-signal description noting the new
  field (small, not a new mechanism).
- `body-layer/src/belief/altimeter_qnh_sync.py` **(new)** — the action: `AltimeterQnhSyncState`
  (frozen dataclass, `replace()`-only, single construction site) and
  `advance_altimeter_qnh_sync(state, aircraft_client, now_wall) -> state`, the self-calibrating
  closed loop (see "The closed loop" below). Declares the tunables.
- `body-layer/src/body.py`:
  - `ConsolePerceptionRunner`: new field `altimeter_qnh_sync: AltimeterQnhSyncState | None = None`
    (plain default, not `init=False` — the exact trap `notes/mission-start-and-reset-patterns-
    bl-15.md` already recorded is avoided by using a normal constructor-included field). **Not** in
    `reset_for_new_mission`'s preserved-field list — it resets to `None` on every mission (re)start
    like `last_mission_start_sequence`, and `_maybe_start_altimeter_qnh_sync` reassigns it
    explicitly afterward on both adoption sites, same pattern.
  - `_maybe_start_altimeter_qnh_sync(runner, event_qnh)` **(new)** — reads `event.get("qnh")` at
    both `_maybe_switch_theatre` call sites inside `_check_for_new_mission`; validates, clamps,
    logs, and sets `runner.altimeter_qnh_sync` to a fresh running state (or clears it to `None` if
    `qnh` is missing/invalid this mission).
  - The poll loop (`_run_crew_text_poll_loop`): one call per poll, unconditional —
    `runner.altimeter_qnh_sync = advance_altimeter_qnh_sync(runner.altimeter_qnh_sync,
    aircraft_client, time.monotonic())` when not `None`; on a transition into a `failed_*` phase,
    set `crew_console.altimeter_qnh_failed_pending = True`. Wired next to the existing
    `drain_config_error` call so the two can share one `GET /spu8/state` fetch when either flag is
    pending (that call's own comment already names the performance reason to share it).
- `body-layer/src/belief/crew_console.py`:
  - `altimeter_qnh_failed_pending: bool = field(default=False, repr=False)` — **not** preserved
    across a mission reset (unlike `config_error_pending`, which is a once-per-process startup
    flag): this condition can recur on a later mission (re)start, so it resets with everything
    else and is re-armed by that mission's own sync attempt.
  - `ALTIMETER_QNH_FAILED_LINE: Final[str]` and `drain_altimeter_qnh_failed(now_sim, *,
    intercom_open)` — same shape as `drain_config_error` (speak once, held until the SPU-8 gate is
    open, deferred — not dropped — while silenced).
- `body-layer/src/tuning.py` — no code change; the new constants are declared in
  `altimeter_qnh_sync.py` the same way every other module declares its own (`tuning.real`/
  `tuning.whole` calls at import time), and `config/defaults.toml` picks them up via the existing
  generator.
- `body-layer/config/defaults.toml` — regenerated (`tools/generate_defaults.py --write`) to pick up
  the new keys.
- `body-layer/tests/test_altimeter_qnh_sync.py` **(new)** — the closed loop against a fake
  read/write pair, no network.
- `body-layer/tests/test_mission_start_reset.py` — QNH-adoption counterpart to the existing
  theatre-adoption tests (both sites: first-event and genuine-reset).
- `body-layer/tests/test_crew_console.py` — `drain_altimeter_qnh_failed` tests mirroring the
  existing `drain_config_error` tests.
- `body-layer/CLAUDE.md` — one paragraph beside the existing mission-start-trigger paragraph,
  naming this mechanism and that it is deliberately *not* an effector-sequence trigger.

### The closed loop

Self-calibrating (secant-method) because the gain (arg834 change per unit of the delta sent to
cmd 3001) is unmeasured and cannot be derived from the shipped files — the research note says so
explicitly. One `advance_altimeter_qnh_sync` call per poll; non-blocking across polls (a settle
wait is a wall-clock check that returns the state unchanged, never a `time.sleep`, so a slow
converge never stalls contact ingestion, speech, or anything else on the poll thread for more than
one `read_args` round trip at a time — the same "blocks briefly, not indefinitely" posture
`effector_engine`'s own one-shot reads already have).

1. **Target.** `target_mmhg = clamp(qnh, 670.0, 790.0)`. If `qnh` fell outside the window, log once
   at INFO (not spoken — this needs pressure far outside anything DCS's weather model produces to
   trigger, and a clamped-but-set altimeter is strictly better than an unset one).
2. **Each step**, gated on `now_wall - last_write_wall >= ALTIMETER_QNH_SETTLE_S` (or immediately
   if no write has been sent yet):
   - `read_args([834])` → `current_mmhg = 670 + 120 * arg834`. A transport failure
     (`AircraftLayerError`) is treated as transient — skip this poll, retry next, same posture
     `_check_for_new_mission` already uses for the mission-start poll itself — bounded by the
     overall time/iteration caps below so a dead collector cannot hang this forever.
   - `error_mmhg = target_mmhg - current_mmhg`. If `abs(error_mmhg) <= ALTIMETER_QNH_TOLERANCE_MMHG`
     → **succeeded**, stop.
   - If `iterations >= ALTIMETER_QNH_MAX_ITERATIONS` or elapsed wall time `>=
     ALTIMETER_QNH_MAX_DURATION_S` → **failed_timeout**, stop.
   - If this is iteration ≥ 1: `observed_delta_arg = arg834 - prev_arg834`. If
     `abs(observed_delta_arg) < ALTIMETER_QNH_NO_RESPONSE_EPSILON`, increment a
     no-response-strike counter; at `ALTIMETER_QNH_NO_RESPONSE_STRIKES` consecutive strikes →
     **failed_no_response**, stop (this is the "the knob did not move" case the brief names —
     two consecutive non-responses, not one, so a single noisy read can't trip it). A strike
     resets to 0 the moment a response is observed.
   - Compute the next delta: with a gain estimate available (`gain = observed_delta_arg /
     prev_delta_sent`, finite and non-zero), `delta = clamp((error_mmhg / 120.0) / gain,
     -ALTIMETER_QNH_MAX_STEP, ALTIMETER_QNH_MAX_STEP)`. With no estimate yet (iteration 0, or a
     degenerate gain), `delta = sign(error_mmhg) * ALTIMETER_QNH_CALIBRATION_STEP` — a small
     nominal probe. The clamp is the real safety net: a bad or wrong-signed gain estimate on one
     step only costs an extra iteration, never a runaway write, and the secant update self-corrects
     the sign on the next step regardless of which way the first probe guessed.
   - `write_cockpit_switch(42, 3001, delta)`. Record `prev_arg834 = arg834` (read just now, before
     this write), `prev_delta_sent = delta`, `iterations += 1`, `last_write_wall = now_wall`.
3. On **succeeded**: stop advancing (state stays at `succeeded`, inert, until the next mission
   (re)start replaces it). No spoken line (silent background housekeeping, matching the existing
   mission-start sequence rows' mostly-empty `petrovich-says` column).
4. On **failed_no_response** / **failed_timeout**: stop advancing, arm
   `crew_console.altimeter_qnh_failed_pending`. One spoken line
   (`"Unable, operator altimeter not responding."` for no-response;
   `"Unable, altimeter pressure not set."` for timeout — "unable + because," the project's own
   convention for an action that is unavailable rather than misheard), held until the SPU-8
   intercom gate is open, same deferral `drain_config_error` already uses.

### Tunables (`body-layer/src/tuning.py` via `tuning.real`/`tuning.whole`, declared in
`altimeter_qnh_sync.py`)

| key | default | bounds | status | why |
|---|---|---|---|---|
| `ALTIMETER_QNH_TOLERANCE_MMHG` | 0.3 | 0.1–1.0 | agreed-guess | "well under 1 mmHg (~11 m)" per the brief; 0.3 mmHg ≈ 3 m |
| `ALTIMETER_QNH_CALIBRATION_STEP` | 0.05 | 0.01–0.2 | uncalibrated | the knob's gain is unmeasured; this is the nominal first probe |
| `ALTIMETER_QNH_MAX_STEP` | 0.3 | 0.05–1.0 | uncalibrated | bounds any single write regardless of a bad gain estimate |
| `ALTIMETER_QNH_SETTLE_S` | 0.3 | 0.05–2.0 | uncalibrated | time between a write and the next read; the device's own settle time is unmeasured |
| `ALTIMETER_QNH_MAX_ITERATIONS` | 20 | 5–60 | agreed-guess | enough for the worst-case 120 mmHg window span at the calibration step size |
| `ALTIMETER_QNH_MAX_DURATION_S` | 15.0 | 5.0–60.0 | agreed-guess | overall wall-clock bound, independent of iteration count |
| `ALTIMETER_QNH_NO_RESPONSE_EPSILON` | 0.002 | 0.0005–0.02 | uncalibrated | arg834 units; must be well under `CALIBRATION_STEP` |
| `ALTIMETER_QNH_NO_RESPONSE_STRIKES` | 2 | 1–5 | agreed-guess | one noisy read must not trip a hard failure |

**Grep performed per the "new temporal/threshold constant" rule**: no existing constant in
`body-layer/src/` or `config/defaults.toml` governs an altimeter, a pressure, device 42, or arg
834/788/788 — `AI_PILOT_ALTITUDE_TOLERANCE_M` (`belief/ai_pilot_wheel.py`) is the nearest
neighbour (a different closed loop, different device, 20 m tolerance on a different quantity) and
is not reused: it tolerates ED's own AI-wheel altitude hold, not the operator altimeter's pressure
window.

### Implementation Plan

1. **Aircraft-layer wire change.** `qnh` field on `MissionStartEvent`, `resolveQnh()` in the Hook
   script, schema tests. No live DCS needed for this stage (offline parse tests only) — acceptance
   criterion: `test_mission_start_schema.py` covers `qnh` present (float), absent, `null`, and a
   non-numeric value (rejected the same way a non-string `theatre` is).
2. **The closed loop, offline.** `altimeter_qnh_sync.py` plus `test_altimeter_qnh_sync.py` against
   a fake object exposing `read_args`/`write_cockpit_switch` with a scripted, parameterised
   fake-device gain (including a zero-gain "knob ignores every write" fake proving
   `failed_no_response`, a never-converges fake proving `failed_timeout`, a transient-error fake
   proving the skip-and-retry posture, and at least one realistic-gain fake proving convergence
   within tolerance from a worst-case 120 mmHg error). Acceptance: every terminal phase reachable
   and asserted; no call ever exceeds `ALTIMETER_QNH_MAX_STEP`; `config/defaults.toml` regenerated
   and its staleness test passes.
3. **Wire into `body.py`/`CrewConsole`.** `_maybe_start_altimeter_qnh_sync`, the new
   `ConsolePerceptionRunner` field, the poll-loop call, `altimeter_qnh_failed_pending`/
   `drain_altimeter_qnh_failed`. Acceptance: `test_mission_start_reset.py` shows QNH adopted at
   both sites (first-event, genuine reset) and dropped to `None` when the event's `qnh` is missing;
   `test_crew_console.py` shows the failed line spoken once, deferred while the gate is closed,
   deferred while silenced, and re-armable on a later mission (re)start (the one behaviour that
   deliberately differs from `config_error_pending`).
4. **Live check (the card).** Mission start (ground, then a separate air-start sortie) → poll
   `read_args([834])` (or watch the cockpit window directly) and confirm it reads the mission's
   known QNH within tolerance within `ALTIMETER_QNH_MAX_DURATION_S` → "Request Aircraft Control" no
   longer produces the wild barometric target the P0/takeover-rehearsal probes measured (+742 m,
   +737 m) on the *first* toggle after takeover. **If the knob ignored the write from the pilot
   seat**: the spoken "Unable, operator altimeter not responding" line is the signal — note which
   seat the human player was in, and whether swapping seats changes the outcome, since that is the
   one fact no amount of file reading could resolve.

### Risks & Unknowns

- **The knob may not respond at all from the pilot seat** (operator crew access `{1}`,
  unverified) — this is the single largest risk to the whole feature, and the first live flight is
  the only way to learn it, per the pilot's own direction to skip a probe. The design fails loud
  (`failed_no_response`, one spoken line) rather than silently doing nothing, which is the most
  this plan can do about an unknown it cannot resolve on paper.
- **The gain is unmeasured and may be non-linear, asymmetric (CW vs CCW), or saturate near the
  window edges** — the secant method tolerates a wrong estimate (it only costs iterations, bounded
  by `ALTIMETER_QNH_MAX_ITERATIONS`/`ALTIMETER_QNH_MAX_DURATION_S`), but a genuinely pathological
  response curve (e.g. a dead zone, or a gain that flips sign mid-range) could still oscillate
  without converging — this is exactly what `failed_timeout` catches, not a silent hang.
- **The settle time between a write and the next read is guessed** (0.3 s) — too short would read
  a write still in flight and miscompute gain; too long just makes the loop slower. Either way it
  fails toward `failed_timeout`, not toward a wrong setting, because the tolerance check runs every
  iteration regardless.
- **Dynamic weather's `qnh` may not be meaningful** (research note, caveat, unverified) — this
  plan reads whatever numeric value the mission reports and acts on it at face value; if dynamic
  weather turns out to report a nonsensical static `qnh` while weather is actually varying, that
  surfaces as a wrong cockpit reading on a flight using dynamic weather, not a crash — worth a
  dedicated research note the first time it is observed, not solved speculatively here.
- **Interaction with the takeover-fix's own correction loop is additive, not exclusive** — if this
  sync succeeds, the takeover fix (`BL-16` Stage P1 revision) should find nothing to correct on the
  next "Request Aircraft Control" (its own stated safety-net posture: *"if the altimeter is set
  right, the wild target should stop appearing and the correction finds nothing to correct"*). If
  this sync fails (no-response/timeout), the takeover fix still runs exactly as it does today — no
  ordering dependency between the two, and neither reads the other's state.

### Decisions Requiring User Input

- **U1: does Petrovich say anything on success, or stay silent?** Recommend: silent — this is
  background avionics housekeeping before the pilot starts moving, matching the existing
  `mission-start.md` sequence rows, most of which have an empty `petrovich-says` cell. A short
  confirmation (e.g. "Altimeter set.") is easy to add later if it turns out to matter in flight;
  defaulting to silence costs nothing to reverse and avoids a line on every single mission start.
- **U2: one live sortie or two for the card?** Recommend: two short sorties, one ground start and
  one air start, since "both ground start and air start" is the pilot's own stated requirement
  (explore answer 2) and a ground-start pass alone would leave the air-start path — the one that
  matters most for the `BL-16` takeover fix, since that fix only runs once the aircraft is already
  airborne — untested.

### Second-order effect

If the knob turns out to respond only from the operator seat (the open risk above resolves
negatively), that is also the answer BL-16's own parked-mode/takeover work needs for every other
operator-seat effector it writes — this sync attempt, failing first and loudly, is effectively a
free probe for that broader question, at no extra flight cost. No other milestone is unblocked,
narrowed, or complicated by this change.
