# BL-B66 — The 9K113 sight, entry 2 of 3: effectors

Architect pass, 2026-10-15. Entry 2 of 3 (`[[BL-B64]]` perception → **this entry, effectors** →
`[[BL-B67]]` the ATGM run), by user direction §5.

**Specification, in precedence order:** `docs/acceptance/2026-10-15-9k113-sight-direction.md`
(§1, §5, §8, §12, §12a) outranks this plan; `docs/concept/9K113.md` is the user's own and is not
edited. Reconnaissance: `body-layer/research/2026-10-14-9k113-warmup-atgm-procedure.md` and
`aircraft-layer/research/mi24p-command-surface.md`.

### Goal

Make the real cockpit systems move: throw the 9K113's switch sequence, turn OBSERV into an actual
cockpit mode rather than only a body-layer one, and make the physical sight head follow the aim
Petrovich has already decided on — so that what the pilot sees in the cockpit matches what
Petrovich believes he is looking through.

---

## 0. The finding that changes this entry, before anything else

**The brief's central premise — that pointing the sight must be a closed rate loop, and that this
makes `[[BL-B63]]`'s fast lane a hard correctness dependency — rests on a claim the repo already
refutes. I am reporting it rather than planning around it, per my own role's rule on evidence
arriving from outside the user's own words.**

`aircraft-layer/research/mi24p-command-surface.md` §4.1.2 and its **CORRECTION of 2026-09-21**
record a *live, five-point measurement*:

> **The AI axis (3060/3061) is a POSITION target, exactly linear**, measured at five points with
> ratio `0.440000` in every case, settling inside 0.25 s and then holding flat. So pointing is a
> **single write** — no closed loop.
>
> The player axis (3025/3026) is NOT the same control — it accumulates/slews the way a human
> holding a slew input expects. **Do not use it as an effector**, and do not assume one channel's
> behaviour from the other; **that mistake cost two probe flights.**

Three things follow, and none of them contradict a word the user wrote:

1. **§12 is a true statement about the crewman, not about our command channel.** The copilot really
   does slew with a rate-commanded joystick — `Devices_specs/9K113.lua` sets
   `axis_use_velocity = true` for exactly that control. **§12 describes the human mechanism we are
   modelling; it does not name which DCS command id Petrobrain writes**, and `BL-B66`'s own entry
   already says so: *"which of those two axes this loop should drive is itself an open question for
   this stage's plan rather than a settled choice."* Answering it is this plan's job, not a
   re-opening of settled direction.
2. **§12a's premise that the maximum rate is unknowable is also refuted by the repo**, and this is
   my own "find N before accepting that N is unknown" rule firing. DCS's own device spec states it:
   `h_axis_velocity = rad(20)/s`, `v_axis_velocity = rad(10)/s`, `Slew_dead_zone = 0.003`,
   `min_slew_velocity = rad(0.07)`. The user's conclusion — *"we do not need to know it"* — is
   correct for the **player** channel, where DCS enforces the limit for us. But the number is not
   unavailable, which means **a faithful slew time can be modelled on our side**, and that is what
   unlocks the cheaper design below.
3. **The player channel may not even work.** The same research note's unresolved gate 1: the 9K113
   is its own mode with a `dedicated_viewport`, and *"the **player** slew axes may simply be ignored
   outside that mode. Unverified, and it is the first thing to test."* Petrovich is not the player
   and there is no viewport. **The brief's chosen channel is the one with an open feasibility
   question against it; the channel it treats as a fallback is the one confirmed working.**

**What this costs if we follow the brief as written:** a proportional controller with an empirical
deflection law, a deadband floored by an unmeasured readout granularity, a limit-cycle risk against
an unknown plant, a correctness-level dependency on an unbuilt milestone (`BL-B63`), and a
feasibility probe that may come back negative — to reproduce, through an unverified channel, a slew
profile DCS has already published the constants for.

**Decision 1 below puts this to the user.** The plan is structured so that **Stages 1–2 are common
to both answers** and the channel choice is isolated to Stage 3 behind one boundary, so this
question does not block the entry starting.

