---
name: pb2-stage2-decay-events
description: PB-2/BL-2 Stage 2 (decay/certainty/lifecycle) implementation facts
metadata:
  type: project
---

Implemented `body-layer/src/belief/decay.py` (certainty ladder: observed/tracked/estimated/lost,
top-down over `now_sim - contact.last_seen_sim`) and `events.py` (CONTACT_DETECTED/LOST/
REACQUIRED derived from a certainty-transition comparison), wired into `ContactStore.tick`.

**PETROBRAIN_RUNTIME.md has no "§3.4 certainty table"** — no numbered sections exist in that
doc at all, and no concrete certainty enum/thresholds are specified anywhere. Its "Uncertainty
and memory decay" section only gives 4 attribute names (identity/position/general_area/motion)
+ 4 example sentences ("I see him."/"I think he was..."/"Last saw him..."/"I lost him."). A task
brief citing "§3.4" or a specific table in this doc should not be trusted at face value — grep
first, the plan's own text usually already anticipates this gap ("derive... otherwise make a
reasonable minimal set").

Only 3 of 5 named half-life constants are actually consumed (`OBSERVED_WINDOW_S=5s`,
`POSITION_HALF_LIFE_S=30s`, `LOST_THRESHOLD_S=120s=4x`); motion/general_area/identity half-lives
are declared-but-unused placeholders for BL-3/BL-4 attributes `Contact` doesn't have yet — this
is intentional (plan wants "one table" from the start), not dead code to clean up.

Deliberate design call not in the plan text: a contact whose *first* `tick()` already finds it
past `LOST_THRESHOLD_S` (last_emitted_certainty=None, current="lost") emits no event at all,
not a synthetic DETECTED+LOST pair. See [[feedback_decouple_fixtures_from_tuned_defaults]] for
the general pattern of documenting placeholder constants explicitly.

Modifying Stage 1's `test_tick_does_not_raise_and_does_not_mutate_contacts` was correct and
expected here (not a "don't touch existing tests" violation) — that test's own docstring and
`contacts.py`'s Stage 1 module docstring both explicitly earmarked `tick` as a Stage-2-fills-this-in
placeholder. Still recorded the change explicitly in implementation.md per house practice.
