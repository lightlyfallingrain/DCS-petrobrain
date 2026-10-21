# BL-B66 — The 9K113 sight, entry 2 of 3: effectors (REVISED, 2026-10-21, narrowed scope)

Architect revision pass. **Supersedes everything below the `---` divider at the end of this file**
(the 2026-10-15 plan plus its 2026-10-17 probe addenda) — kept there only as history; do not plan
against it. What changed and why is in git history (`feature/9k113-effectors`) and in
`plans/9k113-effectors/explore-notes.md`, which is authoritative over this file where they could
ever conflict.

**Precedence:** `plans/9k113-effectors/explore-notes.md` (user's own words, 2026-10-21) >
`docs/acceptance/2026-10-17-9k113-procedures-direction.md` > `body-layer/ROADMAP/BL-B66.md` >
this plan's own text.

### Goal

Make the 9K113's guidance-unit power-up, OBSERV on/off, and the weapons safety bar into real
cockpit writes instead of only body-layer bookkeeping — so the switches the pilot sees in the
cockpit actually move, on Petrovich's own initiative where the user said they should, and the
sight head (slewing, aiming) is explicitly **not** this entry's problem.

### Scope, restated from the narrowing

**In:** the cockpit-action channel (a new, general, reusable sequenced-switch-write facility);
the four-switch guidance-unit power-up, autonomous after takeoff, ending in one callout; OBSERV
on/off as a real cockpit write, gated on readiness; the weapons safety bar (ARMED/SAFE).
**Out:** the slew loop, the slew-time model, pinpoint, the ATGM run, L166V POWER, gyro-topple
modelling — all `BL-B80`/`BL-B67`'s. `advance_sight_aim` stays the pass-through `BL-B80.md`
confirms it keeps.

---

## 0. Transport: investigator findings in, Decision 1 stays the user's to make

**The user independently asked whether [DCS-BIOS](https://github.com/DCS-Skunkworks/dcs-bios)
should carry this channel instead of a new `Export.lua` op.** An `investigator` pass ran in
parallel and has reported: `aircraft-layer/research/2026-10-21-dcs-bios-mi24p-9k113-controls.md`
(on `feature/9k113-effectors` as commit `c5b3fa2d`). Treated as evidence, not instruction, per this
role's standing rule — the findings below are facts to plan against, the recommendation is carried
but the decision itself is left to the user (Decision 1).

**What it found, and why none of it changes Stages 2–5 below:**

- **Every argument number this plan already commits to is independently corroborated.** 773, 885,
  886, 955, 956, 673, 874, 876 all match DCS-BIOS's own Mi-24P module survey exactly — "none
  disagree." **761 is corroborated too**: DCS-BIOS maps it as `OP_USR_PW`, device 16 (`ASP17`),
  command 3015 — the same device family (ASP-17) the procedures-direction note's own physical-layout
  reasoning already landed on, from a second, independent source. **Still "corroborated," not
  "confirmed"**: DCS-BIOS's own description ("USR power") does not establish that `USR` means
  coupler/distributor — the read-probe on the acceptance sortie (Risks & Unknowns) still settles it,
  unchanged by this finding.
- **The `READY`/`READNS.` lamp still has no known draw argument.** DCS-BIOS maps `SCHO READY` (960,
  the *weapon* system's ready lamp, not the sight's), `SHTV READY` (917), and `L166B WORK`/`FAIL`
  (868/869) — none of these is the sight's own post-warm-up readiness lamp. DCS-BIOS's own
  exhaustive-looking coverage of minor tablo lights makes a genuine gap *less* likely than usual, but
  does not prove one — the note's own recommended next step (a brute-force `get_argument_value` scan
  across ~2000 args, diffed before/after a real warm-up) is out of this entry's scope (zero
  real warm-up, by standing direction) and is not needed to ship Stages 2–5. **§3's readiness seam
  keeps the slot regardless**: `sight_ready` reads one field of `GuidanceUnitState` that stays
  `None`/unused until something — a future lamp-read attempt, real or DCS-BIOS-sourced — populates
  it.
- **DCS-BIOS cannot drive the player slew axis (3025/3026) at all** — no clickable control exists
  for it in the Mi-24P module, and DCS-BIOS's command protocol only ever wraps named, pre-defined
  controls, never a generic device/command/value passthrough. Out of this entry's scope (`BL-B80`'s
  problem), but it rules out "adopt DCS-BIOS wholesale and get the slew loop for free" as a reason
  to prefer it here.