### 0a. Why §8 is still honoured either way — the slew model is ours, not DCS's

§8's requirement is behavioural: *"the 9K113 via cockpit manipulation **takes time to move** so we
cannot expect instant alignment with anything."* That is a statement about **what Petrovich
believes he can see**, and it is satisfied inside `advance_sight_aim` — body-layer, no cockpit write
involved — by rate-limiting `actual` toward `desired` at 20°/s azimuth and 10°/s elevation.

So the slew *time* is delivered by Stage 1, testable immediately, with no probe, no fast lane and no
cockpit write at all. The cockpit write then merely **follows** a pointing direction that is already
correctly paced. Under the position-axis answer the sight's head traces our profile; under the
rate-loop answer a controller makes it track the same profile. **§8 does not pick the channel.**

---

## Effort/Value — re-read honestly, and it improved twice today

**The brief is right that this entry lost its cheap half.** §1 removed the ASP-17 crosshair-hold use
case outright (the mark follows the sight automatically — there is no action to build), which was
one of the two non-ATGM justifications. What remains on the non-ATGM side is **pinpoint-on-request**
alone, and that is thin: the pilot already gets the callout from `BL-B64`'s perception without any
cockpit write.

**But two things moved in this entry's favour since that assessment was written, and both are
large:**

- **Zero warm-up (user direction, this session): *"ignore until effectors built. Prepare code for
  it, but use no warmup time."*** The entry's own "acceptance is unusually expensive" section —
  ~3 minutes before anything is testable, a toppled gyro costing a full 3–4 minute reset — **no
  longer applies.** That was the single biggest cost driver and it is gone by direction. Acceptance
  is now an ordinary sortie.
- **§0's finding, if Decision 1 goes the recommended way**, removes the controller, the empirical
  tuning pair, the deadband, the limit-cycle risk and the `BL-B63` dependency. The slew becomes one
  rate-limited interpolation we already know the constants for, plus one `SetCommand` per poll.

**Verdict: the sequencing holds, and `BL-B67` does not need re-scoping.** This entry is genuinely
cheaper than when it was filed, and its real value is not pinpoint-on-request — it is that
**`BL-B67` cannot exist without it.** A SACLOS missile is guided by keeping the sight on the target
for the whole 14–15 s of flight (research addendum: 345 m/s over 5 km); that *is* a cockpit-write
loop. This entry builds the one mechanism the ATGM run is made of, which is why §5 puts it second
rather than making it optional.

**One scope caution.** If Decision 1 goes the brief's way, the honest effort/value read changes: the
controller, its tuning and its probe are a materially bigger build for the same delivered behaviour,
and I would then recommend narrowing this entry to Stages 1–2 plus warm-up/OBSERV writes, and
filing the rate loop as its own entry gated on `BL-B63` — rather than letting one unverified channel
hold up the whole sight.

---

### Affected Modules / Files

**body-layer**

- `src/belief/optic_policy.py` — `advance_sight_aim`'s body replaced (rate-limited convergence, from
  `return desired`); new `SIGHT_SLEW_RATE_AZ_DEG_S` / `SIGHT_SLEW_RATE_EL_DEG_S` /
  `SIGHT_AIM_DEADBAND_DEG` through `tuning.real`; `OpticState` gains the readiness and
  observed-state fields named in the Co-moving Fields table.
- `src/belief/sight_effector.py` — **new.** The one boundary this entry adds: translates
  `OpticState`'s aim and mode into cockpit actions, and ingests the sight's observed state back.
  Holds the switch *sequence* (ordering, device/arg) and the readiness seam. **No DCS knowledge
  below this file; no body-layer belief above it.**
- `src/logger.py` — the poll loop drives the effector beside the existing OBSERV dispatch
  (~L1939–1962); `_apply_active_gaze`'s `advance_sight_aim` call site is **unchanged**.
- `src/aircraft_client.py` — the new command op and the 9K113 state read.
- `config/defaults.toml` — the new tunables, with sourced provenance comments.

