### Debug Report

### Observed Issue

First live sortie of PB-1.5's naked-eye channel produced obviously wrong output on nearly
every logged line:

```
t_sim=0.00  aircraft=(-387759.2, 387885.8, 871.1) source=naked_eye_visual_filtered classification=OP_GROUPSOMETHING bearing_deg=359.0 range_m=100
t_sim=2.25  ... bearing_deg=351.2 range_m=100
t_sim=7.41  ... bearing_deg=44.4  range_m=100
...
```

Four symptoms, all at once:
- `range_m` pinned at 100 (the smallest quantisation bucket) on every emission.
- `classification` always the `OP_GROUPSOMETHING` fallback.
- `bearing_deg` jumping erratically (359 -> 351 -> 44 -> 344 -> 6 -> 333 -> 34) while the
  aircraft flew an almost straight line.
- Emission recurring repeatedly despite `NakedEyePerceptionSource`'s per-object-id debounce,
  which is supposed to suppress a still-visible object after its first appearance.

The user confirmed the real targets in the scenario were nowhere near 100 m away, ruling out a
mundane "there really was something 100 m away" explanation.

### Hypothesis

**Root cause (confirmed): no ownship exclusion anywhere in the perception pipeline.**
`LoGetWorldObjects` is confirmed global, unfiltered ground truth (`aircraft-layer/src/schema/
world_objects.py`'s docstring, backed by a primary-source forum thread: "in multiplayer... it
returns data from all devices"), and it includes the player's own aircraft. Neither
`naked_eye_source.py` nor `association.py` filtered it out. When the player's own aircraft
shows up as a `WorldObjectCandidate`, its position is (to within a small residual) identical
to `ownship_state`'s own position, so:
- `range_m(observer, target)` is near zero -> quantises to the smallest bucket, `100`.
- `bearing_deg(observer, target)` is `atan2(delta_z, delta_x)` over a near-zero vector -- highly
  sensitive to whatever small residual separates the two independently-reported positions for
  the same aircraft, so it swings wildly from poll to poll.
- `object_model.profile_for("Mi-24P")` matches no keyword (aircraft types are out of scope for
  `object_model.py`'s table by design) -> falls back to `OP_GROUPSOMETHING`.
- All three `visibility.check_visibility()` gates trivially pass against oneself (FOV: some
  bearing is always "somewhere"; range: near-zero is always under threshold; LOS: sightline to
  one's own position is never blocked by terrain).

**Cause 2 (object_id instability breaking the debounce): investigated, not confirmed, and not
needed to explain the observed symptoms.** A reproduction (below) shows that with a *stable*
`object_id` across polls, the existing per-object-id debounce correctly suppresses a
still-visible ownship echo -- the live log's repeated-but-irregularly-timed emissions are fully
explained by the FOV gate itself flapping in and out as the near-zero-baseline bearing jitters
past the 60-degree window edge each poll, which defeats the *intent* of the debounce (stable
visibility) without requiring `object_id` to actually change. Whether `LoGetWorldObjects`'s
`pairs()`-iteration key is in fact stable across polls remains genuinely unconfirmed either way
-- no evidence for or against was found this session, and it cannot be resolved without a live
DCS probe (see "Needs live DCS" below).

### Evidence

1. **Code-level confirmation of the missing exclusion**: read `naked_eye_source.py`,
   `association.py`, and `aircraft-layer/src/schema/world_objects.py` in full -- no ownship
   filtering exists anywhere in the candidate pipeline for either channel.

2. **Quantiser ruled out as a competing explanation**: `_quantise_range_m` was exercised
   directly across its whole ladder (0/99/100/101/549/1000/1400/2600/4200/12000 m) and maps
   correctly at every point; only an input <=100 m yields the `100` output seen live. The near-
   zero range genuinely reaches the quantiser as an input, it isn't a display/bucketing
   artefact.

3. **Coordinate round-trip precision ruled out as the source of the near-zero range**: measured
   `wgs84_to_dcs(dcs_to_wgs84(x, z))` round-trip error for the Syria theatre at the logged
   aircraft position -- residual ~6.6e-10 m, many orders of magnitude too small to produce a
   ~100 m (bucketed) apparent range or the observed bearing jitter. The near-zero range is a
   real, physical near-coincidence (ownship vs. ownship), not a projection artefact.

4. **Positive, mechanistic reproduction of all four symptoms from cause 1 alone.** Using the
   project's own test harness pattern (identity-mapped `wgs84_to_dcs`, forced-true
   `line_of_sight_clear`), a `WorldObjectCandidate` for `"Mi-24P"` placed within a few metres of
   `OwnshipState`'s own position -- modelling exactly what `LoGetWorldObjects` returning the
   player's own aircraft alongside independently-computed ownship telemetry would look like --
   reproduces the live output almost verbatim across repeated small random offsets:

   ```
   jitter=(0.528,-0.490) bearing=310.0 range=100.0 class=OP_GROUPSOMETHING
   jitter=(0.303,0.577) bearing=70.0  range=100.0 class=OP_GROUPSOMETHING
   jitter=(0.672,-0.134) bearing=340.0 range=100.0 class=OP_GROUPSOMETHING
   jitter=(0.878,-0.238) bearing=340.0 range=100.0 class=OP_GROUPSOMETHING
   jitter=(0.675,0.113)  bearing=10.0  range=100.0 class=OP_GROUPSOMETHING
   ...
   ```
   Range pinned at 100, classification always `OP_GROUPSOMETHING`, bearing scattered across the
   compass -- matching the live symptom set exactly.

5. **Debounce mechanism itself verified correct, isolating cause 2 as unnecessary.** Re-running
   the same reproduction with one persistent `NakedEyePerceptionSource` instance and a *stable*
   `object_id` across 20 successive polls (only the position residual varying, as it plausibly
   would from tick to tick even for the same real-world object pair) produced 5/20 emissions
   with irregular spacing -- not one emission (debounce would work if the object stayed
   continuously visible) and not 20/20 (which is what a truly broken debounce, e.g. from
   `object_id` reshuffling every poll, would look like). This is the FOV gate itself admitting
   and excluding the near-self object as its jittery bearing crosses the 60-degree window edge,
   which independently explains the live log's irregular-but-repeated timing (7 emissions over
   ~23 s) without needing `object_id` instability at all.

### Fix Applied

Added `perception.association.exclude_ownship(candidates, ownship) -> list[WorldObjectCandidate]`
and a named constant `OWNSHIP_ECHO_EXCLUSION_RADIUS_M = 50.0` (well above the Mi-24P's own
physical extent, ~17 m fuselage/rotor span, and any plausible per-tick position residual
between `LoGetSelfData`-derived ownship telemetry and `LoGetWorldObjects`'s own-aircraft entry;
well below both channels' real range caps of 2500-5000 m, so it cannot plausibly suppress a
real target). Drops any candidate within that radius of ownship's own position.

Wired into both channels that build a `WorldObjectCandidate` list from the same unfiltered
`LoGetWorldObjects` snapshot, per the task's note that `association.py`/the scope channel has
the identical missing-exclusion bug:
- `NakedEyePerceptionSource.poll()` (`naked_eye_source.py`) -- candidates run through
  `exclude_ownship()` before `visibility.check_visibility()`.
- `HybridPerceptionSource.poll()` (`hybrid_source.py`) -- candidates run through
  `exclude_ownship()` before `association.associate()`.

This is a body-layer-only fix; `aircraft-layer/`'s `Export.lua`/`world_objects.py` are
unchanged (see "Needs live DCS" below on why the exclusion was not attempted at the DCS-export
layer instead).

**Cause 2 was not fixed.** Per the Debugger role's "no speculative fixes" rule: it remains
unconfirmed, and the observed bug is already fully explained without it (see Evidence 5). No
change was made to `object_id`-keyed debounce logic in either channel.

### Verification

From `body-layer/`:
```
ruff format --check src tests   # 23 files already formatted
ruff check src tests            # All checks passed
mypy src                        # Success: no issues found in 12 source files
PYTHONPATH=src:../world-model/src pytest tests -q   # 102 passed
```

Added regression coverage:
- `test_association.py`: `exclude_ownship` drops a near-coincident candidate, keeps a candidate
  outside the radius, and drops (not keeps) a candidate exactly at the radius boundary (matches
  the strict `>` in the implementation).
- `test_naked_eye_source.py`: an ownship-echo-only snapshot emits nothing; an ownship echo
  alongside a real distant target still emits only the real target.
- `test_hybrid_source.py`: an ownship-echo-only snapshot causes the detection to drop (no
  candidate survives to associate against); an ownship echo alongside a real target still
  associates correctly with the real target.

All pre-existing tests continue to pass unmodified (101 before this fix's 6 new tests -> 102
total), confirming no regression to either channel's existing filtering/debounce/cap behaviour.

### Needs live DCS (not resolved this session)

- **Positive confirmation that `LoGetWorldObjects` actually includes the player's own aircraft
  in single-player, not just the multiplayer case the cited forum thread confirms.** Capture:
  with the aircraft-layer collector running against a live single-player mission, grep a
  captured `world_objects` snapshot (or `aircraft_layer_debug.log` via the `dcs-log-recon`
  skill) for an object whose `lat_deg`/`lon_deg`/`altitude_m` closely track the same poll's
  `/telemetry/latest` position over several consecutive samples. If found, that positively
  confirms the exact mechanism (rather than the strong-but-indirect reproduction in Evidence 4
  above); it also lets `OWNSHIP_ECHO_EXCLUSION_RADIUS_M` be tuned against the real observed
  residual instead of the current, un-tuned 50 m guess.
- **Whether `LoGetWorldObjects`'s `pairs()`-iteration key (`object_id`) is stable across polls
  for the same underlying object** -- cause 2, still open. Capture: log `object_id` +
  `object_type` + position for every object across several consecutive polls of a scene with at
  least one persistent, slow-moving real unit, and check whether the same physical unit keeps
  the same `object_id` from poll to poll. This is unrelated to the fix in this report (which
  does not depend on `object_id` stability) but remains a live question for the debounce
  mechanism generally, worth resolving before relying on it more heavily.
