# BL-B89 — 9K113 scanning procedure: sector scan, then pointing at a known place

Base: `main` at `e9fb4a2b` (BL-B96 merged — `body-layer/src/logger.py` is now `body.py`,
`tests/test_logger.py` is now `tests/test_body.py`; every reference below uses the new names).

### Goal

Replace the 9K113's idle search cycle — currently three blind geometric bands
(`wide`/`narrow_near`/`narrow_far`) swept regardless of what is actually out there — with the
procedure the user described from flying it: wide S-scans find points of interest, narrow then
visits them **by priority** (finish identifying a partially-known contact before starting to
classify a new one), a blind narrow sweep covers the range band nothing else reaches, and a brief
mandatory naked-eye all-round glance closes every lap so nothing sneaks up unseen. Stage 2 (not
built here, but designed for) adds pointing the sight at a named place (o'clock/bearing, optional
distance) instead of a sector.

### What's already built — read before assuming any of this is new

`feature/9k113-narrow-search` (merged into this base) shipped nearly all of the machinery this
plan reuses:

- The idle-aim invariant (`_decide_sighting`'s idle branch always has an in-regard aim),
  boresight-relative (pitch/bank) regard checking (`heading_relative_to_body_relative`,
  `perception/geometry.py`), and `within_field_of_regard` filtering applied to every search step
  (`body.py:_sight_in_regard_sweep`) — **no new mechanism needed for any of this.**
- `OpticState.sight_search_leg: SightSearchLeg` driving a leg-cycling idle search
  (`_SEARCH_LEG_ORDER`/`_next_search_leg`/`_idle_sight_search`/`_idle_sight_rest`,
  `belief/optic_policy.py`), entering a real `OpticPhase.SEARCHING` detour (binoculars) for any
  out-of-regard remainder of a commanded sector.
- `_split_sector_by_regard`/`_commanded_or_default_sector` (`body.py`) — sector-vs-regard
  geometry, reused by Stage 1 below but fed a **different** sector table (see "Sector widths").
- `sight_look_optic` (wide-vs-narrow for an already-chosen look target) and `sight_can_still_improve`
  (the upper-bound admission test that lets a far contact become a sight candidate at all) —
  **Stage 1 only changes which target `choose_look`'s sight-side equivalent picks, never whether
  one is admitted.**
- `SIGHT_STALL_COOLDOWN_S`/`OpticState.attempted_at_level` (`BL-B85`) — the "don't get stuck on one
  contact forever" bound. This is **not** the "quick position check" the user asked for (see
  Decisions) — it is what currently stands in for it, by simply not re-looking.
- `SIGHT_MAX_DWELL_S`/`SIGHT_GLANCE_AWAY_S`/`_start_glance_away` — the existing naked-eye
  interruption, today purely time-based. Stage 1 adds a **second**, lap-completion trigger
  alongside it (see "The naked-eye pause").

**None of this is reused wholesale, though — BL-B89's own roadmap title is "points of interest,
not band sweeps," and the band-sweep design is exactly what shipped.** Stage 1 changes the shape
of the idle cycle (legs renamed/reduced, one new priority-ordered look-selection function) while
keeping every piece above load-bearing underneath it.

### Affected Modules / Files