- **Recommendation carried from the investigator: reference-only, not a runtime dependency.**
  GPL-3.0 licensing, a second install step for a public stranger-facing project, and a second
  project's own patch-tracking cadence, for a switch set this project can already read and write
  through its own Export.lua today — set against a cross-check value (confirming the eight arg
  numbers above) that is already fully captured by *having asked the question once*, with no
  install required. **This plan adopts that recommendation for Stage 1** (write the new
  `Export.lua` op as planned) but Decision 1 restates it as the user's call, not a default silently
  acted on.

**Why none of this blocks writing the plan or changes Stages 2–5's shape.** `sight_effector.py`
(new, body-layer) is the one module that knows device/arg/command numbers; everything above it —
`CrewConsole`, `logger.py`, `OpticState` — talks to it in terms of "write guidance-unit switch N
to ON/OFF" and "is the sight ready", never in terms of `performClickableAction` or a wire format.
Below `sight_effector.py`, `aircraft_client.AircraftLayerClient` is body-layer's existing HTTP
boundary to aircraft-layer, and aircraft-layer's own API (`POST /command/cockpit_switch`, Stage 1)
is a stable *contract* that would not change shape even if a future decision reversed Decision 1.

---

## 1. What already exists, and what this entry reuses rather than invents

**Query results** (`gq.sh`, `memory-search.py`): nothing beyond what `explore-notes.md` and the
2026-10-17 probe docs already record — no undiscovered prior plan on this ground, and the only
memory hits were this role's own general process memories (verify brief status claims, find N
before trusting it, do not reinvent the wheel), not project-specific prior art on cockpit switch
sequencing.

- **The cockpit-write pattern is the SPU-8 one** (`Export.lua` lines ~480–577): a single
  `performClickableAction(cmd, value)` write, a change-epsilon telemetry readback
  (`push_spu8_state`, `SPU8_EPSILON = 0.01`) sent only when a value actually moved. This entry's
  switch states (0/1, animating over ~3 frames per the 2026-10-17 probe) are the same shape, one
  tier simpler (no continuous knob).
- **The inbound-command pattern is `poll_command_socket`** (`Export.lua` lines ~660–677,
  `handle_petrovich_search_command`): a small `{"op": ..., ...}` JSON datagram over the existing
  loopback UDP command socket, dispatched by `op`. Stage 1 adds one more `op` here, not a new
  socket.
- **The raise-on-failure HTTP write pattern is `trigger_petrovich_search`**
  (`aircraft_client.py` lines ~260–269): a real cockpit effector write raises `AircraftLayerError`
  on failure rather than being swallowed, unlike the opaque-display-string writes
  (`push_text_line`). This entry's switch write is the same class of call — a dropped write is a
  real behavioural gap — and follows that posture.
- **The one-shot external-signal pattern is `attack_run_transition`/`observ_transition`**
  (`crew_console.py`): a command handler sets a `Literal[...] | None` field for the poll loop
  (`logger.py`) to apply once, because `CrewConsole` cannot reach `ConsolePerceptionRunner`'s state
  directly. The weapons-safety-bar command uses the same shape (§4).
- **`render_unable`/the "unable, `<reason>`" template dict already exists**
  (`belief/speech.py`, `_UNABLE_TEMPLATES`, e.g. `"ON_GROUND": "Unable, on the ground."`) — the
  refusal wording for OBSERV-before-ready (§3) is one more entry in that dict, not a new mechanism.
- **The X-T26 tuning pattern** (`src/tuning.py` accessors, `config/defaults.toml` generation) is
  reused for every new constant below — none of them are hand-rolled literals.
- **`on_ground` on `CrewConsole`** (`logger.py` ~L3069–3073, refreshed every poll from
  `runner.last_ownship_state.alt_agl_m`) is the existing takeoff-adjacent signal this entry reads
  for the power-up trigger (§2), not a new telemetry field.
- **`optic_policy.py` is untouched by this entry.** `OpticState`/`decide()` carry no cockpit
  knowledge today and this plan keeps it that way — see §3's own note on why the readiness gate
  belongs in `CrewConsole`, one layer up, not inside the phase-cycle state machine `BL-B64`/`BL-B71`
  already hardened.

