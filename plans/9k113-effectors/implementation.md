### Implementation Summary

BL-B66 Stages 1-4 (`plans/9k113-effectors/plan.md`, text above the `# Superseded text below`
divider). Stage 5 (acceptance sortie) is explicitly out of scope for this pass.

Built back to back as directed, on `feature/9k113-effectors`, fast-forwarded from
`5f6b43cb04d6d6984544f8324ff947b6f98f5ac1`.

### Stage 1 — the cockpit-action channel (aircraft-layer)

- `aircraft-layer/dcs-export/Export.lua` — new `"cockpit_switch"` op on `poll_command_socket`'s
  dispatch (`handle_cockpit_switch_command`): writes *any* `(device, cmd, value)` via
  `GetDevice(device):performClickableAction(cmd, value)`, shape-validated only (device/cmd must be
  integers, value a finite number) — **no allow-list**, per the user's explicit override of the
  security plan review's required fix. Every write is flag-gated debug-logged. New
  `push_cockpit_switch_state` readback telemetry (args 773/761/885/955/886/673, change-epsilon,
  wire key `"missl_pw"`), same shape as `push_spu8_state`. `EXPORT_SCRIPT_VERSION`/
  `EXPECTED_EXPORT_VERSION` bumped to `2026-10-21`.
- New `aircraft-layer/src/schema/cockpit_switch.py` (`CockpitSwitchState`), `collector/cache.py`
  (`CockpitSwitchCache`), `collector/command_sender.py` (`CommandSender.send_cockpit_switch`),
  `collector/server.py` line routing, `api/server.py` (`POST /command/cockpit_switch`,
  `GET /cockpit_switch/latest`), `collector/__main__.py` wiring.
- `body-layer/src/aircraft_client.py` — `write_cockpit_switch` (raises, mirrors
  `trigger_petrovich_search`) and `get_cockpit_switch_state_latest` (swallow-to-`None`).

### Stage 2 — the guidance-unit power-up (body-layer)

- New `body-layer/src/belief/sight_effector.py` — the one module that knows device/arg/command
  numbers: `GuidanceUnitState` (frozen dataclass), `start_power_up`/`advance_power_up` (the
  four-switch sequencer: MISSILE POWER 773 → CPLR DISTR 761 (UNVERIFIED) → Sight Power 885 → SHCHO
  PWR B1 955, one write per call spaced by `GUIDANCE_UNIT_SWITCH_DELAY_S`), `sight_ready` (the
  readiness predicate), `write_observ`/`write_weapon_safety` (single writes, no sequencing),
  `refresh_readback` (pulls `observ_observed`/`weapon_safety_observed` from the aircraft layer's
  own telemetry — unread by this entry, carried for `BL-B67`).
- `logger.py` — `ConsolePerceptionRunner.guidance_unit_state` field (one construction site,
  grep-tested); poll-loop wiring: takeoff rising-edge detection (reuses `on_ground`'s existing
  signal, no new telemetry field), `advance_power_up`/`refresh_readback` every poll,
  `crew_console.sight_ready` refresh, and `CrewConsole.drain_guidance_unit_ready` (new method,
  speaks "Guidance unit ready." exactly once).

### Stage 3 — OBSERV as a real cockpit write (body-layer)

- `crew_console.py` — `_handle_observ_on` now gates on `self.sight_ready`
  (new field, default `False`), returning `render_unable("GUIDANCE_NOT_READY")` when not ready;
  `_handle_observ_off` unchanged (no gating, per plan §3). `speech.py` — new
  `"GUIDANCE_NOT_READY": "Unable, guidance unit not ready."` template.
- `logger.py` — on an accepted `observ_transition`, the real cockpit write (`write_observ`) is
  issued alongside the existing `OpticState.home_phase` mutation, wrapped in try/except
  (`AircraftLayerError` logged and continued, never crashes the poll loop); sets
  `GuidanceUnitState.observ_commanded`.

### Stage 4 — the weapons safety bar (body-layer + audio-adapter)

