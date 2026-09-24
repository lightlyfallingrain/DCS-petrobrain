---
name: project-belief-los-call-pattern
description: LOS calls in ContactStore.tick's engagement block were unconditional, not gated by range/alt -- a recurring shape to check for
metadata:
  type: project
---

In `feature/watch-reporting` (2026-09-24 review), `ContactStore.tick`'s engagement block
(`body-layer/src/belief/contacts.py`) computed `range_ok`/`alt_ok`/`los_ok` all up front and only
combined them (`range_ok and alt_ok and los_ok`) at the end, instead of short-circuiting the
expensive `los_ok` term behind the cheap `range_ok and alt_ok` terms. LOS (`world-model`'s
`query.line_of_sight.line_of_sight_clear`, via `perception.geometry.line_of_sight_clear`) samples
elevation against an on-disk SQLite store -- by a wide margin the most expensive primitive
`belief/` can reach, confirmed by the project's own task framing and by this review's harness
(LOS call count scales 1:1 with watched-contact count regardless of whether the contact is even
inside its own threat envelope).

**Why this is worth remembering:** the deadband/dwell mechanisms this project builds around
expensive per-tick checks (`RANGE_CROSS_MIN/MAX`, `LOS_MASK_CONFIRM_S`) are easy to mistake for
cost controls on the call itself. They aren't -- they gate whether a *result* is allowed to
produce an *event*, after the expensive call has already run. The only real cost control is a
short-circuit *before* the call, gated on cheap prerequisites (here: range/altitude) that are
already being computed for the boolean anyway.

**How to apply:** whenever a plan introduces a cheap-precondition + expensive-check + dwell/
deadband combination (common in this codebase's belief-folding functions), check the order of
evaluation specifically -- `a and b and expensive()` short-circuits correctly in Python, but
`expensive_result = expensive(); ...; a and b and expensive_result` (compute-then-combine, which
is what a docstring-driven, each-term-explained implementation naturally falls into) does not.
Ask directly: "is the expensive call already behind the cheap gate, or just combined with it
afterward?" See [[project_watch_reporting_scale_notes]] for the specific numbers from this review.
