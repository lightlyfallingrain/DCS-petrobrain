---
name: emitter-kind-answers-bypass-fired-not-emitter-exists
description: naked_eye_source.py/visibility.py -- VisibilityResult.emitter_kind means "the bypass fired", not "an Emitter was resolved"; conflating the two drops the fact for every unaided admission
metadata:
  type: project
---

`perception/visibility.py`'s `check_visibility` only sets `VisibilityResult.emitter_kind`
when the range/size or forest gate would otherwise have rejected the candidate and the
bypass actually fired (the tier-clamp section). It is **not** "was an `Emitter` resolved for
this candidate" -- that is a separate, always-available fact (`emitter_by_object_id.get
(candidate.object_id)` in `naked_eye_source.py`, independent of whether `check_visibility`
needed it).

**Why this matters**: `BL-B73` (targets_ownship) was built by gating the `targets_ownship`
bit on `result.emitter_kind is not None`, which silently means "only report taking fire if
the shooter would otherwise have been invisible" -- exactly backwards from the obvious case
(a shooter at 1 km, plainly visible, firing at ownship). The same conflation reached
`_build_observation`'s provenance fold too: the `targets_ownship` unanimity check lived
*inside* the `member_emitter_kinds == {"firing"}` branch, itself sourced from the same
bypass-only map, so fixing only the per-candidate dict would not have been enough.

**How to apply**: any time a new signal needs to "cross" from a resolved `Emitter`/collector
fact into an `Observation`/`Percept` field, check whether it is gated on `emitter_kind is
not None` (bypass fired) versus `emitter is not None` (fact exists). The two are **not** the
same population: "clearly visible and firing" is exactly the set where they diverge, and it
is the single most common real case a user will actually report from a sortie. Fixed in
`docs/acceptance/2026-10-20-sortie-feedback.md` F6 / `plans/taking-fire-visible-shooter/
debug.md`. Classification/tier (`achieved_tier`/`achieved_confidence` in `visibility.py`)
correctly *is* gated on bypass-fired (that's the invariant: emitter state must never raise
or reveal classification) -- only `targets_ownship`/provenance was wrongly gated the same
way. Don't "fix" the tier-clamp gating by analogy; it is correct as-is.

See also: `perception/emitters.py`'s `Emitter.targets_ownship` docstring (always `False` for
`BURNING`, so this conflation never affected burning callouts) and `belief/percept.py`'s
`_TARGETS_OWNSHIP_PROVENANCE` closed-mapping pattern (the only carrier of this fact across
the belief boundary is `Observation.provenance`, so a fix to the per-candidate dict alone,
without the provenance fold, is a silent no-op downstream).