- `body-layer/src/belief/optic_policy.py`
  - `SightSearchLeg` narrows from four names to three: `"wide_near"`, `"wide_far"`,
    `"narrow_far_sweep"` — `"narrow_near"` is dropped (see "Narrow visits replace the near-band
    sweep" below) and `"binocular"` moves out of the enum (see next bullet).
  - New `choose_sighting_look(targets) -> LookTarget | None` — `choose_look`'s own coverage/watched
    ordering, with an outer priority bucket (contacts seeking `type` before contacts seeking
    `class`). `_decide_sighting` calls this instead of `choose_look` for its candidate selection;
    `GLASSING`'s own call to `choose_look` is untouched.
  - `_idle_sight_search`: on completing a lap of the three search legs (the leg about to start is
    the cycle's first, `"wide_near"`), returns `_start_glance_away` instead of continuing — the
    mandatory pause, independent of `SIGHT_MAX_DWELL_S`. The out-of-regard binocular excursion
    (now entered as its own, separately-triggered detour rather than a fourth cycle leg — see
    below) does not count toward a lap for this purpose.
  - Tunables: `SIGHT_SEARCH_NEAR_M` default lowered **2333.0 → 1500.0** (user correction, "more
    like 1.5 km – 4 km", `lo` lowered to `500.0` to keep the default off the floor). New
    `SIGHT_SEARCH_WIDE_MID_M` (wide_near/wide_far boundary, default `4_000.0`,
    `lo=2_000.0, hi=6_000.0`). New `SIGHT_SEARCH_WIDE_FAR_M` (wide_far's own far edge, default
    `8_000.0`, `lo=4_000.0, hi=15_000.0`) **replacing** the derived `_SIGHT_WIDE_SEARCH_FAR_M`
    (see "Why the derived far edge has to become a plain tunable"). `SIGHT_SEARCH_MID_M` is
    **removed** — it was the `narrow_near`/`narrow_far` boundary and has no leg left to bound;
    `narrow_far_sweep` now runs `[SIGHT_SEARCH_WIDE_FAR_M, SIGHT_SEARCH_FAR_M]` (picks up exactly
    where wide's own reach ends, the same "wide's far edge is wide's own useful reach; beyond that
    only narrow brings information" principle the 2026-10-20 F4 follow-up already established).
  - `_SIGHT_WIDE_SEARCH_FAR_M`'s old derivation comment and its own test class move with the old
    constant name's removal — `tools/generate_defaults.py --write` regenerates
    `config/defaults.toml` (loses `SIGHT_SEARCH_MID_M`'s row, gains the two new rows).
- `body-layer/src/perception/gaze.py`
  - New `SIGHT_SECTOR_WEDGE_DEG: dict[RelativeSector, tuple[float, float]]` — the sight's own
    sector widths, **separate from** `SECTOR_WEDGE_DEG` (naked eye/binoculars keep their existing
    o'clock-hour convention unchanged): `"left": (-30.0, 30.0)` (span [-60, 0]), `"right": (30.0,
    30.0)` (span [0, 60]), `"full": (0.0, 60.0)` (span [-60, 60], == the sight's own regard — this
    is the same value `_commanded_or_default_sector`'s no-command default already synthesizes, so
    `"full"` and "nothing commanded" now coincide for the sight by construction). `"ahead"` is not
    a single wedge — see next bullet.
  - New `SIGHT_AHEAD_LEGS: tuple[tuple[float, float], ...] = ((-10.0, 20.0), (10.0, 20.0))` — the
    two alternating 40°-wide windows (span [-30, +10] then [-10, +30]) the user described for the
    forward sector, the sight's own analogue of `_SECTOR_LEGS["ahead"]`'s naked-eye `(11, 12, 1)`
    cycling but a different geometry (two wide windows, not three narrow ones) — kept as its own
    table rather than forced into the existing one, since the two conventions now genuinely differ
    (see "Sector widths diverge from the naked eye's" below).
- `body-layer/src/body.py`
  - `_commanded_or_default_sector`/`_split_sector_by_regard`/`_sight_in_regard_sweep`/
    `_sight_out_of_regard_sweep` all take `SIGHT_SECTOR_WEDGE_DEG` (and, for `"ahead"`,
    `SIGHT_AHEAD_LEGS`) in place of `SECTOR_WEDGE_DEG` — `_search_sweep` (the naked-eye/binocular
    path) is **untouched**, still reads `SECTOR_WEDGE_DEG`.
  - A commanded single o'clock hour (`ScanPlan.commanded_legs`, one int) resolves to its own 30°
    wedge via the existing `_gaze_for_clock_hour` azimuth, same `_split_sector_by_regard` geometry
    — an hour fully outside ±60° (4–8 o'clock) yields an empty in-span, so the sight contributes
    nothing and eyes/binoculars cover all of it, unchanged from today's behaviour for an
    out-of-regard commanded sector.
  - The out-of-regard binocular excursion becomes **rare, not routine**, once `left`/`right`/
    `full`/`ahead` are all ⊆ regard by construction (only a straddling single o'clock hour still
    produces one) — no code change beyond feeding the new table in; flagged so a reviewer does not
    read the near-empty `sight_out_of_regard_search` as a regression.
- `body-layer/tests/test_optic_policy.py`, `body-layer/tests/test_body.py` — see Tests.
- `body-layer/config/defaults.toml` — regenerated.
- Not touched in Stage 1: `BL-B83` (mission objective area) stays deferred — no runtime datum
  exists; `BL-B74` (SAM launch smoke) stays in the backlog, both reconfirmed by the user.

---

## Implementation Plan

### Stage 1 — the sector scan

**1. Sector widths diverge from the naked eye's, and that is correct, not an inconsistency.**
The naked eye's `left`/`right` (`SECTOR_WEDGE_DEG`) are the 9–11 and 1–3 o'clock windows — narrow,
outward-shifted bands that deliberately exclude dead ahead (`"ahead"` already covers that). The
sight's own regard is physically bounded at ±60°, and the user's own words size `left`/`right` to
the *whole* left/right half of that regard (0 to ±60), not an outward sliver of it. These are
different instruments scanning different things for different reasons; forcing one table to serve
both would either narrow the sight's coverage to what the eye convention happens to carve out, or
widen the eye's. Kept as two tables, `SECTOR_WEDGE_DEG` (unchanged, naked eye/binoculars) and
`SIGHT_SECTOR_WEDGE_DEG` (new, sight only).

**2. Narrow visits replace the near-band blind sweep — this is the mock's steps 3–4, not new
search legs.** Re-reading the explore-notes mock: steps 3 ("narrow: visit unidentified units by
priority") and 4 ("same for class") are not sweeps of a range band at all — they are visits to
**specific already-detected contacts**, which is exactly what `_decide_sighting`'s existing
look-selection already does whenever something is `worth_looking`. The idle search legs
(`wide_near`/`wide_far`/`narrow_far_sweep`) only ever run when `choose_sighting_look` returns
`None` — i.e. when there is nothing to visit. So Stage 1 does **not** add legs for steps 3–4; it
fixes the **order** `choose_sighting_look` picks among candidates, and removes the now-redundant
`narrow_near` blind sweep (2.3–5.6 km), since any contact in that band worth resolving is already
reached by the look mechanism the moment it is `worth_looking`, and a band nothing has been
detected in yet is covered by `wide_near`/`wide_far` instead.

**3. The priority order, as a function:**

```python
def choose_sighting_look(targets: Sequence[LookTarget]) -> LookTarget | None:
    """Same ordering as choose_look, with an outer priority bucket: a
    contact seeking `type` (one look from full identification) is visited
    before any contact still seeking `class` (user: "first units not yet
    identified that might be inside identification range... same thing
    for class"). Within a bucket, choose_look's own coverage/watched/
    range ordering applies unchanged."""
    if not targets:
        return None

    def bucket(target: LookTarget) -> int:
        return 0 if target.current_level == "class" else 1

    by_bucket: dict[int, list[LookTarget]] = {}
    for target in targets:
        by_bucket.setdefault(bucket(target), []).append(target)
    return choose_look(by_bucket[min(by_bucket)])
```

(Implemented by grouping and delegating to `choose_look` rather than re-deriving its coverage
math, per "do not reinvent the wheel.") `current_level == "type"` never appears in `targets` here
— `sight_can_still_improve` already excludes it from `worth_looking` upstream, same as today.

**4. Band edges**, reusing the already-established "wide's far edge is wide's own reach" principle
for the boundary between `wide_far` and `narrow_far_sweep`:

| leg | band | tunable |
|---|---|---|
| `wide_near` | 1.5–4 km | `SIGHT_SEARCH_NEAR_M`–`SIGHT_SEARCH_WIDE_MID_M` |
| `wide_far` | 4–8 km | `SIGHT_SEARCH_WIDE_MID_M`–`SIGHT_SEARCH_WIDE_FAR_M` |
| `narrow_far_sweep` | 8–13.6 km | `SIGHT_SEARCH_WIDE_FAR_M`–`SIGHT_SEARCH_FAR_M` |

All three `status="judgement"` — the user confirmed only the near edge (1.5 km); the rest of the
mock's numbers ("rows and time per pass were not corrected... should be tunable") stand as
starting values. **Known residual coupling**, same shape as `belief.decay`'s documented one: no
per-key bound stops `NEAR_M` being tuned above `WIDE_MID_M`, etc. Flag in each tunable's own
comment.

**Why the derived far edge has to become a plain tunable.** The shipped
`_SIGHT_WIDE_SEARCH_FAR_M` was *derived* from `SIGHT_SEARCH_NEAR_M * SIGHT_WIDE_OPTIC.
presence_range_mult`, justified because `SIGHT_SEARCH_NEAR_M` *was* the naked eye's own unaided
presence reach (2333 m) — scaling a known baseline by the sight's own calibrated multiplier. Once
`SIGHT_SEARCH_NEAR_M` is lowered to 1.5 km specifically *because* it is no longer meant to equal
that reach, the derivation's premise is gone (it would now derive 1500 × 3.55 ≈ 5.3 km, below the
mock's own 4–8 km placeholder and below where `wide_far`'s own band starts). Made a plain,
independent tunable instead — a genuine behaviour change in how this constant is produced, not
just its value, so it gets its own line in the implementer's commit per "mechanism and calibration
never share a commit" (though here the *mechanism* change — derived to plain — is forced by the
calibration change, so one commit explaining both is acceptable; flagged so the reviewer does not
read it as an unexplained reversal of the narrow-search plan's own reasoning).

**5. The naked-eye pause is mandatory per lap, not only time-based.** Today's `SIGHT_MAX_DWELL_S`
scheduled break (30 s default) is a safety net — it fires regardless of search progress, so it
already satisfies "needed so that no surprise attack creeps up on us" in the worst case. The
mock's step 6 places the pause explicitly **after** a full lap (`wide_near → wide_far →
narrow_far_sweep`) rather than on an independent clock, and the explore answer confirmed the mock
stands. Add a second trigger: `_idle_sight_search` checks, before stepping into a leg that would
be the cycle's first (`wide_near`) immediately after the last (`narrow_far_sweep`) ran out, and
routes to `_start_glance_away` instead of restarting the lap. Both triggers call the same function
and read the same `SIGHT_GLANCE_AWAY_S` duration — this is an additional entry path, not a new
mechanism. The binocular out-of-regard excursion (now rare, see Affected Modules) does not count
toward "a lap" for this purpose — it already returns to `wide_near` on its own exit, and counting
it would double the pause for sectors that happen to need it.

**6. "Quick position check" for a known unit that has not crossed a threshold — not built, see
Decisions.** The explore notes' closing clause ("No use rescanning a known unit... except a quick
check for position") names an action this codebase has no shape for: a short look that refreshes
*position* without attempting to advance *classification*. Today, a contact `sight_can_still_
improve` excludes is simply never looked at again until it moves (`RETRY_RANGE_FRACTION`) or the
stall cooldown lapses — there is no cheaper, shorter "just check where it is" look. Flagged as a
Decision rather than built, because "how short" and "how often" are new judgement calls this
plan's own source material does not supply.

---

### Stage 2 — pointing at a known place (designed, not built this round)

Per the roadmap's own staging ("sector first, pointing as second stage, but do that too") and the
explore notes ("for now: an o'clock or a compass bearing, with an optional distance"), this stage
is scoped and left for its own implementation pass once Stage 1 has flown. Shape, so the
Implementer is not starting from nothing when it is picked up:

- **Command surface**: a new voice command, `point <o'clock|bearing>[, distance]`, parsed the same
  way `scan <sector>`/`watch <o'clock>` already are (`belief/voice_commands.py`). Requires
  `OBSERV ON` (`home_phase is SIGHTING`) — issuing it otherwise is a `"unable"` reply per the
  project's own "say again vs unable" convention, not a `"say again"`.
- **Aim**: a single fixed `(azimuth, elevation)` goal, the sight's own analogue of `gaze.
  ScanPlan.fixed_look_at` (used today for the attack-run's fixed-aim case) — not a leg of the
  idle search cycle, so `OpticState` needs a way to say "pointed, not searching" that the existing
  `sight_search_leg` enum does not currently express. **This is the stage's own co-moving-fields
  question** (see below) and needs its own pass at the state machine, not a bolt-on field.
- **Wide-then-narrow at the point**: orient with `SIGHT_WIDE_OPTIC` for a short, tunable duration,
  then switch to `SIGHT_NARROW_OPTIC` to identify/range — the same wide-then-narrow shape
  `sight_look_optic` already encodes for an ordinary look, applied to a commanded point instead of
  a detected contact's believed bearing.
- **Distance estimate**: the stadiametric mechanism from `docs/acceptance/
  2026-10-15-9k113-sight-direction.md` §11 (`BL-B55`'s ranging, not yet built) is the natural
  consumer once it exists; until then, range comes from whatever ordinary classification/position
  belief resolves once something is seen there.
- **"Move between targets"**: once the point produces a contact worth a look, control hands back
  to the ordinary `choose_sighting_look` mechanism (unchanged) — pointing establishes where to
  look first, it does not replace what happens once something is found.

This is deliberately underspecified relative to Stage 1 — it is the next plan, not a stub inside
this one.

**Performance and security debt carried into this stage.** The `[[BL-B98]]` fix folded into Stage
1 (`01a6fadd`, reviewed `47c8e96d` APPROVED) shipped with both passes waived by user direction
(2026-10-25: *"this should be a small fix, skip perf and sec now, do them with stage 2 code"*).
Stage 2's own performance and security passes must cover that fix's code too — `_start_glance_away`'s
removed nulling and `body.py`'s `run_once` OBSERV-off-edge aim reset — not just whatever Stage 2
itself adds. This is not `#needs-flight`-shaped debt (nothing here needs a live DCS session to
clear); it is a deferred review pass, and ends when Stage 2's batch runs Performance Reviewer and
Security over the combined diff.

---

## Co-moving Fields

Trigger: `OpticState.phase`/`home_phase`, already multi-field co-moving, gains two further
internally-decided fields this plan touches (`sight_search_leg`'s narrowed vocabulary; the
priority bucket is computed, not stored). Built by grepping every `OpticState(` (2 fresh
constructions, `body.py`'s `GLASSING`/`SEARCHING` entries) and `replace(state` site inside
`_decide_sighting`/`_idle_sight_search`/`_start_glance_away`.

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| `sight_search_leg` | internal | a lap completes (`narrow_far_sweep` exhausted, next leg would be `wide_near`) | **routed to `_start_glance_away` instead of advancing** — `sight_search_leg` is left at whatever it was (irrelevant; `_back_to_home`'s resume restarts at `wide_near` the same way it already does after any `SIGHTING` interruption) |
| `sight_search_leg` | internal | `SIGHT_MAX_DWELL_S` fires mid-lap (existing, unchanged) | same `_start_glance_away` path — the two triggers are not distinguished downstream |
| `look_contact_id`/`look_optic` | internal | `choose_sighting_look` picks a target | unchanged from the already-shipped mechanism — this plan only changes *which* target is picked, not what happens once one is |
| `home_phase` | external (pilot) | "Observ on"/"Observ off" | unchanged — every phase-dispatch branch already re-checks it |

(Stage 2's own co-moving-fields table is explicitly deferred to its own plan — see Stage 2's note
above; a "pointed, not searching" state is a new co-moving concern this plan does not resolve.)

---

### Tests

- `TestChooseSightingLook` (new, `test_optic_policy.py`): a `"class"`-level target beats a
  `"presence"`-level one regardless of range/coverage; within one bucket, `choose_look`'s own
  ordering is reproduced unchanged (reuse its existing fixtures); no targets → `None`.
- `TestSightSearchLegs` (replaces the narrow-search plan's `TestSearchCycle` for the new shape):
  `wide_near → wide_far → narrow_far_sweep → wide_near` cycles correctly; a lap completion (not
  `SIGHT_MAX_DWELL_S`) produces the glance-away — assert via `phase` transitioning to `SCANNING`
  with `now_sim - phase_started_sim` well under `SIGHT_MAX_DWELL_S` (proves the *other* trigger
  fired, not the clock one); the binocular excursion (still reachable via a straddling commanded
  o'clock hour) does not count toward a lap.
- `TestSightSectorWedge` (new, `test_body.py`): `SIGHT_SECTOR_WEDGE_DEG`'s `left`/`right`/`full`
  against the worked spans ([-60,0]/[0,60]/[-60,60]); `SIGHT_AHEAD_LEGS` alternation produces
  [-30,+10] then [-10,+30] across two laps; every one of `left`/`right`/`full`/`ahead` yields an
  **empty** out-of-regard sweep (the simplification named in Affected Modules); a commanded o'clock
  hour fully outside ±60° yields an empty in-regard sweep and a non-empty out-of-regard one,
  unchanged from today.
- **Nose-up at 50–800 m AGL** (`TestSightInRegardSweepBoresightRelative`, extended): a 5° and 10°
  nose-up case (the user's own "5 deg nose down in slow flight, 10 deg if fast" direction read in
  reverse, since nose-*up* is the untested half of the F5 fix's pitch range) at 100 m, 300 m, and
  800 m AGL — asserts `wide_near`'s near edge stays reachable (nose-up *raises* the depression
  needed for a given range, so this is the direction most likely to empty the near band if the fix
  has any asymmetry) and that the lap/leg mechanism above still composes correctly at that
  attitude (no leg silently empties forever).
  **"TAKE_FIRE... and the rest of the cycle stands" deliberately does not test above 800 m** — see
  below.
- **1–2 km AGL band**: one parametrized case at 1500 m AGL, level and 5° nose-down, confirming the
  whole lap (all three legs, plus the priority look mechanism) still produces at least one
  in-regard step per leg — "rare but must work," not optimised for.
- **> 2 km AGL is explicitly not tested** — the user's own instruction ("2000+ m AGL do not even
  consider"), recorded so a reviewer does not read the absence as a gap.
- Removed/renamed: every test asserting a `"narrow_near"`/`"binocular"`-as-fourth-cycle-leg shape
  from the narrow-search plan's own suite needs updating to the three-leg shape; `SIGHT_SEARCH_
  MID_M`'s own tests (band-edge, derivation) are deleted with the constant.

---

### Risks & Unknowns

- **Changing `SIGHT_SEARCH_NEAR_M` moves two things that happened to share a default, not one.**
  `body.py`'s `_SEARCH_BAND_M[0]` (the *naked-eye/binocular* search band) was noted in the prior
  plan as "reused by value, not import, since the two are independent tunables that happen to
  share a default" — confirming they are still independent (a `grep` for `_SEARCH_BAND_M` showing
  no read of `SIGHT_SEARCH_NEAR_M`) is cheap insurance before this value moves.
- **Removing `narrow_near` changes detection timing for contacts between 1.5–8 km that are not yet
  `worth_looking`.** Previously a blind narrow sweep covered 2.3–5.6 km independent of whether
  anything was known to be there; now only `wide_near`/`wide_far` cover that range until something
  crosses into `worth_looking`. This is the intended effect ("it's not really about a band, more
  like points of interest"), but it is a real reduction in blind-search resolution inside 8 km,
  worth confirming in flight rather than only in a unit test.
- **The lap-completion glance-away and `SIGHT_MAX_DWELL_S`'s own scheduled break can now fire in
  quick succession** if a lap happens to finish just before the dwell clock would have. Not harmful
  (both produce the same brief naked-eye interruption), but worth a sortie check that this does not
  read as the sight "stuttering" between glances.
- **Stage 2 is unscoped work for whoever picks it up** — flagged, not a gap in this plan's own
  scope (see Stage 2's note).

### Second-order effect

Simplifies what `BL-B66` (the 9K113 effector entry) inherits: three idle search legs instead of
four, and a near-empty out-of-regard excursion for the three named sectors, is less state for a
real slew-rate model to reason about transitioning through. It also gives `BL-B80`'s eventual
"quick look" binocular carve-out one fewer leg boundary to interact with. The deferred "quick
position check" (Decisions) is the one thread this plan deliberately leaves for a future pass
rather than guessing at now.

### Decisions Requiring User Input

- **"Quick position check" for a known, unmoved contact — build it, or leave the current
  "simply don't re-look" behaviour as the stand-in?** The explore notes name it explicitly but
  give no shape (how short, how it differs from an ordinary look, whether it reports anything).
  **Recommendation: leave it as the stand-in for now** — the stall cooldown already prevents the
  failure mode this guards against (indefinite re-looking), and a position-only look invents a new
  action class (shorter than a classification look, reports nothing new) with no flown example to
  calibrate against yet. Revisit once Stage 1 has flown and there is a concrete case where "he lost
  track of where it drifted to" is observed.
- **Confirm the wide band split (1.5–4 / 4–8 km) and the narrow-far-sweep band (8–13.6 km) as
  starting values.** Only the 1.5 km near edge is the user's own correction; the rest are the
  mock's placeholders, explicitly flagged as "should be tunable" rather than confirmed numbers.
  Flying it and adjusting via `config/tuning.toml` is the expected path, not a sign the defaults are
  wrong.