- `crew_console.py` — `weapon_safety_transition` field (one-shot signal, same shape as
  `observ_transition`); `_handle_weapons_armed`/`_handle_weapons_safe` (new handlers, added to
  `DISPATCHED_COMMAND_TOKENS`); `_handle_engage` now also sets `weapon_safety_transition = "armed"`
  alongside its existing `attack_run_transition = "engage"` (plan §4: "ARMED ... any attack run
  start").
- `logger.py` — drains `weapon_safety_transition`, writes arg 673 via `write_weapon_safety`
  (1=ARMED, 0=SAFE, confirmed `body-layer/research/2026-10-14-9k113-warmup-atgm-procedure.md`
  Finding 6), sets `GuidanceUnitState.weapon_safety_commanded`.
- `audio-adapter/src/vocabulary.py` — `"weapons_armed"`/`"weapons_safe"` added to
  `VOICE_ONLY_TOKENS` and `PHRASES` (`"weapons armed"`/`"weapons safe"` only, per user direction —
  "weapons on/off" explicitly dropped). Not added to the F10 menu (voice is primary, the F10
  vocabulary is the legacy, non-growing one — checked per the task brief's instruction).
  **The "weapons"/"tanks" `VERB_FLOOR` near-collision is accepted by the user, 2026-10-21:**
  *"keep it, we'll test on the sortie. There's no good alternative either."* Stage 5 listens for
  false triggers.

### Tuning

- `GUIDANCE_UNIT_SWITCH_DELAY_S` (`belief.sight_effector`, default `1.0`, `lo=0.5, hi=5.0`,
  `status="derived"`) through `tuning.real`. `config/defaults.toml` regenerated and checked — the
  **rendered** comment (not the source `#:` comment) states what the constant does and which
  direction is dangerous, per root `CLAUDE.md`'s rule.
- 761 (`CPLR DISTR`) is a plain literal, not a tuning key — it is a *fact* (an argument/command
  number), not a behaviour knob; marked UNVERIFIED in three places (`Export.lua`,
  `sight_effector.py`, `cockpit_switch.py`).

### Files Changed

**aircraft-layer**
- `dcs-export/Export.lua` — `cockpit_switch` op, `push_cockpit_switch_state`, version bump.
- `src/schema/cockpit_switch.py` (new), `src/schema/__init__.py` (re-export).
- `src/collector/cache.py` (`CockpitSwitchCache`), `src/collector/command_sender.py`
  (`send_cockpit_switch`), `src/collector/server.py` (line routing, version bump), `src/collector/
  __main__.py` (wiring).
- `src/api/server.py` — `POST /command/cockpit_switch`, `GET /cockpit_switch/latest`.
- `CLAUDE.md` — Tech stack bullet for the new channel (the "What this is" exception note was
  already present from the fast-forwarded merge).

**body-layer**
- `src/belief/sight_effector.py` (new) — the guidance-unit/OBSERV/weapon-safety effector module.
- `src/aircraft_client.py` — `write_cockpit_switch`/`get_cockpit_switch_state_latest`.
- `src/belief/crew_console.py` — `sight_ready`/`weapon_safety_transition` fields,
  `_handle_observ_on` readiness gate, `_handle_weapons_armed`/`_handle_weapons_safe`,
  `_handle_engage`'s new ARMED side effect, `drain_guidance_unit_ready`.
- `src/belief/speech.py` — `GUIDANCE_NOT_READY` unable-template.
- `src/logger.py` — `guidance_unit_state` field, poll-loop wiring (takeoff detection, sequencer
  advance, readback refresh, OBSERV/weapon-safety cockpit writes).
- `config/defaults.toml` — regenerated (`GUIDANCE_UNIT_SWITCH_DELAY_S`).
- `ROADMAP/BL-B66.md` — dated implementation note; stays `#status/in-progress` pending Stage 5.

**audio-adapter**
- `src/vocabulary.py` — `weapons_armed`/`weapons_safe` tokens and phrases.

### Tests Added

- `aircraft-layer/tests/test_cockpit_switch.py` — schema (parse/threshold/boolean-decide),
  `CockpitSwitchCache`, collector line routing (including "never parsed as telemetry" and "no
  cache configured" cases), `CommandSender.send_cockpit_switch`, and the full
  `POST /command/cockpit_switch`/`GET /cockpit_switch/latest` endpoint surface — including a test
  that an *arbitrary* `(device, cmd)` pair is accepted (the no-allow-list decision, asserted
  positively, not just absence of a check).
- `body-layer/tests/test_sight_effector.py` — the power-up sequencer (immediate first write,
  delay-respecting subsequent writes, in-order device/cmd pairs, becomes-ready transition,
  true-no-op before start/after completion), the failed-write retry (stage does not advance,
  logs, retries successfully next poll), `write_observ`/`write_weapon_safety` (correct
  device/cmd/value, raises on failure), `refresh_readback`, and two grep-based tests enforcing the
  plan's "Construction-site check" (`GuidanceUnitState` has exactly one real construction site in
  `logger.py`; `sight_effector.py` itself never constructs it directly).
- `body-layer/tests/test_crew_console.py` — `test_observ_on_refused_when_guidance_unit_not_ready`,
  `test_observ_off_needs_no_readiness` (new); three **pre-existing** tests updated to set
  `console.sight_ready = True` before calling `observ_on` (see Deviations below).
- `audio-adapter/tests/test_command_matcher.py` — `TestWeaponsArmedSafe` (both phrasings resolve;
  the measured `"weapons"` vs `"tanks"` false-anchor collision, asserted explicitly; no collision
  with any existing phrase).
- `body-layer/tests/test_logger.py` — `FakeConsoleAircraftClient` gained
  `get_cockpit_switch_state_latest`/`write_cockpit_switch` so the existing `_run_crew_text_poll_loop`
  tests keep working against the new per-poll calls.

### Checks

**aircraft-layer/**
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src`: pass (26 source files)
- `pytest`: pass (407 passed)
- `luac5.1 -p Export.lua`: pass; bytecode global-leak check (`luac5.1 -l -p` → `GETGLOBAL` scan):
  clean, no new helper name leaks as a global.

**body-layer/**
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src`: pass (69 source files)
- `pytest`: pass (2383 passed, 4 xfailed)
- `tools/generate_defaults.py` staleness test: pass (regenerated and committed)

**audio-adapter/**
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src`: pass (16 source files)
- `pytest`: pass (346 passed, 2 skipped)

### Deviations / Notable Discoveries

1. **Device/cmd numbers for the four power-up switches had to be cross-referenced from three
   different research docs**, not read off any single table — the plan's own Affected Modules
   section names the six args but not their numeric device/cmd pairs. Resolved from
   `aircraft-layer/research/mi24p-command-surface.md` (positional table, confirms device ids
   WEAP_SYS=6/I9K113=7/ASP_17V=16 and cmd numbers 3028/3015/3001/3030) and the 2026-10-17 probe
   findings (confirms 773/885/886/955/673 live; 761 untested there). Recorded in
   `sight_effector.py`'s own comments with their sources, so a future reader does not have to
   redo this cross-reference.

2. **Three existing `test_crew_console.py` tests needed a one-line addition** (`console.sight_ready
   = True`) because Stage 3's readiness gate is a genuine, plan-mandated behaviour change to
   `_handle_observ_on` that the tests predate — they asserted `observ_on` always succeeds, which is
   no longer true against the new (and correct) default of `sight_ready=False`. Modified rather
   than left broken, with a comment on each explaining why and pointing at the new tests
   (`test_observ_on_refused_when_guidance_unit_not_ready`, `test_observ_off_needs_no_readiness`)
   that now cover the readiness dimension those three were not written to test.

3. **A measured, structural collision between the user's locked voice phrase and the recognizer's
   verb-anchor mechanism — flagged for visibility, not silently absorbed.** `audio-adapter`'s
   `VERB_ANCHOR_WORDS` is strictly derived from the first word of every phrase in `PHRASES`, with
   no override list (by design — see `command_matcher.py`'s own docstring). Adding `"weapons
   armed"`/`"weapons safe"` makes `"weapons"` a verb-anchor word, and
   `difflib.SequenceMatcher(None, "tanks", "weapons").ratio() == 0.5`, exactly `VERB_FLOOR` — the
   same floor-boundary collision the existing `"engage"`/`"attack"` rejection comment in
   `vocabulary.py` already documents and avoided by *not* adding `"attack"`. Here there is no
   substitute word available (the phrase is the user's own exact, locked wording, Decision 3), so
   I added it anyway. The phrase-sequence score — `command_matcher.py`'s own stated "real
   defence" — still rejects the adversarial sentence (`"the tanks are on the ridge"`) end to end:
   `token` stays `None`. The only observable change is the intermediate `verb_anchored` flag
   flipping `False → True` on that one sentence, which is exactly the accepted-cost category the
   module's own docstring describes ("a false anchor... costs one extra phrase-scoring pass that
   almost always rejects it anyway"). One pinned test
   (`test_transcribe_api.py::test_non_command_speech_enqueues_with_null_token`) asserted the
   intermediate flag specifically and was updated (one assertion removed, with a comment); its
   actual regression guard — `token is None` — is untouched and still passes. A new test
   (`test_command_matcher.py::TestWeaponsArmedSafe::test_weapons_is_a_measured_false_anchor_
   against_tanks`) pins the collision explicitly so it cannot silently regress further. Flagging
   this for the Reviewer/user: if this trade is unacceptable, the fix is a product decision (a
   different phrase, or accepting degraded recognition on this one adversarial sentence class),
   not something further engineering here can resolve — the derivation is deliberately
   hand-override-free.

4. **`refresh_readback`/`observ_observed`/`weapon_safety_observed` are wired but genuinely unread**
   by this entry's own logic, exactly as the plan specifies — this is not an oversight; `BL-B67` is
   named as the consumer. Flagging again here per the plan's own instruction ("stated here so it is
   not rediscovered the way `BL-B64`'s own defect was").

5. **No `.venv` existed in this worktree for any of the three touched subprojects** (worktrees don't
   carry gitignored content) — created fresh for each, pinned to the main checkout's own installed
   tool versions (`ruff 0.16.6`/`0.16.8`, `mypy 2.3.1`, `pytest 9.1.1`) so the checks run against
   the same tooling the project already uses.

### What the acceptance sortie (Stage 5, not built here) must verify

Per the plan's own Stage 5 card: take off, confirm the four switches move and "Guidance unit
ready" is heard; try "Observ on" before and after that callout (expect a refusal, then
acceptance); say "Observ off"; say "weapons armed"/"engage" and "weapons safe", confirming arg
673's readback both ways; and specifically confirm or correct arg 761 (`CPLR DISTR`) by throwing
it by hand while watching `GET /cockpit_switch/latest`'s `cplr_distr`/`cplr_distr_on` fields.

## Review fix (`plans/9k113-effectors/review.md`, required fix)

The review's one required fix: the `_run_crew_text_poll_loop` wiring for Stages 2-4 (takeoff
rising-edge detection, sequencer advance/readback refresh/`sight_ready` refresh/
`drain_guidance_unit_ready`, and the OBSERV/weapons-safety cockpit write-through) had no test
driving the real poll loop — only `belief.sight_effector`'s own pure-function tests in isolation,
confirmed as a real gap by the reviewer's own two mutations (forcing the takeoff `if` to `False`;
removing the `announced` guard in `CrewConsole.drain_guidance_unit_ready`), both of which left the
full suite green.

**Added three tests to `body-layer/tests/test_logger.py`**, all driving the real
`_run_crew_text_poll_loop` on a background thread (same technique as the pre-existing
`test_crew_text_poll_loop_resets_belief_on_mission_restart`), mutating the fake client's telemetry
dict between polls the way a real sortie's clock would:

- `test_takeoff_runs_the_guidance_unit_power_up_sequence_through_the_real_poll_loop` — no write
  while still on the ground; the four switches (`(6, 3028, 1.0)`, `(16, 3015, 1.0)`,
  `(7, 3001, 1.0)`, `(6, 3030, 1.0)`) written in order on the takeoff rising edge, advancing the
  fake's own sim clock by `GUIDANCE_UNIT_SWITCH_DELAY_S` between writes (the sequencer's own gate
  is *sim* time, not wall time); `sight_ready` checked `False` on every partial count (1-3
  switches) so a sequencer that readied early would be caught even if the 4th write landed on the
  very next tick; "Guidance unit ready." spoken exactly once across six further polls after
  completion, captured via `crew_console.output = io.StringIO()` (not `capsys` — this reads more
  reliably across the poll thread/main thread boundary than a global stdout capture).
- `test_second_takeoff_in_the_same_mission_does_not_rerun_the_power_up` — starts from an
  already-ready `GuidanceUnitState` (bypassing the sequence the first test already covers), drives
  a landing then a second takeoff via `crew_console.on_ground`, and confirms no further writes.
- `test_observ_and_weapons_safety_write_through_the_real_poll_loop` — "Observ on" before
  `sight_ready` is refused through the real loop with no write
  (`["Unable, guidance unit not ready."]`, `cockpit_switch_writes == []`); once ready, "Observ on"
  writes `(7, 3002, 1.0)`, "weapons armed" writes `(6, 3020, 1.0)`, "weapons safe" writes
  `(6, 3020, 0.0)`, each via `crew_console.handle_command` dispatched from the main thread and
  observed landing on the real poll thread's own write-through block.

**Both of the reviewer's mutations re-run and confirmed to fail** (then reverted, confirmed by
`shasum` before/after on both files):
- Forcing the takeoff `if` to `False` in `logger.py` → `test_takeoff_runs_the_guidance_unit_
  power_up_sequence_through_the_real_poll_loop` fails (`cockpit_switch_writes == []` instead of the
  expected four writes).
- Removing the `announced` guard from `CrewConsole.drain_guidance_unit_ready` → the same test fails
  (`spoken.count("Guidance unit ready.") == 20`, not `1`).

No bug was found while writing these tests — the wiring behaves exactly as the plan and the
pure-function tests already claimed; the gap was coverage, not correctness. One scope note: a
telemetry fixture that starts airborne (rather than on the ground, `CrewConsole.on_ground`'s own
default) produces a takeoff rising edge on the very first poll, since `on_ground` defaults `True`
— the third test's telemetry was adjusted to start on the ground for exactly this reason, after
first hitting it as a test-authoring mistake, not a product bug.

**Checks (re-run after the fix):**
- `ruff format --check body-layer/src body-layer/tests`: pass (one file reformatted by
  `ruff format` before the check — the new tests' multi-line `while (...)` conditions over
  3-tuples, reformatted to ruff's own single-line style).
- `ruff check body-layer/src body-layer/tests`: pass.
- `cd body-layer && .venv/bin/mypy src`: pass, no issues (69 source files). `mypy tests` is not a
  project command (see `body-layer/CLAUDE.md`'s "Commands") and was not run; it has ~170
  pre-existing errors unrelated to this change.
- `pytest body-layer/tests -q`: **2386 passed, 4 xfailed** (2383 passed before this fix, +3 new
  tests, no regressions).
- No `.venv` existed in this worktree (fresh worktree) — created with `python3.12 -m venv .venv`
  and `pyproj`/`numpy<2.5`/`pytest`/`ruff`/`mypy` installed per `body-layer/pyproject.toml`'s own
  declared dependencies.

## Stage 4b — slew telemetry logging (`plans/9k113-effectors/plan.md`'s "Stage 4b" paragraph)

User direction, 2026-10-21: *"Put logging in so that the slew loop can be adjusted based on data
from logs. Actual vs desired angles especially, slew command values, etc."* Purpose: data to tune
`[[BL-B80]]`'s rate loop from, plus the hand-slew segment on the Stage 5 acceptance sortie card.

### aircraft-layer

- `dcs-export/Export.lua` — args 874/876 (the sight's own actual-position readback) added to the
  existing `push_cockpit_switch_state` line (change-epsilon, a finer `SIGHT_POS_EPSILON` than the
  switches' own `COCKPIT_SWITCH_EPSILON` — the probe drove 874/876 in steps as small as 0.002).
  A **second, independent debug flag** (`aircraft_layer_slew_debug.flag`, distinct from the
  general `DEBUG` flag) gates a new per-**frame** local log (`push_slew_trace`,
  `Logs\aircraft_layer_slew_trace.log`): sim time, raw 874/876, OBSERV (886), and a
  `slew_cmd_az`/`slew_cmd_el` pair that is always `null` in this entry (nothing writes the player
  slew axis yet — `[[BL-B80]]` fills that field rather than adding a new log format). Logged only
  while OBSERV is on, plus a `SLEW_TRACE_TAIL_S` (5 s) tail after it goes off, so an idle sortie's
  log stays empty; buffered (`SLEW_LOG_FLUSH_EVERY_N_LINES = 25`) rather than one flush per frame,
  flushed on `LuaExportStop`. `EXPORT_SCRIPT_VERSION`/`EXPECTED_EXPORT_VERSION` bumped to
  `"2026-10-21b"` (additive wire-format change, same-day `b` suffix per the project's existing
  convention).
- `src/schema/cockpit_switch.py` — `CockpitSwitchState.sight_az`/`sight_elev`, `float | None`,
  **optional** unlike the six switch fields (an `Export.lua` predating Stage 4b never sends them;
  absent must parse as "no reading yet", not a parse error). `from_dict` validates type only when
  the key is present; `to_api_dict` always includes both.

### body-layer

- `src/belief/sight_effector.py` — `GuidanceUnitState.sight_az_raw`/`sight_elev_raw` (raw args
  874/876, refreshed by `refresh_readback` the same call as `observ_observed`/
  `weapon_safety_observed`, same absence-leaves-prior-value posture). New
  `sight_azimuth_raw_to_deg`, the one confirmed raw-to-degrees calibration (`arg_874 = (deg/60) *
  0.44`, inverted) — **azimuth only**; elevation's gauge is still unmeasured, so there is
  deliberately no equivalent function for 876. A plain module constant (`_SIGHT_AZIMUTH_DEG_PER_
  RAW_UNIT`), not a tuning key: it is a measured fact, and a different value would not change
  anything Petrovich does, only how a debug log displays a number — same reasoning the plan already
  applies to arg 761.
- `src/sight_trace_writer.py` — **new.** `SightTraceWriter`, following `detection_trace_writer.py`'s
  shape (buffer a few polls, flush periodically, disable-after-first-write-error) at a fraction of
  the complexity (no ground-truth/belief join — just `OpticState` and `GuidanceUnitState`, both
  already public and belief-side). One row per poll: desired az/el (`OpticState.look_azimuth_deg`/
  `look_elevation_deg`), actual az/el with a `_source` field ("readback" when a raw 874 reading
  exists and converts via the calibration above, "model" otherwise, `None` while no look is
  commanded), the error, raw 874/876 (logged regardless of which actual value is used, "alongside
  any degree conversion" per the plan — elevation's `_source` is always `"model"`, never
  `"readback"`, since its conversion is unmeasured, but its raw reading is still carried so a
  conversion can be derived later without a second sortie), OBSERV commanded/observed, and optic
  mode (`OpticState.look_optic.name`, `None` outside an active look).
- `src/logger.py` — `--slew-trace PATH` (requires `--crew-text`, same posture as the other per-run
  logs this entry is scoped to): a sixth per-run log, with its own sibling resolver
  (`_resolve_slew_trace_log_path`, mirroring `_resolve_group_trace_log_path`) rather than widening
  `_per_run_log_paths`'s arity, same reasoning that function's own docstring already gives for
  `--group-trace`/`--mission-memory`. `_reroll_run_logs` gained `slew_trace_writer`/`slew_trace_base`
  parameters and now returns a 3-tuple (both existing call sites updated: `--console`'s passes
  `None`/`None` and discards the third element). `_run_crew_text_poll_loop` builds the writer, calls
  `write_poll` every poll a real ownship state exists — **after** the guidance-unit/OBSERV block has
  had its turn to update `optic_state`/`guidance_unit_state` that same poll, never before, or the
  row would log the previous poll's values under the current timestamp — and closes it in the
  `finally:` block. `--console` never gets this flag: the takeoff/power-up/OBSERV wiring this writer
  reads only runs on the crew-text loop.

### Tuning

None. Considered and rejected: `SIGHT_POS_EPSILON`/`SLEW_TRACE_TAIL_S`/`SLEW_LOG_FLUSH_EVERY_N_
LINES` (Lua) and `DEFAULT_FLUSH_EVERY_N_POLLS` (`sight_trace_writer.py`) all affect what gets
*logged*, never what Petrovich *does* — the inclusion test in root `CLAUDE.md`'s "Behaviour-
affecting constants are tunable" excludes them, same category `DetectionTraceWriter.DEFAULT_
FLUSH_EVERY_N_POLLS` already sits in. `_SIGHT_AZIMUTH_DEG_PER_RAW_UNIT` is a measured fact (a
calibration), not a tunable, for the same reason arg 761 is a plain literal rather than a tuning
key. Outside body-layer (`Export.lua`) there is no tuning loader at all, per root `CLAUDE.md`'s
"Outside body-layer the loader does not exist yet."

### `sortie-log-triage` skill

- `.claude/skills/sortie-log-triage/scripts/triage.py` — two new report functions. `slew_report`
  (`--slew PATH`, default `~/aircraft_layer_slew_trace.log`) reads the aircraft-layer per-frame log:
  rows with OBSERV on, smallest observed non-zero step in 874/876 (a controller's deadband can never
  be finer than this), and the rate (deg/s, azimuth only, converted via the same calibration) over
  the longest monotonic azimuth run — the exact data the Stage 5 hand-slew segment exists to
  produce. Explicitly reports "readback lag: not computed" rather than fabricating a number — there
  is no commanded-side timestamp to lag against until `slew_cmd_az`/`slew_cmd_el` are non-null
  (`[[BL-B80]]`). `body_slew_report` (`--body-slew PATH`, no default — the flag has none) reads
  `--slew-trace`'s own per-poll file as a coarser cross-check (azimuth source counts,
  `|error_azimuth_deg|` distribution).
- `SKILL.md` — a "Slew" subsection under "What each section answers", and two notes: this skill now
  reads one aircraft-layer file (a deliberate, stated exception to "this skill reads body-layer's
  own three files, `dcs-log-recon` reads Export.lua's"), and `aircraft_layer_slew_trace.log` is
  never stamped (it is outside `run_log_paths` entirely, a single accumulating file across every
  sortie the flag was on for) while `--slew-trace`'s own file is.

### Files Changed

**aircraft-layer**
- `dcs-export/Export.lua` — args 874/876 added to `push_cockpit_switch_state`; new
  `aircraft_layer_slew_debug.flag`/`push_slew_trace`/`slew_log_flush`; version bump.
- `src/schema/cockpit_switch.py` — `sight_az`/`sight_elev` fields, docstring.
- `src/collector/server.py` — `EXPECTED_EXPORT_VERSION` bump + comment.
- `tests/test_cockpit_switch.py` — two new parse tests; two existing `to_api_dict`/endpoint
  assertions extended with the two new (always-`None`-in-these-tests) fields.
- `CLAUDE.md` — Tech stack bullet extended for Stage 4b.

**body-layer**
- `src/belief/sight_effector.py` — `sight_az_raw`/`sight_elev_raw` fields, `refresh_readback`
  extended, new `sight_azimuth_raw_to_deg`.
- `src/sight_trace_writer.py` (new) — `SightTraceWriter`.
- `src/logger.py` — `--slew-trace` CLI flag + validation, `_resolve_slew_trace_log_path`,
  `_reroll_run_logs`'s widened signature/return, poll-loop wiring.
- `tests/test_sight_effector.py` — new conversion/readback tests.
- `tests/test_sight_trace_writer.py` (new) — field-selection, buffering, and failure-mode tests.
- `tests/test_run_log_reroll.py` — updated the three existing unpacking call sites for the new
  3-tuple return; one new reroll test for the slew-trace writer.
- `tests/test_logger.py` — `FakeConsoleAircraftClient.cockpit_switch_state` (new, settable); one
  new wiring-level test driving the real poll loop.
- `CLAUDE.md` — `--slew-trace` documented alongside `--detection-trace`; added to the Decision-5
  per-mission-reroll list.

**Project**
- `.claude/skills/sortie-log-triage/scripts/triage.py`, `SKILL.md` — slew sections.

### Tests Added

- `aircraft-layer/tests/test_cockpit_switch.py::test_parses_a_line_with_sight_position_readback`,
  `::test_a_present_but_non_numeric_sight_position_is_a_parse_error` — the optional-field parse
  contract (present-and-numeric parses, absent is `None`, present-but-wrong-typed still errors).
- `body-layer/tests/test_sight_effector.py::test_refresh_readback_sets_sight_position_raw_fields_
  from_the_latest_sample`, `::test_refresh_readback_leaves_sight_position_unchanged_when_absent`,
  `::test_sight_azimuth_raw_to_deg_uses_the_confirmed_calibration` — the new readback fields and
  conversion function.
- `body-layer/tests/test_sight_trace_writer.py` (10 tests) — every field-selection branch (readback
  vs. model per axis, elevation never "readback", error computation, all-null while scanning, optic
  mode, OBSERV passthrough), buffering (`_polls_since_flush` resets on the configured cadence), and
  the write-failure-disables-after-one-report posture (`_FullDiskFile` double, same technique as
  `test_detection_trace.py`'s own).
- `body-layer/tests/test_run_log_reroll.py::test_reroll_closes_the_old_slew_trace_writer_and_opens_
  a_new_one` — the open-handle-close-before-reassign shape, mirroring the existing detection-trace
  reroll test.
- `body-layer/tests/test_logger.py::test_slew_trace_is_written_from_the_real_poll_loop` — drives
  OBSERV on, a sight-position readback arriving through the fake client, and OBSERV off, through the
  real `_run_crew_text_poll_loop`; asserts on the rows actually written to disk (at least one row
  before OBSERV is touched, `observ_commanded` both `True` and `False` across the run, the
  readback-sourced row's converted azimuth degrees and both raw values). **Verified as a real
  regression guard, not just green by construction**: disabled the `write_poll` call site with an
  `and False` short-circuit, confirmed the test fails for the stated reason (`len(rows) >= 2`
  against zero rows), restored the line, confirmed `shasum` on `logger.py` matches the pre-mutation
  hash and the test passes again.

### Checks

**aircraft-layer/**
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src`: pass (26 source files)
- `pytest`: pass (409 passed)
- `luac5.1 -p Export.lua`: pass; bytecode global-leak scan (`luac5.1 -l -p` → `GETGLOBAL` scan):
  clean, no new helper name leaks as a global.

**body-layer/**
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src`: pass (70 source files)
- `pytest`: pass (2401 passed, 4 xfailed)
- `tools/generate_defaults.py` staleness test (`test_tuning_defaults_toml.py`): pass — no tunables
  added this stage, `config/defaults.toml` untouched.

### How to turn the logging on for the sortie

Flags to set, in order:

1. **On the Windows box**, create (any content, even empty)
   `Saved Games\DCS\Scripts\aircraft_layer_slew_debug.flag` before launching DCS — checked once at
   load, so a flag created after the mission starts needs a mission/DCS restart to take effect. This
   enables the per-frame local log at `Saved Games\DCS\Logs\aircraft_layer_slew_trace.log`; it writes
   nothing while OBSERV is off, so it is safe to leave on for the whole sortie.
2. **On the Mac**, add `--slew-trace logs/dcs-slew-trace.jsonl` to the existing `logger.py` command
   line (alongside `--crew-text`; omit on `--console`, which is rejected with a `parser.error`). The
   actual filename written is stamped (`run_log_paths`), printed to stderr as the process starts.
3. **Fly the Stage 5 card's hand-slew segment** (~2 minutes, full left/right and up/down, slow and
   fast, with OBSERV on) — this is what both files above are collecting data for.
4. **After landing**, copy `aircraft_layer_slew_trace.log` from the Windows box over to wherever
   `python3 .claude/skills/sortie-log-triage/scripts/triage.py` is run from (default `~`, or pass
   `--slew PATH`), and pass the stamped `--slew-trace` file as `--body-slew PATH`.