---

## Affected Modules / Files

**aircraft-layer**

- `dcs-export/Export.lua` — one new `op` (`"cockpit_switch"`) on `poll_command_socket`'s existing
  dispatch, writing via `GetDevice(device):performClickableAction(cmd, value)` for **any**
  `(device, cmd, value)` — validated for *shape* only (integers / a finite number), **no allow-list
  of switches. User direction 2026-10-21, overriding the security plan review's required fix:**
  *"Allow any cockpit switch. That gives us much more freedom later and even now with
  experimenting. This is LAN only and switch behaviour is limited to DCS."* This is a deliberate,
  stated departure from `aircraft-layer/CLAUDE.md`'s "no general-purpose remote-exec surface"
  line, which is amended to name it; the command socket itself stays loopback-only and the HTTP
  API is the LAN surface, as for every other write path. Every write is debug-logged. A new
  `push_cockpit_switch_state` telemetry push (SPU-8's change-epsilon shape) for the six args this
  entry cares about (773, 761, 885, 955, 886, 673). Flag-gated debug logging (`debug_log`, already
  the file's own convention) on every write and every state-change push, from the first commit —
  not bolted on after a failed sortie.
- `src/collector/command_sender.py` — a `send_cockpit_switch(device, cmd, value)` method,
  structurally identical to `CommandSender.send_command`, same `CommandSendError` posture.
- `src/collector/cache.py` — a small cache for the six-arg switch-state snapshot, mirroring
  `TelemetryCache`'s shape (most-recent-sample, not a queue — a switch's state is a level, not an
  event).
- `src/api/server.py` — `POST /command/cockpit_switch` (`{"device", "cmd", "value"}`, `400` on a
  malformed body, `500`/raise on a send failure — `/command/petrovich_search`'s own posture) and
  `GET /cockpit_switch/latest` (the six-arg snapshot, `None` on an empty cache — every other
  `/latest` endpoint's posture).
- `src/schema/` — a `CockpitSwitchState` record (six named floats) alongside the existing
  per-channel schemas.

**body-layer**

- `src/aircraft_client.py` — `write_cockpit_switch(device, cmd, value)` (raises, mirrors
  `trigger_petrovich_search`) and `get_cockpit_switch_state_latest()` (swallow-to-`None`, mirrors
  every other `get_*`).
- `src/belief/sight_effector.py` — **new.** The one boundary below which nothing above knows a
  device/arg/command number. Holds:
  - `GuidanceUnitState` (frozen dataclass, carried on `ConsolePerceptionRunner` the same way
    `optic_state`/`attack_run_state` are): power-up progress, `sight_ready`, `observ_commanded`/
    `observ_observed`, `weapon_safety_commanded`/`weapon_safety_observed`.
  - The four-switch power-up sequencer (one write per `advance()` call, spaced by
    `GUIDANCE_UNIT_SWITCH_DELAY_S`).
  - `sight_ready(state) -> bool` — the readiness predicate, §0's named seam.
  - `write_observ(on: bool)` / `write_weapon_safety(armed: bool)` — single writes, no sequencing.
- `src/logger.py` — a `guidance_unit_state` field on `ConsolePerceptionRunner`, advanced once per
  poll beside the existing `optic_state`/`attack_run_state` handling (same call site, ~L3085–3123);
  `crew_console.sight_ready` refreshed every poll the same way `crew_console.on_ground` is
  (~L3069–3073); a new one-shot `weapon_safety_transition` applied the same way `observ_transition`
  is.
- `src/belief/crew_console.py` — `_handle_observ_on` gated on `self.sight_ready`, returning
  `render_unable("GUIDANCE_NOT_READY")` when not; new `_handle_weapons_armed`/`_handle_weapons_safe`
  handlers setting `weapon_safety_transition`; `_handle_engage` (existing) also sets it to
  `"armed"` alongside its existing `attack_run_transition = "engage"`.
- `src/belief/speech.py` — one new `_UNABLE_TEMPLATES` entry, `"GUIDANCE_NOT_READY": "Unable,
  guidance unit not ready."`
- `src/tuning.py` / `config/defaults.toml` — `GUIDANCE_UNIT_SWITCH_DELAY_S` (default `1.0`, the
  measured ~3-frame animation plus margin, `lo=0.5, hi=5.0`), and the takeoff-trigger threshold if
  it needs its own constant beyond the existing `ON_GROUND_AGL_THRESHOLD_M` (see §2).

**Cross-subproject (voice)**

- `audio-adapter/src/vocabulary.py` — two new `VOICE_ONLY_TOKENS` entries, `weapons_armed`/
  `weapons_safe`, with `PHRASES` entries ("weapons armed", "weapons safe" — user direction 2026-10-21; *"weapons
  on/off"* dropped). **Not added to the F10 menu** — root `CLAUDE.md`/`vocabulary.py`'s own docstring: voice
  is primary, the F10 vocabulary is the legacy, non-growing one (2026-09-19 direction). Checked,
  per the task brief's instruction to check; the answer is "voice only, by existing precedent."

**Docs / roadmap**

- `body-layer/ROADMAP/BL-B66.md` — amended with this plan's narrowed scope and Decision 1.
- `body-layer/ROADMAP/BL-B65.md` — already closed/folded; no change needed.

---

## 2. The takeoff trigger, and the "already on" / landing questions

**Reuses `on_ground`'s existing signal** (`alt_agl_m <= ON_GROUND_AGL_THRESHOLD_M`), not a new
telemetry field. The power-up sequencer fires once on the **rising edge** of "was on the ground,
now is not" this mission — `GuidanceUnitState` carries a `takeoff_seen: bool` one-shot latch,
reset by the existing mission-restart machinery (`_reset_mission_state`/`reset_for_new_mission`,
same list every other per-mission field is already on).

**Hot start / switches already on (explore-notes' open question 1): no special case.** Every
switch write in this entry is `performClickableAction(cmd, 1)` — an absolute set, not a relative
toggle (confirmed by the 2026-10-17 probe's own restore pass, which drove the same switches back
to 0 cleanly). Re-asserting an already-ON switch is a no-op in the cockpit and costs one harmless
write per switch. **Proposed answer, not re-opening a decision**: no hot-start detection needed.

**Landing (explore-notes' open question 2): proposed answer — do nothing.** Nothing in the user's
procedure direction powers the unit down, and modelling a power-down is new scope with no stated
behaviour to build against. `GuidanceUnitState` stays `READY` for the rest of the mission once
reached; a second takeoff (touch-and-go) does not re-run the sequence (the latch is one-shot per
mission, not per ground contact) — flagged as a choice, not a measured fact, in case a training
mission with multiple landings makes this wrong in practice.

---

## 3. Readiness, OBSERV, and why `optic_policy.py` is not touched

**`sight_ready` gates the command, synchronously, in `CrewConsole._handle_observ_on` — before
`observ_transition` is ever set.** This is deliberate and different from how `BL-B64`'s own
`home_phase`/`observ_observed`-shaped hazard would suggest handling it: that hazard is about a
*poll-lag* window between a command being accepted and the cockpit catching up. Gating the command
itself, at the moment it is spoken, removes the one case that would matter to belief state (a
`home_phase` that says SIGHTING while the sight was never going to engage at all) without adding
any new branch to `decide()`. `optic_policy.py` keeps `BL-B64`/`BL-B71`'s hardened invariants
exactly as they are.

**What is *not* removed by that gating: `observ_commanded` vs `observ_observed` lag.** Once a
command is accepted (`sight_ready` was `True`), the cockpit write for arg 886 still animates over
~3 frames before the readback agrees — the same lag `BL-B64`'s own table named for a different
field. No consumer reads `observ_observed` today (the 9K113 optic is deliberately deferred in
`optics.py`; nothing in perception resolves against it), so this is a **recorded risk for `BL-B67`
to inherit, not a defect to fix here**: whoever builds the ATGM run must read `observ_observed`
before trusting the sight is actually engaged, never `home_phase`. Stated here so it is not
rediscovered the way `BL-B64`'s own defect was.

**OBSERV OFF needs no gating and no sequence** — confirmed by the user's own procedure direction
(§2 of `docs/acceptance/2026-10-17-9k113-procedures-direction.md`): one write, DCS handles the
rest. `_handle_observ_off` is unchanged.

---

## Co-moving Fields

Step 6a's trigger fires: `GuidanceUnitState` and `OpticState.home_phase` both track "is the sight
usable," one external (pilot command, telemetry) and one internal (sequencer, `decide()`), and
they must not silently diverge the way `BL-B64`'s `phase`/`home_phase` did.

| Field | Written by | Transition | Must hold true immediately after |
|---|---|---|---|
| `takeoff_seen` | internal (`sight_effector`, from `on_ground`'s rising edge) | takeoff detected | `True`; power-up sequence starts this same poll |
| `power_up_stage` | internal (`sight_effector` sequencer) | each `GUIDANCE_UNIT_SWITCH_DELAY_S` tick while in progress | advances by exactly one switch; never skips a switch even if an earlier readback has not yet confirmed (zero-warmup direction: the *ordering* is structural, the *timing gates* are not) |
| `sight_ready` | internal (`sight_effector`, derived) | last switch write issued | `True` (zero real warm-up); the one seam a lamp-read or a real duration lands in later, per §0 |
| `guidance_unit_ready_announced` | internal (one-shot latch) | `sight_ready` becomes `True` | `True`; `"Guidance unit ready"` spoken exactly once, never once per poll |
| `home_phase` | **external** (pilot "Observ on", `crew_console._handle_observ_on`) | OBSERV-on request | **if `sight_ready` was `False` at request time: unchanged, request refused with `render_unable("GUIDANCE_NOT_READY")`, `observ_transition` never set.** If `True`: `home_phase` set to `SIGHTING` next poll exactly as `BL-B64` already does — this entry adds no new branch inside `decide()` |
| `observ_commanded` | internal (`sight_effector`) | OBSERV-on accepted | `True`; cockpit write for arg 886 issued exactly once |
| `observ_observed` | **external** (aircraft telemetry, arg 886 readback) | OBSERV-on accepted | **may still be `False` for up to ~3 frames** — nothing in this entry reads it, but `BL-B67` must, per §3 |
| `weapon_safety_commanded` | **external** (pilot "weapons armed"/"weapons safe") **or internal** (`_handle_engage`'s existing `attack_run_transition = "engage"` path) | either trigger | `ARMED`; both triggers converge on the same field, so an attack run started while already armed is a harmless re-write, never a conflicting state |
| `weapon_safety_observed` | **external** (aircraft telemetry, arg 673 readback) | any `weapon_safety_commanded` change | lags the commanded value by the same ~3-frame animation; no consumer reads it in this entry (recorded for `BL-B67`, which fires a real missile and should not trust an unconfirmed safety bar) |

**Construction-site check, per step 6a's own rule — grepped, not narrated from the transition
list**: `GuidanceUnitState(` has exactly one construction site in this plan's design
(`ConsolePerceptionRunner`'s `field(default_factory=GuidanceUnitState)`, mission-reset's
`reset_for_new_mission` re-running `__init__`) and the sequencer itself only ever calls `replace()`
on it, never a fresh `GuidanceUnitState(...)` mid-sequence — there is no second construction site
for the Implementer to introduce silently, unlike `OpticState`'s two (`BL-B71`'s own worked
example). State this explicitly in the Implementer handoff as the thing to keep true, since the
failure mode is adding a *second* construction site under time pressure (e.g. a "reset the
sequence" helper that looks easier to write as `GuidanceUnitState(...)` than as `replace(state,
...)`).

---

## Implementation Plan

**Stage 1 — the cockpit-action channel.** `Export.lua`'s `cockpit_switch` op (write) and
`push_cockpit_switch_state` (readback telemetry, change-epsilon, the six args named above);
aircraft-layer collector/API/schema; `aircraft_client.py`'s two new methods. Flag-gated debug
logging from the first commit. Testable without live DCS the same way every other aircraft-layer
write path is (`tests/test_api.py`'s real-server pattern) — live confirmation is the acceptance
sortie, same posture as SPU-8/BL-6.

**Stage 2 — the guidance-unit power-up.** `sight_effector.py`'s `GuidanceUnitState` and
sequencer; the takeoff trigger (§2); `sight_ready`; the "Guidance unit ready" callout wired through
`CrewConsole`'s existing per-poll drain. Testable against a fake `AircraftLayerClient` (no live
DCS), same as every other body-layer effector test.

**Stage 3 — OBSERV as a real cockpit write.** The readiness gate in `_handle_observ_on`
(§3); `observ_commanded`/`observ_observed` fields; the `GUIDANCE_NOT_READY` refusal template.
No change to `optic_policy.py`.

**Stage 4 — the weapons safety bar.** ARMED on `_handle_engage` (existing) or the two new voice
commands; SAFE on its own voice command; `weapon_safety_transition`; the vocabulary entries.

**Stage 4b — slew telemetry logging, for tuning `[[BL-B80]]`'s loop from data.** User direction,
2026-10-21: *"Put logging in so that the slew loop can be adjusted based on data from logs. Actual
vs desired angles especially, slew command values, etc."*

- **`Export.lua`, every frame, flag-gated** (its own debug flag, off by default): sim time, args
  **874/876** (actual sight azimuth/elevation, raw), OBSERV (886), and the **last slew command sent
  on 3025/3026** — always `nil` in this entry, since nothing writes the slew axis yet; the field is
  there so `BL-B80` fills it rather than adding a format. Per frame, because body-layer's 1 Hz poll
  cannot see a slew: the open `BL-B80` question is whether the readback is quantised, lagged or
  genuinely stepped, and only frame-rate samples separate those. Log only while OBSERV is on (or a
  short tail after it goes off) so an idle sortie does not fill the file.
- **body-layer, every poll: a sight trace `.jsonl`**, following `detection_trace_writer.py`'s
  pattern and the BL-11 Stage 5 per-sortie filename stamp: desired az/el (`OpticState`), actual
  az/el (readback when present, else the model's value, with a `source` field saying which), the
  error, OBSERV commanded/observed, optic mode (wide/narrow). Same flag posture as the other
  sortie traces.
- Raw arg values are logged alongside any degree conversion — elevation's conversion is still
  unmeasured, so a derived number alone could not be re-derived later.
- **`sortie-log-triage` gets a slew section** (rate during a slew, smallest observed step, lag) —
  skill edit, `.claude/skills/sortie-log-triage/`.

**What this buys: the hand-slew segment on the Stage 5 card** (user: *"Yes"*). Two minutes of the
pilot slewing the sight by hand while the frame log runs measures real rates, readback granularity
and lag — which is the "one more probe run" `BL-B80` lists as a hard dependency, collected for free.

**Stages 1–4 (and 4b) are built back to back** (Stage 2 needs Stage 1's channel to write through; Stage 3
needs Stage 2's `sight_ready`; Stage 4 reuses Stage 1's same channel for one more arg) — **one
performance-review pass and one security pass after Stage 4**, not one per stage, per the current
cadence in root `CLAUDE.md`'s "Agents" section.

**Stage 5 — acceptance sortie, one flight.** A card naming the branch and a sequence the user can
fly in one sortie: take off, confirm the four switches move and "Guidance unit ready" is heard;
try "Observ on" before and after that callout (expect a refusal, then acceptance); say "Observ
off"; say "weapons armed"/"engage" and "weapons safe", confirming arg 673's readback both ways.
**Then ~2 minutes of hand-slewing the sight in OBSERV** (full left/right, up/down, slow and fast)
with the slew frame log on — the data `BL-B80` needs (Stage 4b).
No gyro-reset risk and no multi-minute wait — the zero-warm-up direction makes this an ordinary
sortie, not the "~3 minutes per attempt" cost the pre-split entry carried.

---

## Invariants checked

- **DCS is authoritative about the simulated world.** Readbacks (arg 886/673/the four power-up
  args) are the source of truth for `*_observed` fields; `*_commanded` is a statement about what
  Petrovich asked for, never substituted for what DCS reports.
- **Never modify the DCS installation.** Every write is a runtime `performClickableAction` call
  against a running sim through the existing listener — no file in the DCS tree is touched.
- **Code owns factual state.** `sight_ready` is a predicate code evaluates against `GuidanceUnitState`;
  no model is asked whether the sight is warm.
- **Module independence.** aircraft-layer ↔ body-layer stays HTTP/JSON. §0's boundary is exactly
  what keeps the DCS-BIOS-vs-Export.lua question from ever reaching body-layer's import graph.
- **Single-player only.** No group/coalition scoping anywhere in this entry.
- **No new abstraction without a named duplication removed.** `sight_effector.py` earns its place
  the same way the 2026-10-15 plan argued for it: without it, device/arg numbers leak into
  `crew_console.py` and `logger.py`, and a transport change (§0) would touch every call site instead
  of one module.

---

## Risks & Unknowns

- **The transport is still formally an open decision (§0, Decision 1)**, though the investigator's
  findings now favour proceeding with Stage 1 as planned (own `Export.lua` op) — DCS-BIOS is
  recommended as reference-only, cannot drive the slew axis anyway, and does not solve the READY
  lamp. If the user nonetheless prefers DCS-BIOS as a runtime dependency, Stage 1 is the one stage
  that changes shape — the HTTP contract (`POST /command/cockpit_switch`, `GET /cockpit_switch/
  latest`) should still hold, but its aircraft-layer-side implementation would differ.
- **761 (`CPLR DISTR`) is corroborated by two independent sources (physical layout, DCS-BIOS's own
  device-16 mapping) but still not confirmed as to function** — built as planned, confirmed on the
  acceptance sortie by logging changed arguments while the user throws it by hand, per the user's
  own "one-line fix" framing, not a blocker.
- **Argument numbers are positional.** All eight this plan commits to (773, 761, 885, 886, 955, 956,
  673, 874, 876) were probed live 2026-10-17 and independently corroborated against DCS-BIOS's own
  Mi-24P survey 2026-10-21 — two independent sources agreeing lowers this risk without eliminating
  it. An ED patch inserting a table entry still shifts them silently; regenerate against the
  installed tree (or re-diff against DCS-BIOS, which costs nothing and was exactly how this
  session's corroboration was obtained) if a sortie disagrees with this plan's numbers.
- **The `READY`/`READNS.` lamp has now failed two independent read attempts** (`list_indication`,
  and DCS-BIOS's own exhaustive-looking survey) — treated as a standing seam, not a blocker, per
  §0/§3; a real fix would need a brute-force `get_argument_value` scan across ~2000 args during a
  real warm-up, out of scope while zero-warm-up direction stands.
- **`weapon_safety_observed` lag is unread in this entry** — explicitly a risk `BL-B67` inherits,
  named in §3 and the Co-moving Fields table so it is not rediscovered.
- **One-shot-per-mission power-up latch may be wrong for a multi-landing training mission** — a
  stated choice (§2), not a measured constraint; cheap to revisit if a sortie shows it wrong.
- **Every phase-dispatch lesson from `BL-B64`/`BL-B71` is about `optic_policy.py` internals this
  entry deliberately does not touch** — the risk that lesson warns about (a diverged pair read by
  the wrong branch) cannot recur here because no branch in `decide()` reads any field this entry
  adds. Flagging the absence explicitly so it is not assumed overlooked.

---

## Second-order effect

**Makes the cockpit-write channel the first reusable facility** (Stage 1's generic
`cockpit_switch` op) — `BL-B80`'s eventual slew write and `BL-B67`'s ATGM-run writes (ARMED check,
launch-station selector) inherit it rather than each growing their own `op`. **Narrows `BL-B67`'s
own remaining work**: the guidance-unit power-up, OBSERV, and the safety bar are no longer open
questions by the time that entry starts, and it inherits the `observ_observed`/
`weapon_safety_observed` readback risk named above as something to check before firing, not
discover mid-flight.

---

## Decisions — all answered 2026-10-21 (user)

1. **Transport: own `Export.lua` op; DCS-BIOS reference-only.** *"yes"*.
2. **Refusal wording: `"Unable, guidance unit not ready."`** *"ok"*.
3. **Voice phrases: `"weapons armed"` / `"weapons safe"`** only. *"weapons armed/safe"*.
4. **No switch allow-list on `cockpit_switch`** — overrides the security plan review's required
   fix; see the Export.lua bullet under Affected Modules for the user's words.

---

---

# Superseded text below (2026-10-15 plan + 2026-10-17 probe addenda)

**Everything from here down predates the 2026-10-21 scope split and explore pass. Kept for
history only — do not plan or implement against it.** It argued about which DCS channel should
drive the sight head (AI position axis vs. player rate axis); that question moved to `BL-B80` in
full, including the probe findings that answered it. The switch-sequence and OBSERV half it also
covered has been rewritten above against the user's own procedures direction, which this text
predates and in places contradicts (it still carries the recon table's 11-switch sequence and the
3–4 minute/10–15 second timers that direction overrode).

See `git log --follow plans/9k113-effectors/plan.md` for the full prior text rather than
reproducing it here.
