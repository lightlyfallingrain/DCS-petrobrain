---
name: taking-fire-visible-shooter-security-approved
description: Security deep-analysis verdict for fix/taking-fire-visible-shooter (F6/F6-follow-up) — APPROVED; where to look to verify "no-omniscience" mechanically for a bypass-independent emitter-fact fix
metadata:
  type: project
---

`plans/taking-fire-visible-shooter/security-review.md`, reviewed at tip
`59eea0854589bd0a340a2f8a07a2bf9cfde83e3b`. **APPROVED**, no findings.

**Why this one is worth remembering beyond the verdict**: it is the fix that closes the gap
`project_emitter_kind_bypass_conflation.md` (debugger memory) describes — `targets_ownship`/
firing facts were gated on "did the emitter bypass fire" instead of "does an `Emitter` fact
exist", which silently suppressed "taking fire" for exactly the easiest-to-see shooter. The fix
makes the per-candidate dicts (`targets_ownship_by_object_id`, `firing_by_object_id`) read
`emitter is not None` instead of `result.emitter_kind is not None`.

**The one-line mechanical check that settles "can this leak to an unperceived unit"**: both new
dicts are built by `for candidate, _result in visible:` — `visible` is the list `check_visibility`
already gated through gaze/cockpit mask/optic FOV/terrain LOS (gates this kind of fix never
touches). Confirming the loop source is `visible`, not `raw_objects`/the full `emitter_by_object_
id` map, is the whole no-omniscience argument — cheaper than tracing the fold logic itself, and
is the first thing to check on any future "surface a bypass-independent fact" fix in this module.

**Wire-boundary re-check, found unnecessary**: `perception/emitters.py::firing_emitters` (the
`/firing/latest` parser) was untouched by this diff (`git diff --stat` confirms) — its
`isinstance`/dict-type/`.get()`+`bool()`-coercion validation was reviewed at Stage B
([[emitter-visibility-stage-b-approved]]) and still holds: missing/non-bool/unknown-name all
degrade to `False`/dropped, never a crash. **Check `git diff --stat` for the parser file before
re-deriving its validation from scratch** — a diff that only touches the *consumer* of an
`Emitter`/wire fact doesn't need the producer re-audited.

**Verification method used**: ran the touched test modules myself (`pytest tests/test_naked_eye_
source.py tests/test_percept.py tests/test_speech.py`, 259 passed) rather than trusting the two
reviewer passes' pasted counts; read the citation-fix commit (`59eea085`) line-by-line to confirm
it really is a pure `plan.md`→`debug.md` string swap with zero logic change, since a "mechanical,
no behaviour change" claim is exactly the kind of claim worth one `git show` rather than taking on
trust.

See also [[emitter-visibility-stage-a-approved]], [[emitter-visibility-stage-b-approved]] for the
closed-mapping pattern this fix extends (three `PROVENANCE_EMITTER_FIRING*` values now, same
`frozenset`-membership shape).
