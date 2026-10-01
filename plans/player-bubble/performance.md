### Performance Review

Reviewed `feature/player-bubble` at tip `5c5bde6` (real change set: `6e3a2b7`, reviewed/corrected
by `824fea5`/`5c5bde6`). Scope: `filter_player_bubble()` in `body-layer/src/perception/
association.py`, called from `NakedEyePerceptionSource.poll()` and `HybridPerceptionSource.poll()`
right after `filter_ownship()`. body-layer runs this at 5 Hz against live DCS state — hot path, no
hard real-time budget yet (that starts with Petrobrain Runtime), but a live per-tick cost all the
same.

All numbers below are measured (`.venv` built fresh from `pyproject.toml`; microbenchmarks run
against the actual `filter_player_bubble`/`check_visibility`/`group_salient_ids`/`wgs84_to_dcs`/
`_resolve_velocity_by_object_id` functions, not models of them), not reasoned about.

**Real-mission scale** (`/Users/sg/dcs-detection-trace.jsonl`, 2 026-10-01 engagement replay,
2 072 630 trace rows, 3 749 distinct ticks — pre-dates this feature, so `true_range_m` is the raw
candidate pool the bubble would now filter):
- Median/p90/p99 tick size: 423 / 425 / 439 candidates. A handful of combat-burst ticks spike to
  20 000–203 000 (explosions/debris, not sustained load).
- **76.6% of all reported candidates sit beyond 10 km** on average across the whole trace, and the
  fraction holds (60–97%) even on the burst ticks. This is the pool the bubble removes from
  consideration before anything else runs.

#### Filter's own cost (focus area 2)

- `filter_player_bubble()` itself: **~0.53 us/candidate**, linear (measured 423→200 000
  candidates). At the real median tick (423) that's **0.22 ms/tick**; even at the worst observed
  burst (200 000) it's **106 ms**, still inside a 200 ms (5 Hz) budget on its own. It is one
  `GeoPosition` + one `range_m` (subtract, subtract, subtract, `sqrt`) per candidate — no
  projection, no `describe_position`, no per-candidate allocation beyond the output list. Not a
  risk.

#### What it actually saves (focus area 1) — smaller than the 76.6% figure suggests

This is the finding worth recording. A straight read of "76.6% of candidates excluded" implies a
correspondingly large saving, because the obvious next step for a surviving candidate is the
*expensive* one: `check_visibility`'s terrain-LOS gate, measured here (flat-terrain fixture,
`tests/support/mock_world_model.py`, `store.reader.sample_grid`) at **~540 us/candidate** — about
1000x the bubble filter's own per-candidate cost, confirming the "20-point sqlite grid sample per
LOS check" cost the code and prior agent-memory
([[project_terrain_watershed_scaling]]-adjacent) already flagged as expensive.

But that LOS cost was **never reachable by an out-of-bubble candidate in the first place**:
`check_visibility` gates cheap-before-expensive (gaze → cockpit mask → optic FOV → range/size →
LOS), and its own range/size gate is capped at `visibility.NAKED_EYE_RANGE_CAP_M = 10000.0` —
**the same 10 000 m as `PLAYER_BUBBLE_RADIUS_M`, today.** A candidate beyond 10 km was already
being rejected at that cheap gate, before LOS, with or without this feature. Equivalently for the
hybrid channel: `associate()`'s own `RANGE_CAP_M = 5000.0` is unconditional and stricter, so it
already rejected everything the bubble now also rejects (this is the no-op the implementer/
reviewer already recorded in `plans/player-bubble/implementation.md` and corrected in `5c5bde6`'s
log — confirmed correct by reading `associate()` directly).

End-to-end measurement, realistic scale (423 candidates, 76.6% beyond 10 km, flat-terrain fixture
so every in-bubble candidate reaches LOS): running `group_salient_ids` + a `check_visibility` loop
over the full candidate list vs. over the bubble-filtered list —

| | time/tick |
|---|---|
| without the bubble filter | 66.633 ms |
| with the bubble filter | 65.678 ms |
| saved | 0.955 ms (**1.4%**) |

The saving is real but comes from the *cheap* path, not the expensive one: avoiding `bearing_deg`/
`range_m`/profile lookups inside `check_visibility`'s own early gates for ~324 candidates/tick, and
avoiding the `O(n)` `_resolvable()` pass inside `group_salient_ids` (`perception/
group_salience.py`) over those same candidates (its `O(n²)` union-find only runs over the much
smaller *resolvable* subset, which far candidates already fail to join regardless of the bubble,
via their own tiny angular size). Nothing here is a defect — the function and its docstrings are
honest about being a computation-scope decision "not measured, deliberately," not a discovered
perf win. Worth recording precisely so it isn't later cited as removing LOS cost, which it does
not do today.

**Why it will matter more later, and already is the right call architecturally**: `association.py`'s
own docstring is explicit that `PLAYER_BUBBLE_RADIUS_M` and `NAKED_EYE_RANGE_CAP_M` are
independent constants that happen to share a value today and will diverge once the 9K113 sight
(20 km cone) lands — at that point the bubble is the only thing stopping a wider-range optic from
reinstating whole-pool LOS cost. Tests already guard the two constants against aliasing
(`test_player_bubble_radius_is_not_imported_from_visibility`). The structural correctness holds
independent of today's measured number.

#### Pre-existing velocity-join ordering (focus area 3)