**aircraft-layer**

- `dcs-export/Export.lua` — a new `op` on the existing `poll_command_socket` (which already
  dispatches `petrovich_search` and already calls `performClickableAction` live); args **874/876/886**
  pushed as telemetry on the change-epsilon pattern `push_spu8_state` established.
- `src/collector/command_sender.py`, `src/api/server.py`, `src/schema/` — the op and the state
  payload. **HTTP/JSON across the subproject boundary**, as aircraft-layer ↔ body-layer already does.

**Docs / roadmap**

- `body-layer/ROADMAP/BL-B66.md` — amended with §0's finding, the zero-warm-up direction and
  Decision 1.
- `body-layer/ROADMAP/BL-B63.md` — its "hard dependency of `BL-B66`" amendment is **conditional on
  Decision 1** and must say so.
- `plans/9k113-sight/plan.md` — §15c amended (Decision 5a below): the three constraints it recorded
  for this entry are contingent on a channel choice it treated as settled.

---

### Implementation Plan

**Stage 1 — the sight takes time to move, and nothing touches the cockpit.**
Replace `advance_sight_aim`'s pass-through with a rate-limited convergence: move `actual` toward
`desired` by at most `rate * dt_s` per axis, 20°/s azimuth and 10°/s elevation, clamped to the
field of regard already on the optic, and snap when inside the deadband. `dt_s` is already threaded
in and unused, exactly for this. Per-optic by construction — the naked eye and binoculars have no
field of regard and stay `actual := desired`. **Delivers §8 in full, is testable in the existing
test suite, and is correct under either answer to Decision 1.**

**Stage 2 — the cockpit-action channel and the switch sequence, with zero warm-up.**
The new `op` on `Export.lua`'s listener, plus `sight_effector.py` holding the 11-switch **ordering**
and its device/arg table. Readiness gets `BL-B64`'s own seam shape: a named predicate that today
returns ready immediately, with one obvious place for a duration or a real lamp read to land.
Flag-gated debug logging built in up front, not bolted on after a failed sortie.

**Stage 3 — the sight head actually follows, and the channel is Decision 1's to pick.**
Behind `sight_effector.py`, one of:
- *(recommended)* **position actuator** — write Stage 1's already-paced `actual` to
  `SetCommand(3061, az/60)` each poll. Confirmed live, needs no loop, no tuning, no fast lane.
