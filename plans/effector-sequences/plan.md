# BL-B90 — configurable cockpit effector sequences

Precedence: `plans/effector-sequences/explore-notes.md` (user's own words) >
`docs/concept/configurable-cockpit-effector.md` ("concept, not final truth") >
`body-layer/ROADMAP/BL-B90.md` > this plan's own text.

### Goal

Replace BL-B66's hard-coded guidance-unit power-up / OBSERV / weapons-safety-bar switch logic
(`body-layer/src/belief/sight_effector.py` + its `logger.py` wiring) with a named effector
registry plus startup-loaded, markdown-table sequence files per (aircraft, role, trigger) — so
adding or reordering a cockpit switch sequence is a data edit, not a code change — while leaving
every gating/refusal decision (readiness, armed/safe) in code and leaving the slew loop (`BL-B80`)
untouched.

### What already exists, and what this entry reuses rather than invents

- **The write channel is already fully generic.** BL-B66 Stage 1's `cockpit_switch` op
  (`Export.lua`'s `handle_cockpit_switch_command`, `aircraft_client.write_cockpit_switch`) writes
  *any* `(device, cmd, value)` with no allow-list — user direction, 2026-10-21. **This plan needs
  zero `Export.lua`/aircraft-layer change for the write side.** Only the *readback* side is still
  a fixed, hard-coded set of six named fields (`CockpitSwitchState`/`push_cockpit_switch_state`),
  and that is the one piece this plan does have to generalise (Stage 3).
- **The replace()-only, one-construction-site discipline** `GuidanceUnitState` already follows
  (plan `plans/9k113-effectors/plan.md`'s "Construction-site check") is reused verbatim for the new
  `EffectorRunState`.
- **The tuning-loader pattern** (`src/tuning.py`, lazy singleton resolved once) is the model for
  how the registry/sequence files are loaded once per process — but see Decision 2 below for why
  the *failure posture* is deliberately the opposite of `tuning.py`'s "never refuses to start."
- **The one-shot external-signal shape** `observ_transition`/`weapon_safety_transition` already use
  on `CrewConsole` (set by a handler, drained once by the poll loop) is unchanged — this plan
  replaces what the poll loop *does* with that signal (fire a registry trigger instead of writing a
  hard-coded switch), not the signal mechanism itself.
- **`render_unable`/`_UNABLE_TEMPLATES`** (`belief/speech.py`) and the existing
  `"GUIDANCE_NOT_READY"` refusal stay exactly where they are — gating is explicitly staying in code
  (explore-notes decision 3).
- **Query results** (`gq.sh`, `memory-search.py`): nothing beyond `explore-notes.md`, the concept
  doc, and BL-B66/BL-B90's own roadmap entries — no undiscovered prior plan on this ground. The one
  relevant memory hit, `reviewer`'s `project_terrain_callout_stage5_wiring_gap.md` (3rd occurrence,
  this same feature's own predecessor entry), is the reason this plan calls out explicit
  poll-loop-wiring tests in Stage 2/3 rather than trusting the engine's own pure-function tests —
  see "Risks & Unknowns".

No `investigator` pass is needed: this plan introduces no new DCS-internals claim.
`GetDevice(0):get_argument_value(arg)` (the generic, device-independent read already used for
874/876/the six switch args today) is the one read primitive Stage 3 needs, and it is already
live and confirmed in `Export.lua`.

---

## Affected Modules / Files

**body-layer (new)**

- `src/belief/effector_registry.py` — **new.** Loads and validates `config/effectors.toml`: a flat
  table of named effectors, each `{device: int, cmd: int, arg: int, values: {name: float, ...},
  unverified: bool = false}`. Pure, no I/O beyond reading the one file.
- `src/belief/effector_sequences.py` — **new.** Parses `config/effector-sequences/*.md` into
  `SequenceDef`s keyed by `(aircraft, role, EffectorTrigger)` read from each file's own header
  table (not from the filename), validated against the loaded registry (unknown effector/value
  name, unknown trigger string, malformed row, duplicate `(aircraft, role, trigger)` across two
  files) — see "File formats" below for the exact grammar.
- `src/belief/effector_engine.py` — **new.** The runtime: `EffectorRunState` (frozen,
  `replace()`-only, one construction site — see Co-moving Fields), `EffectorTrigger` (the code
  enum, five members this cut), `fire_trigger`, `advance`, `drain_say_lines`, `refresh_readback`,
  `is_complete(trigger)`. Replaces `sight_effector.py`'s sequencing half (`GuidanceUnitState`,
  `start_power_up`/`advance_power_up`, `sight_ready`, `write_observ`/`write_weapon_safety`) — see
  "What moves, what stays" below for the split.
- `config/effectors.toml` — **new, committed** (this is authoritative behaviour-defining data, not
  a user override like `config/tuning.toml` — it lives beside `config/defaults.toml`, not
  `.gitignore`d).
- `config/effector-sequences/mi-24p-copilot-takeoff.md`,
  `…-observ-on.md`, `…-observ-off.md`, `…-weapons-arm.md`, `…-weapons-safe.md` — **new, committed.**
  Content reproduces BL-B66's current hard-coded behaviour exactly (same switches, same order, same
  values, same callout) — see "Behaviour parity" below.

**body-layer (changed)**

- `src/logger.py` — `ConsolePerceptionRunner.guidance_unit_state: GuidanceUnitState` replaced by
  `effector_state: EffectorRunState`; the takeoff rising-edge block, the OBSERV on/off block, and
  the weapons-safety block (currently ~L3120–3282, see "What already exists") each shrink to a
  `fire_trigger(...)` call plus the existing `advance`/`refresh_readback`/`drain_say_lines` calls
  every poll; `crew_console.sight_ready` is refreshed from `effector_engine.is_complete(TAKEOFF)`
  instead of `sight_effector.sight_ready(state)`. `_reset_mission_state` gains one new line: resend
  `set_watch_args` after a mission (re)start (Stage 3) — flagged explicitly because nothing else in
  the existing reset list touches aircraft-layer-side state, only in-process dataclasses.
- `src/belief/crew_console.py` — `_handle_observ_on`'s `self.sight_ready` gate is unchanged in
  *shape* (still a plain bool field refreshed every poll); `_handle_observ_on`/`_handle_observ_off`/
  `_handle_weapons_armed`/`_handle_weapons_safe`/`_handle_engage` each still set the same one-shot
  `observ_transition`/`weapon_safety_transition` fields they do today — **no change to this file's
  public surface**, only to what the poll loop does with those signals.
- `src/tuning.py` / `config/defaults.toml` — `GUIDANCE_UNIT_SWITCH_DELAY_S` renamed/moved to
  `belief.effector_engine.EFFECTOR_SEQUENCE_STEP_DELAY_S` (same value `1.0`, same `lo=0.5, hi=5.0`),
  since it now gates every sequence file's inter-row delay, not only the guidance-unit power-up —
  regenerate `config/defaults.toml`.
- `src/belief/sight_effector.py` — shrinks to the Stage 4b slew-telemetry half only:
  `sight_az_raw`/`sight_elev_raw` readback + `sight_azimuth_raw_to_deg`, carried in a slimmer
  `SightPositionState` (or kept inline on whatever replaces it — Implementer's naming call). The
  switch-sequencing half (everything else in the file today) is deleted, not kept as dead code.

**aircraft-layer (Stage 3 only)**

- `dcs-export/Export.lua` — new `"watch_args"` op on the existing inbound command listener
  (`handle_watch_args_command`): replaces a module-level `watched_args: int[]` table. New
  `push_watched_args_state(t)`, throttled to its own slower cadence (a `last_watched_args_export_t`
  gate, same shape as the existing 5 Hz telemetry throttle, but looser — e.g. 1 Hz), reading every
  arg in `watched_args` via `GetDevice(0):get_argument_value(arg)` generically, change-epsilon per
  arg (reuse `COCKPIT_SWITCH_EPSILON`'s value), sent as `{"t": ..., "args": {"<arg>": <value>, ...}}`.
  **874/876 and `push_cockpit_switch_state` are untouched** — Stage 3 only generalises the six
  switch args' readback, not the sight-position readback `BL-B80` needs per-frame.
- `src/schema/watched_args.py` — **new.** `WatchedArgsState` (dual-clock provenance +
  `values: dict[int, float]`), parse/`to_api_dict`.
- `src/collector/cache.py` — `WatchedArgsCache` (most-recent snapshot, mirrors `TelemetryCache`'s
  shape).
- `src/collector/command_sender.py` — `send_watch_args(args: list[int])`.
- `src/api/server.py` — `POST /command/watch_args` (`{"args": [...]}`), `GET /watched_args/latest`.
- `src/schema/cockpit_switch.py` — the six named switch fields (`missl_pw`/`cplr_distr`/`sight_pw`/
  `scho_pw`/`observe`/`weap_safe` and their `*_on` properties) are removed; `sight_az`/`sight_elev`
  stay. Rename the class if the Implementer judges `CockpitSwitchState` misleading once it only
  carries sight position — grep every reference first.

**body-layer (Stage 3 only)**

- `src/aircraft_client.py` — `set_watch_args(args: list[int]) -> None` (raises — this is a
  structural "the watch list must be correct" write, same posture as `write_cockpit_switch`) and
  `get_watched_args_latest() -> dict[int, float] | None` (swallow-to-`None`, every other `get_*`'s
  posture).
- `src/belief/effector_engine.py`'s `refresh_readback` reads this dict (keyed by arg number),
  maps each arg back to its owning effector name via the registry, and sets `observed_values[name]`
  (boolean-decided at `>= 0.5`, the existing switch-threshold convention) — **absence leaves the
  prior value**, same posture `GuidanceUnitState.refresh_readback` already has today.

---

## File formats

**Registry — `config/effectors.toml`** (TOML; explore-notes' own proposed shape, confirmed — no
objection was raised and TOML is this project's existing format for exactly this kind of flat,
human-editable, typed table, `config/defaults.toml`/`config/tuning.toml`):

```toml
[effectors.missile_power]
device = 6
cmd = 3028
arg = 773
values = { on = 1.0, off = 0.0 }

[effectors.cplr_distr]
device = 16
cmd = 3015
arg = 761
values = { on = 1.0, off = 0.0 }
unverified = true   # see docs/acceptance/2026-10-17-9k113-procedures-direction.md

[effectors.sight_power]
device = 7
cmd = 3001
arg = 885
values = { on = 1.0, off = 0.0 }

[effectors.scho_pwr_b1]
device = 6
cmd = 3030
arg = 955
values = { on = 1.0, off = 0.0 }

[effectors.observ]
device = 7
cmd = 3002
arg = 886
values = { on = 1.0, off = 0.0 }

[effectors.weapon_safety]
device = 6
cmd = 3020
arg = 673
values = { armed = 1.0, safe = 0.0 }
```

**Sequence files — `config/effector-sequences/*.md`** (markdown tables, the concept's own shape,
confirmed by explore-notes point 6 — "user accepted the registry, did not object to the markdown
sequences"). Two tables per file, in order:

1. A 2-column header table (`file-param | for`) with exactly the rows `aircraft`,
   `petrovich-role`, `run-on-trigger` — **this header, not the filename, is the loader's key** for
   duplicate detection.
2. A data table, columns `condition (optional) | effector | value | petrovich-says (optional) |
   comment (optional)`. Each row is one of:
   - a **switch row**: `effector`/`value` name a registry entry and one of its `values` keys;
     `condition`, if present, is `<effector> = <value>` or `<effector> != <value>`, evaluated
     against this engine's own **commanded** state (never a DCS readback — see Decision 3), and a
     false condition skips the row entirely (no write, no delay, falls through to the next row the
     same poll);
   - a **wait row**: `condition` column holds `wait_s(<n>)` and every other column is blank — sets
     the delay before the next row to `<n>` seconds, overriding (not adding to) the default
     inter-row delay for that one gap (Decision 4).

Example, reproducing BL-B66's current takeoff sequence exactly:

```markdown
| file-param | for |
| --- | --- |
| aircraft | Mi-24P |
| petrovich-role | copilot |
| run-on-trigger | takeoff |

| condition | effector | value | petrovich-says | comment |
| --- | --- | --- | --- | --- |
| | missile_power | on | | MISSILE POWER |
| | cplr_distr | on | | CPLR DISTR -- unverified, see registry |
| | sight_power | on | | Sight Power (GUID.UNIT POWER) |
| | scho_pwr_b1 | on | Guidance unit ready. | SHCHO PWR B1 |
```

Validation (all fatal at startup, per Decision 2): unknown effector name, unknown value name for
that effector, unknown trigger string, a row that is neither a valid switch row nor a valid
`wait_s(n)` row, and more than one file claiming the same `(aircraft, role, trigger)` triple.

---

## What moves, what stays

| Concern | Today (`sight_effector.py`) | After this plan |
|---|---|---|
| Which switches, in what order, what values | Hard-coded `_POWER_UP_SWITCHES` tuple + two more hard single writes | `config/effectors.toml` + `config/effector-sequences/*.md` |
| Inter-switch delay | `GUIDANCE_UNIT_SWITCH_DELAY_S` | `EFFECTOR_SEQUENCE_STEP_DELAY_S` (same value, renamed — now generic) |
| "Is the takeoff sequence done" | `GuidanceUnitState.sight_ready` | `effector_engine.is_complete(EffectorTrigger.TAKEOFF)` |
| "Guidance unit ready" callout | Hard-coded in `CrewConsole.drain_guidance_unit_ready` | The sequence file's own `petrovich-says` column, spoken through the **same** `CrewConsole._print` path `drain_guidance_unit_ready` already uses — no new speech mechanism (task brief's explicit requirement) |
| OBSERV-on readiness gate | `_handle_observ_on` checks `self.sight_ready` | **Unchanged** — still checks `self.sight_ready`, now refreshed from `is_complete(TAKEOFF)` instead of `sight_ready(state)`. Gating logic itself never moves into a file (explore-notes decision 3) |
| Weapons armed/safe refusal logic | None today (unconditional) | None — stays that way; this plan adds no new gate |
| Sight-position readback (874/876), slew telemetry | `GuidanceUnitState.sight_az_raw`/`sight_elev_raw`, `sight_azimuth_raw_to_deg` | **Unchanged, verbatim** — `BL-B80`'s concern, out of scope, carried in whatever `sight_effector.py` shrinks to |

---

## Co-moving Fields

Step 6a's trigger fires: the new engine's internal sequencing state and `CrewConsole`'s
externally-written signal fields both track "has the pilot's command taken effect," the same shape
BL-B66's own plan already had to reason about for `GuidanceUnitState`/`OpticState.home_phase` — this
plan must not let that divergence reopen while renaming the fields underneath it.

| Field | Written by | Transition | Must hold true immediately after |
|---|---|---|---|
| `EffectorRunState.pending`/`active_*` | internal (`effector_engine`) | any `fire_trigger` call | the trigger is either started immediately (queue was idle) or appended to the per-trigger queue — never dropped |
| `EffectorRunState.commanded_values[name]` | internal (`advance`, on a successful write) | each row executed | updated to that row's value; a later row's `condition` in *any* file reads this, never a DCS readback (Decision 3) |
| `is_complete(TAKEOFF)` (via `crew_console.sight_ready`) | internal, refreshed every poll | last row of the takeoff sequence executes | `True`; `_handle_observ_on`'s gate reads this value, unchanged shape from today |
| `home_phase` | **external** (pilot "Observ on"/"Observ off" via `crew_console`) | OBSERV-on/off request | **if `sight_ready` was `False` at request time: unchanged, refused, `fire_trigger(OBSERV_ON)` never called.** If `True`: `home_phase` set exactly as `BL-B64`/`BL-B66` already do — this plan adds no new branch inside `decide()` |
| `observ_transition`/`weapon_safety_transition` | **external** (`crew_console` handlers) | pilot command | drained once by the poll loop into exactly one `fire_trigger(...)` call, then cleared to `None` — same one-shot-signal discipline as today, unchanged |
| `EffectorRunState.observed_values[name]` | **external** (aircraft-layer watched-args readback, Stage 3) | any readback poll | lags the commanded value by the same ~3-frame animation BL-B66 already documents; **no consumer in this entry reads it**, carried for `BL-B67` exactly as `observ_observed`/`weapon_safety_observed` are today |

**Construction-site check, grepped not narrated**: `EffectorRunState(` must have exactly one
construction site (`ConsolePerceptionRunner`'s `field(default_factory=EffectorRunState)` plus
mission-reset's `__init__` re-run) — every function in `effector_engine.py` returns `replace(state,
...)`. State this explicitly in the Implementer handoff, since the predecessor plan's own worked
example (`BL-B71`'s two silent fresh-construction sites) is exactly the failure mode a "build a
fresh run-state for sequence X" helper would reintroduce under time pressure.

---

## Implementation Plan

**Stage 1 — registry + sequence loader, pure.** `effector_registry.py`, `effector_sequences.py`,
the committed `config/effectors.toml` and five `config/effector-sequences/*.md` files reproducing
BL-B66's current behaviour exactly. Every validation rule above enforced with a dedicated test
(unknown effector, unknown value, unknown trigger, malformed row, duplicate triple, a well-formed
file round-tripping to the expected `SequenceDef`). No body-layer wiring yet, no DCS.

**Stage 2 — the engine, wired in (write side only, no aircraft-layer change).** `effector_engine.py`
(`EffectorRunState`/`fire_trigger`/`advance`/`drain_say_lines`/`is_complete`), driving writes
through the **existing** `aircraft_client.write_cockpit_switch` (already generic, no new wire
format needed). `logger.py`'s takeoff/OBSERV/weapons-safety blocks rewired to call `fire_trigger`
instead of the hard-coded `sight_effector` functions; `sight_effector.py`'s sequencing half deleted.
**Test the real poll loop, not only the engine's pure functions** — `reviewer`'s own
`project_terrain_callout_stage5_wiring_gap.md` names this exact wiring-into-the-poll-loop seam as a
3-times-recurring defect class on this project, most recently on this same feature's predecessor
(BL-B66). Reuse `test_logger.py`'s existing `_run_crew_text_poll_loop`-driving tests (the ones the
BL-B66 review required) as the template rather than writing new pure-function-only coverage and
calling it done.

**Stage 3 — generic low-rate readback.** `Export.lua`'s `watch_args` op + `push_watched_args_state`;
aircraft-layer schema/collector/API; `aircraft_client.set_watch_args`/`get_watched_args_latest`;
`effector_engine.refresh_readback`; `logger.py` sends `set_watch_args` once at startup (after the
registry loads) and again on every detected mission (re)start. **Needs a Windows redeploy** — the
only stage that does. Best-effort/retried posture for the push itself (not the file validation):
a `set_watch_args` call failing because aircraft-layer/DCS is not yet running is the ordinary
"not connected yet" case every other `aircraft_client` call already tolerates, not a startup
failure — retried every poll until it lands, never fatal.

**Stage 4 — cleanup and parity check.** Remove `GuidanceUnitState` and every now-dead reference;
confirm (by a diff of `cockpit_switch_writes` test assertions before/after) that the five sequences
produce byte-identical device/cmd/value writes in byte-identical order with the byte-identical
1.0 s spacing BL-B66's own tests already pin. Regenerate `config/defaults.toml` for the
renamed tuning key.

**Stages 1–2 are built back to back** (Stage 2 needs Stage 1's loader); **Stage 3 is a separate
batch** (it is the one stage gated on a Windows redeploy and may land later) — one performance
pass and one security pass after whichever batch actually ships together, per root `CLAUDE.md`'s
current cadence, not one per stage.

**No separate acceptance sortie is scoped for this plan** — "Behaviour after the change must be
identical to the current hard-coded build" (task brief) means the acceptance bar is parity against
BL-B66's own already-flown Stage 5 card, re-run quickly (take off, hear "Guidance unit ready," say
"Observ on"/"Observ off," say "weapons armed"/"weapons safe") rather than a new multi-minute test —
flagged under Decisions in case the user wants a dedicated card instead.

---

## Invariants checked

- **DCS is authoritative; code owns factual state.** Conditions in sequence files read the
  engine's own commanded state, never a DCS readback — see Decision 3; this keeps the "code owns
  truth" line exactly where BL-B66 already drew it, rather than letting a config file encode a
  judgement about live aircraft state.
- **Never modify the DCS installation.** Every write stays the existing `performClickableAction`
  path; Stage 3 adds a read-only `get_argument_value` loop, also already in use.
- **Module independence.** aircraft-layer ↔ body-layer stays HTTP/JSON; no new in-process coupling.
- **No new abstraction without a named duplication removed.** The registry/sequence split removes
  the duplication BL-B66 itself flagged as a cost of its own design: five near-identical blocks of
  "write this switch, wait, write the next" hand-written in `logger.py` and `sight_effector.py`
  collapse into one engine driven by data.
- **Single-player only.** No group/coalition scoping anywhere in this entry.

---

## Risks & Unknowns

- **Startup-fatal validation is a deliberate, stated departure from `tuning.py`'s "never refuses to
  start" posture** (Decision 2) — a malformed sequence file is a build-breaking error at body-layer
  launch, by explicit user direction ("I'd rather a check at startup and error than finding out in
  middle of flight"). Flag this loudly in the error message so it reads as expected behaviour, not
  a regression, the first time someone hits a typo in a markdown table mid-editing.
- **The queue-scope question (Decision 1) is the one place this plan's reading of explore-notes
  could be wrong** — per-trigger queuing (this plan's choice) versus a single global queue (the
  explore-notes' literal wording) produce different, observable behaviour the moment two different
  triggers' sequences overlap in time (e.g. "weapons armed" said while the takeoff power-up is
  still mid-sequence). Needs the user's confirmation before Stage 2, not a silent pick.
- **The predecessor feature's own recurring defect class — leaf logic unit-tested, poll-loop wiring
  not** — is specifically guarded against in Stage 2's own instructions above, not left to Reviewer
  to find a fourth time.
- **761 (`cplr_distr`) stays UNVERIFIED**, carried through unchanged from BL-B66 into the registry's
  `unverified = true` field — this plan does not re-open or re-settle that question.
- **Stage 3's Windows redeploy is the one piece of this plan that cannot be verified without a live
  DCS session** — if Stage 3 ships separately from Stages 1-2, the committed sequence files still
  work end to end on the write side alone; Stage 3 only removes the last piece of hard-coding on the
  *read* side, so splitting it off is safe, not a half-finished feature.

---

## Second-order effect

Makes the next cockpit-effector sequence (any new trigger, any new switch) a config change rather
than a code change — the explicit point of the feature. It also sets the pattern `BL-B67`'s own
ATGM-run writes (launch-station selector, the ARMED check) would want to follow rather than growing
their own one-off sequencing code, and gives `BL-B80`'s slew-loop tuning a stable, unrelated home
(`sight_effector.py`'s shrunk remainder) that this refactor does not disturb.

---

## Decisions Requiring User Input

1. **Queue scope: per-trigger (this plan's choice) or global, single-engine queue (explore-notes'
   literal wording)?** Per-trigger preserves BL-B66's exact current timing (a "weapons armed" said
   mid-power-up still writes immediately, as it does today); a global queue would delay it behind
   the power-up's remaining switches, a real behaviour change the "must be identical" requirement
   argues against. **Recommend per-trigger.**
2. **TAKEOFF's one-shot-per-mission latch vs. the concept doc's own trigger table, which lists
   `takeoff` as "every time."** BL-B66's current code is one-shot-per-mission (a second takeoff/
   touch-and-go does not re-run the power-up or re-speak "ready"); this plan keeps that, as a
   stated, trigger-specific departure from the concept table's generic cardinality, because
   "identical behaviour" is the explicit bar for this cut. **Recommend keeping TAKEOFF one-shot**;
   flagged because the concept doc (not binding, "concept not final truth") says otherwise and a
   future reader should not assume the table is simply unimplemented.
3. **Fatal-at-startup validation (no "warn and run on defaults" fallback, unlike every tunable
   constant)** — confirmed by explore-notes point 6, restated here as the one place this plan
   deliberately contradicts the project's otherwise-universal "never refuse to start" tuning
   posture. **Recommend confirming this is still wanted**, since it is a different failure mode from
   anything else in body-layer today: a typo in a markdown table now stops the whole process, not
   just one constant.
4. **No dedicated Stage 5 acceptance sortie card** — this plan treats BL-B66's own Stage 5 card as
   sufficient re-verification once this refactor lands, since the goal is byte-identical behaviour.
   **Recommend confirming**, or say if a short re-flight card should be written anyway.