`NakedEyePerceptionSource.poll()` runs `_resolve_velocity_by_object_id` and
`WorldObjectCandidate.from_dict` (which calls `coordinates.wgs84_to_dcs`, a cached-`pyproj`-
`Transformer` call) over **every** raw object, before `filter_player_bubble` sees any of them —
confirmed by reading `poll()` directly (lines ~443–471). Measured rather than inherited:

| step | per-candidate | at 423 candidates |
|---|---|---|
| `wgs84_to_dcs` | ~0.6–0.9 us | ~0.36–0.6 ms |
| `_resolve_velocity_by_object_id` (dict join) | ~0.2 us | ~0.09 ms |

Combined, well under half a millisecond at realistic scale. The reviewer's "cheap, pre-existing,
not worth reordering" judgement holds — now with numbers attached rather than inherited
unmeasured. **Action: LATER/MONITOR, not NOW.** Reordering would save well under 1 ms/tick today;
not worth the change given no budget pressure exists yet in this phase.

#### Hybrid channel's claimed no-op (focus area 4)

Confirmed by direct code reading of `associate()`: `RANGE_CAP_M = 5000.0` is applied
unconditionally (no bearing/hemisphere gating on the range check itself — the forward-hemisphere
window is a separate, later check), so every candidate the bubble drops at 10 km, `associate()`
would already have dropped at 5 km. The bubble changes nothing measurable for the hybrid channel
today. This matches `5c5bde6`'s own corrected log entry; nothing to add beyond confirming it from
the code rather than the log's own say-so.

### Findings

#### Player bubble filter cost
- **Location:** `association.filter_player_bubble`
- **Risk:** none at any realistic or burst scale measured (0.53 us/candidate, 0.22 ms/tick at the
  real median, 106 ms even at a 200 000-candidate burst tick).
- **Action:** MONITOR (no action expected to ever be needed; record the number for future
  reference).

#### Measured saving is small today, for a specific and recordable reason
- **Location:** `filter_player_bubble` interaction with `visibility.NAKED_EYE_RANGE_CAP_M` (naked-eye
  channel) and `association.RANGE_CAP_M` (hybrid channel).
- **Risk:** none — this is a record-the-finding item, not a defect. The risk it guards against is
  reputational/documentation: someone later citing "76.6% of candidates excluded" as the feature's
  perf win, when the measured win is ~1.4% because both existing per-channel gates already bounded
  LOS reachability at or below 10 km before this feature existed.
- **Action:** MONITOR. Re-measure once the 9K113 sight (20 km cone) lands and
  `NAKED_EYE_RANGE_CAP_M`/`PLAYER_BUBBLE_RADIUS_M` genuinely diverge — that is when this filter's
  real payoff appears, not today.

#### Pre-existing coordinate-transform + velocity-join cost ahead of the bubble
- **Location:** `NakedEyePerceptionSource.poll()`, `WorldObjectCandidate.from_dict` /
  `_resolve_velocity_by_object_id`, both run over the full raw pool before `filter_player_bubble`.
- **Risk:** low. Combined ~0.45 ms/tick at the real median scale (423 candidates); would need
  roughly two more orders of magnitude of candidates per tick before this became a budget concern,
  and no such scale appears in the real trace outside momentary combat bursts.
- **Action:** LATER. Reordering (bubble before `from_dict`/velocity-join) is a small, safe change
  whenever someone is already touching this code, but not worth a dedicated change now — measured
  saving would be under 1 ms/tick at realistic scale.

#### Hybrid channel bubble is a confirmed no-op
- **Location:** `HybridPerceptionSource.poll()` / `association.associate()`.
- **Risk:** none. Confirmed by code reading: `RANGE_CAP_M = 5000.0` unconditional, stricter than
  the bubble's 10 000 m.
- **Action:** MONITOR. No change needed; already documented in both constants' docstrings and the
  implementation plan.

#### BL-B23 interaction (ContactStore pruning, queued next)
- **Location:** `belief.contacts.ContactStore`, never pruned (`[[project_contact_store_never_pruned]]`).
- **Finding:** the bubble filters the *candidate* pool, not admitted contacts. Since nothing beyond
  `NAKED_EYE_RANGE_CAP_M` (10 km, same value as the bubble today) could ever have been admitted to
  a `ContactStore` entry before this feature either, **the bubble does not reduce the rate at
  which `ContactStore` accumulates** — that rate was already bounded by the pre-existing naked-eye
  range cap. BL-B23's own measurement should not assume the bubble changes its baseline; it will
  only start doing so once `NAKED_EYE_RANGE_CAP_M` and `PLAYER_BUBBLE_RADIUS_M` diverge (9K113
  sight), the same condition noted above.
- **Action:** MONITOR / informational for BL-B23's future measurement, not an action item here.

### Verdict
APPROVED — MONITOR

The implementation is correct, safe, and well-tested, and the architectural decision to keep
`PLAYER_BUBBLE_RADIUS_M` independent of `NAKED_EYE_RANGE_CAP_M`/`RANGE_CAP_M` is sound — it is what
makes the filter's real payoff available once a wider-range optic (9K113) exists. No change
required now. The one thing worth carrying forward is the corrected expectation: today's measured
per-tick saving is small (~1.4% end-to-end; both channels' own pre-existing range gates already
bounded LOS/association cost at or below the bubble radius), not the large reduction a naive read
of "76.6% of candidates excluded" would suggest. Re-measure when the two constants diverge.
