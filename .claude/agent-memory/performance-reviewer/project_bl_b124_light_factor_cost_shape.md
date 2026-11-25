---
name: bl-b124-light-factor-cost-shape
description: BL-B124's light-level astronomy/light_factor split -- measured costs, so a future reviewer doesn't re-derive them from scratch
type: project
---

`body-layer/src/perception/light_level.py`, wired by `[[BL-B124]]`: `sun_elevation_deg()` (real
solar-position trig) is resolved exactly once per poll in `body.py::_resolve_sun_elevation_deg`
and cached on `self.light_level_sun_elevation_deg`; `light_factor(optic, sun_elevation_deg)` (a
cheap piecewise-linear lookup over 3 measured anchors) is resolved per-optic at every one of
`belief/optic_policy.py`'s six `tier_ranges()` call sites, via `_light_factor_for`, which is the
choke point every "is it worth raising this instrument" decision in that module already shares
(`[[feedback_tier_ranges_is_the_choke_point]]`).

**Measured** (`body-layer/.venv`, `perception.light_level` directly):
- `sun_elevation_deg()`: ~1.25 µs/call, called once per poll.
- `light_factor()`: ~0.95 µs/call. A representative busy poll (30 candidates × 4 named optics,
  deliberately over-counting — the real ladder loop short-circuits on the first sufficient rung)
  costs ~114 µs total, against a 1,000,000 µs (1 Hz) budget.

**Why this shape matters generally, not just for this feature**: the expensive, genuinely
per-poll-invariant quantity (sun elevation — a pure function of mission clock + position, the
same for every optic and every candidate this poll) is computed once and threaded as a raw float;
the cheap, genuinely per-optic quantity (the measured factor curve) is resolved locally at each
comparison site rather than precomputed once and shared across optics
(`[[feedback_shared_value_across_multiple_optics_in_one_call]]` — a shared precomputed value would
have been a *correctness* bug here, since different optics' curves differ, but it is also the
right performance shape: the per-optic cost is cheap enough that resolving it fresh at each
comparison was never a real tradeoff). Worth recognizing this pattern — "one expensive
poll-invariant computation, several cheap per-entity lookups fed by its raw output" — as *not*
needing precomputation/caching on the cheap side even though the raw advice ("prefer
precomputation") might suggest hoisting it further; here the correctness constraint and the
performance constraint point the same way.

See also `[[project_body_layer_poll_loop_serial_unpooled_gets]]` — this feature's one extra
`GET /firing/latest` round-trip per poll is the Nth instance of that already-accepted pattern, not
a new cost class.