- *(brief's path)* **rate controller** — proportional deflection on 3025/3026 against the 874/876
  readback, with the deadband floored by the probe's measured granularity. Needs `BL-B63`.

Either way, **once 874/876 are read, they are authoritative for `actual_aim_*`** — see Invariants.

**Stage 4 — acceptance sortie**, then pinpoint-on-request as the surviving non-ATGM use.

---

### Co-moving Fields

Step 6a's trigger fires: this entry adds **three layers over one concept** — the pilot's intent, what
we have commanded into the cockpit, and what DCS reports back — where `BL-B64` had two. That is the
exact shape of its `phase`/`home_phase` defect, one layer deeper, so the table is mandatory.

**The hazard in one sentence:** `home_phase` says Petrovich intends to use the sight, the cockpit
switch may not be thrown yet, and the sight head may still be slewing — and perception must act on
the *last* of those three, never the first.

| Field | Written by | Transition | Must hold true immediately after |
|---|---|---|---|
| `home_phase` | **external** (pilot "Observ on/off", `logger.py` ~L1947) | OBSERV on | `home_phase is SIGHTING`; `phase` **unchanged** (`decide`'s `_back_to_home` moves it at the next boundary — the illegal "jump straight into SIGHTING" stays illegal) |
| `phase` | internal (`decide`) | OBSERV on | still the prior phase this poll; may become `SIGHTING` only once `observ_observed` is on **and** `sight_ready` is true |
| `hands_busy_until_sim` | **external** (same site) | OBSERV on **or** off | `= now_sim + HANDS_BUSY_DURATION_S` on **both** edges — the hand is on the switch either way |
| `observ_commanded` | internal (`sight_effector`) | OBSERV on | `True`; a cockpit write to arg 886 has been issued exactly once, not once per poll |
| `observ_observed` | **external** (DCS telemetry, arg 886) | OBSERV on | **may still be `False`** — the write is in flight. **Every phase-dispatch branch must re-read this, not `home_phase`** |
| `sight_ready` | internal (readiness seam) | OBSERV on | `True` today (zero warm-up by direction); the one place a duration or lamp read lands later |
| `actual_aim_azimuth_deg` / `..._elevation_deg` | internal (`advance_sight_aim`), **then external** (arg 874/876 once read) | any aim change | strictly between the prior value and `desired`, never equal to `desired` while the error exceeds one poll's `rate * dt` |
| `actual_aim_*` | as above | OBSERV **off** | `None` — and the *commanded* deflection/position must be released in the same transition, or the head keeps slewing after the mode is gone |
| `look_contact_id` | internal (`decide`) | OBSERV off | `None`, cleared by `_back_to_home` |
| `look_started_sim` | internal (`decide`) | OBSERV off | `None` |

**Two transitions that are easy to miss, and both are `BL-B64`'s defect recurring:**

- **OBSERV off while the head is mid-slew.** `actual_aim_*` going `None` is not sufficient — the
  *cockpit* is still being driven. The release must be part of the same transition, named here so it
  cannot be left to a later branch.
- **`home_phase is SIGHTING` while `observ_observed is False`.** This is the diverged pair, and it is
  reachable on *every* OBSERV-on for at least one poll — not a rare case, the normal case. A branch
  that reads `home_phase` to decide whether the sight is usable is wrong for that window, which is
  precisely how a pilot's "Observ off" left the sight running for 30 s in `BL-B64`.

**Construction rule, carried forward from `BL-B64`'s own docstring and its third instance of this
defect:** every `decide` branch that builds a fresh `OpticState` rather than `replace`-ing one must
carry all of these forward explicitly. A controller needs continuity across polls to converge at all.

---

### Invariants checked

- **DCS is authoritative about the simulated world.** This is what settles the model-versus-readback
  question on principle rather than taste: Stage 1's rate-limited `actual` is our *model* of the
  head, and the moment args 874/876 are read, **the readback wins and the model becomes the fallback
  for when it is absent**. Perception already reads `actual` and never `desired`
  (`association.py:306`, `naked_eye_source.py:442`), so no call site moves.
- **Never modify the DCS installation.** Writes are `SetCommand`/`performClickableAction` against a
  running sim through the existing listener — runtime state, not files. Nothing in the tree is
  touched.
- **Code owns factual state.** Readiness is a predicate code evaluates; no model is asked whether
  the sight is warm.
- **Module independence.** aircraft-layer ↔ body-layer stays **HTTP/JSON**. No new in-process
  cross-subproject import.
- **Single-player only.** No group/coalition scoping anywhere in this entry.
- **No new abstraction without a named duplication removed.** `sight_effector.py` is the only new
  boundary, and it earns its place by isolating Decision 1: without it, the channel choice leaks
  into `logger.py` and `optic_policy.py` and cannot be changed after a sortie.

---

### Risks & Unknowns

- **The warm-up argument numbers are positional and were probed on a different device set.** Every
  one of 673/955/885/886/963 is cross-referenced from a 2026-09-11 probe (DCS 2.9.29.27278);
  `performClickableAction` is proven live only on device 30 and device 55. An ED patch inserting a
  table entry shifts them silently. **Regenerate against the installed tree before coding.** This is
  the single largest risk in the series.
- **`performClickableAction` on devices 6 and 7 is unproven.** Note the verbs are distinct: the sight
  *axes* have no clickable element and use `SetCommand` (confirmed), while the warm-up *switches* do
  and need `performClickableAction` (unconfirmed on these devices). A negative here blocks Stage 2's
  switch sequence but **not** Stage 1 or Stage 3's position write.
- **Elevation has no degree conversion.** Arg 876's gauge is piecewise (`-1→-0.75, 0→0, 1→1.0`) and
  its limits in degrees are unmeasured. Azimuth is exactly linear and calibrated; **elevation
  feedback is the weaker axis and the 10°/s model rate is the mitigation.**
- **The player channel may be inert outside the sight's dedicated viewport** (unresolved gate 1). If
  Decision 1 goes the brief's way, this is a feasibility risk on the critical path.
- **Gimbal limits are from the English manual, not read live** — ±60° az, +20°/−15° el; the native
  `initLimits` is not exposed to Lua. The field of regard must be enforced on our side.
- **The gyro-topple failure mode is unmodelled** — an excessive-rate manoeuvre needs `GUID.UNIT POWER`
  cycled. Out of scope by the zero-warm-up direction, but it exists in the aircraft and a sortie can
  hit it.
- **Per-poll write traffic.** Writing a position every poll is new cockpit traffic. Suppress writes
  inside the deadband rather than sending unconditionally.

---

### Second-order effect

**Unblocks `BL-B67` and narrows it in a good way.** The SACLOS guidance this entry's mechanism
becomes is the whole of the ATGM run's control problem, so `BL-B67` stays thin, as intended — its
missile data is already in the research addendum and it adds the launch decision, not a new
actuator. It also makes the cockpit-write channel the **first reusable** one (SPU-8 and the AI wheel
are each one-off), which `[[BL-B65]]` inherits for free. And if Decision 1 goes the recommended way,
it **removes a correctness-level dependency from `[[BL-B63]]`**, which returns that entry to being
the optimisation it was filed as.

---

### Decisions Requiring User Input

**1. Which DCS channel drives the sight head — and this is the one that matters.**
*Recommendation: the **AI position axis (3060/3061)**.* It is confirmed live at five measured points
with an exact linear law, settles in 0.25 s, needs no controller, no empirical tuning, no deadband
calibration and no `BL-B63`; §8's slew time is delivered by Stage 1 on our side using DCS's own
published 20°/10°per-second limits. The player rate axis is the faithful-looking choice but is the
one the research explicitly says *"do not use as an effector"*, is unverified outside the sight's
own viewport, and generalising between the two channels **already cost this project two probe
flights**. The counter-argument deserves stating: the position axis is DCS-Petrovich's own channel,
and this project exists to replace that behaviour — but we are borrowing its *actuator*, not its
perception or its judgement, and the pacing stays ours.

**2. If Decision 1 goes the brief's way, should the rate loop be its own entry?**
*Recommendation: yes.* It would then carry a controller, a tuning pair, a probe with an open
feasibility question and a dependency on an unbuilt milestone — too much to hold the switch sequence
and the slew model hostage to. Stages 1–2 ship either way.

**3. Does the readback become authoritative for `actual_aim_*` as soon as it is available?**
*Recommendation: yes* — "DCS is authoritative about the simulated world" decides it, and I have
planned on that basis. Flagged because it means our modelled slew is a fallback, not the truth, and
a sortie may show the two disagreeing.

**4. The warm-up timer — ANSWERED by direction, recorded not open.**
> *"ignore until effectors built. Prepare code for it, but use no warmup time."*

Zero duration, no ЩО `READY` lamp model, no 3–4 minute constant. The **ordering** of the 11 switches
and their device/arg numbers are structural and stay (Stage 2); only the *elapsed-time* gates — the
210 s program timer, the 3–4 min warm-up, the 10–15 s gyro alignment, the 2–8 s caging — are
dropped. Readiness keeps `advance_sight_aim`'s own seam shape.

**5. What OBSERV on/off means once the effectors are real.**
*Recommendation: the command still returns immediately, and Petrovich acknowledges the **ask**, not
the completion.* The existing 1 s `hands_busy` suppression already models the hand on the switch, and
with zero warm-up there is no long sequence left to narrate — so *"Observ on"* is answered as it is
today. What changes is only that a dispatch branch must wait on `observ_observed` before treating the
sight as usable (see the Co-moving Fields table), which is invisible to the pilot. **If a real
warm-up ever lands, this answer must be revisited** — a 3-minute silence after an acknowledgement
would be the wrong behaviour, and that is the moment to add *"guidance unit ready"*.

---

## PROBE REPORTED, 2026-10-17 — §0 is withdrawn by measurement and Decision 1 inverts

**Read this before §0 or Decision 1 below; both are superseded on their central claim.** Full
record: `aircraft-layer/research/2026-10-17-9k113-effector-and-slew-probe-findings.md`.

§0 argued that the AI axis is a working position target and the player axis is the unverified one,
on a five-point live measurement from 2026-09-11. **Both halves measured false today**, in two
runs, the second with the aircraft set up by hand and `OBSERV` confirmed on:

| channel | commanded | result |
|---|---|---|
| AI 3061 / 3060 | 5 bearings + 12 staircase steps each | args 874/876 **never left 0.00000** |
| player 3026 / 3025 | ±0.5 held ~3 s | **~45° azimuth, elevation the same shape, sign-inverted** |

Every call returned `ok=true`, so only the argument readback separates them — and the player axis
moved the head in the same run, same device, same `SetCommand` path, seconds after the AI axis did
not.

**So:** Decision 1 takes the player axis by elimination; the controller, deflection law, deadband
and limit-cycle risk return; `BL-B63` is a hard dependency again, as direction §12 and `BL-B66`'s
own entry had it. §0's "find N before accepting that N is unknown" reasoning was sound and its
conclusion was still wrong, because the number it found described a channel that no longer answers.

**This plan's scope caution is now in force rather than hypothetical** — narrow the entry to the
switch sequence and `OBSERV` (both measured working today), and file the slew loop separately,
gated on `BL-B63` and on one more probe run with per-frame slew logging.

---

## Probe brief — for the user's Windows box

**Self-contained; needs a running DCS and cannot be done by any agent.** Everything below is one
sortie's work. Target: the installed DCS version — record the build number, because every argument
number here is **positional** and shifts if ED inserts a table entry.

**Why it matters:** question 1 decides whether Stage 2's switch sequence is buildable at all;
question 2 sizes a controller's deadband *only if* Decision 1 goes the brief's way; question 3 would
let readiness be observed rather than assumed. **Question 4 is new and is the cheapest high-value
item on the list** — it decides Decision 1 empirically.

1. **Can `performClickableAction` move the warm-up switches?** Args **673, 955, 885, 886, 963** on
   **`WEAP_SYS` (device 6)** and **`I9K113` (device 7)**. For each: issue the action, then read
   `GetDevice(0):get_argument_value(<arg>)` back and report whether it changed, and whether the
   associated lamp followed. *(Proven live today only on devices 30 and 55 — a different device set.)*
2. **What is arg 874/876's read granularity?** Not merely "is it readable" — the **smallest
   non-zero change observable** while the sight slews slowly, sampled as fast as the export loop
   allows. A controller's deadband cannot be finer than this number, so it sizes the design.
   Elevation (876) matters more than azimuth: its gauge is piecewise and its degree conversion is
   still unmeasured.
3. **Does `list_indication` read the `READY` lamp?** Index **8, `ccGunnersCPanel`** (owned by
   `WEAP_SYS`, never tried), and the 9K113's own `list_indication(0)`. Report the full text dump,
   not just a yes/no — a sibling string may carry it. *Low priority now that warm-up is zero; keep
   it only if the sortie has room.*
4. **Does the AI position axis still behave as measured, and does the player axis work at all?**
   `GetDevice(7):SetCommand(3061, az/60)` at a few bearings — confirm it still settles in ~0.25 s
   with `arg_874 = value * 0.44`. Then `SetCommand(3025/3026, ±0.5)` **while not in the sight's own
   viewport** and report whether the head moves at all. This is the unresolved gate that decides
   Decision 1 on evidence instead of judgement.
