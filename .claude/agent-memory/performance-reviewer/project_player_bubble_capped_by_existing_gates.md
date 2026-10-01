---
name: player-bubble-capped-by-existing-gates
description: player-bubble's measured per-tick saving is ~1.4%, not the ~77% its exclusion rate implies, because both channels' own pre-existing gates already bounded LOS/association reachability at or below 10km
metadata:
  type: project
---

`body-layer/src/perception/association.filter_player_bubble` (PLAYER_BUBBLE_RADIUS_M = 10000.0,
feature/player-bubble, reviewed 5c5bde6, 2026-10-02) drops ~76.6% of candidates per tick on the
real 2026-10-01 engagement trace (423 median candidates/tick). That sounds like a large saving,
but measured end-to-end it is ~1.4% (66.6ms -> 65.7ms/tick in a realistic pipeline benchmark),
because:

- `visibility.NAKED_EYE_RANGE_CAP_M` (naked-eye channel) and `association.RANGE_CAP_M` (hybrid
  channel, 5000.0, unconditional) already reject out-of-bubble candidates at a **cheap** gate,
  before the expensive terrain-LOS check (`check_visibility`'s gate order is cheap-before-LOS).
  `NAKED_EYE_RANGE_CAP_M` happens to equal `PLAYER_BUBBLE_RADIUS_M` (both 10000.0) today, so LOS
  was never reachable by an out-of-bubble candidate with or without this feature.
- LOS itself measured ~540us/candidate (flat-terrain fixture, `store.reader.sample_grid`, ~20
  interior points) — ~1000x the bubble filter's own ~0.53us/candidate cost. That 1000x gap is real
  and matters, but the bubble doesn't currently buy it, because nothing beyond 10km was reaching
  LOS before this feature existed either.
- The bubble's real payoff is structural/future: `PLAYER_BUBBLE_RADIUS_M` is deliberately kept
  independent of `NAKED_EYE_RANGE_CAP_M` (tests guard against aliasing), and will diverge once a
  wider-range optic (9K113, 20km cone) lands — that is when this filter starts actually saving
  LOS cost rather than duplicating an existing cheap gate.
- Same reasoning extends to [[project_contact_store_never_pruned]] / BL-B23: the bubble does not
  reduce ContactStore's accumulation rate today, since nothing beyond the pre-existing
  NAKED_EYE_RANGE_CAP_M could have been admitted before either.

**Lesson for future reviews**: an exclusion-rate percentage ("X% of candidates are out of range")
is not itself the saving — check what gate would have rejected those candidates anyway, and at
what cost, before attributing a performance win to a new upstream filter. Full numbers in
`plans/player-bubble/performance.md`.
