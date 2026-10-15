---
name: feedback-provenance-is-not-a-free-pass-across-percept-boundary
description: an implementer removed "provenance" from test_percept.py's forbidden truth-field set to let Contact.is_burning learn from it -- judged this a required fix on emitter-visibility review, because a free-form str crossing the boundary defeats the structural guard even when every current value is self-descriptive
metadata:
  type: feedback
---

On `feature/emitter-visibility` (`BL-B72` Stage A), the plan explicitly promised *"No schema change
to `Observation`, `Percept` or `Contact`"* for the provenance mechanism, then turned out to need one
anyway (`Contact.record` only ever sees a `Percept`, never raw `Observation`, so `Contact.is_burning`
had no other way to learn "this came from the emitter bypass"). The implementer's fix was to add
`Percept.provenance: str | None` and remove `"provenance"` from `test_percept.py::test_percept_has_
no_truth_carrying_field`'s forbidden set, arguing `provenance` is channel-self-description (same
footing as `classification_level`/`count_bucket`), not DCS-truth.

**Judged this a required fix, not an approval.** The argument is correct about every value
`provenance` holds *today*, but the field's declared type is a bare `str`, not a closed enum --
nothing stops a future producer from folding something richer into it once it's known to cross the
boundary freely. `hybrid_source.py`'s own existing value
(`"petrovich_indication+world_objects/ambiguous_association"`) already names internal pipeline
uncertainty, not a perceived fact -- a milder instance of exactly the leak the test exists to catch.
The cheaper, correct fix: add a narrow, purpose-built field (`Percept.emitter_kind: str | None`,
mirroring the already-existing `VisibilityResult.emitter_kind`/`DetectionTrace.emitter_kind`) instead
of letting the open-ended string through, so the guard test never needs touching at all.

**Why this matters beyond this one review:** a test that exists to make "does this field carry
something `Percept` shouldn't see" a *structural* question (introspect the dataclass, don't just
build one correctly -- the test's own docstring) stops being structural the moment the set it
checks against is edited to exclude the field in question. After the edit, the guarantee is a
comment in a test file, not a guard. **Treat any PR that edits a project-invariant guard's own
enumerated exclusion/inclusion set as the headline finding, not a footnote** -- the implementer in
this case flagged it correctly per their own role instructions, and the right response was to judge
it hard on the merits (per [[project_configurable_constants_crosskey_assert_gap]]'s general lesson:
per-field review is not the same shape of safety net as the invariant the guard exists to enforce),
not to wave it through because the stated argument for the one current value was sound.

**How to apply:** whenever a diff removes an entry from a forbidden-field-names set, a denylist, or
similar enumerated guard, ask not "is this specific value safe" but "what mechanically stops the
next value through this same gap from being unsafe." If the answer is "nothing, just discipline,"
the narrower field-level fix is almost always available and almost always cheaper than it looks --
the existing narrow signal (`emitter_kind` here) was already sitting one layer up, unused for this
purpose only because nobody had reached for it yet.
