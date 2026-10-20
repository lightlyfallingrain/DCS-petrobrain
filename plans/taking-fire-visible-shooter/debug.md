### Debug Report

### Observed Issue
A ground unit firing AT ownship, already visible to Petrovich without needing its muzzle
flash to be seen (an ordinary, unaided admission — no range/size or forest bypass needed),
never produced "Taking fire, X o'clock". `docs/acceptance/2026-10-20-sortie-feedback.md`
F6 and its follow-up: a Leopard-2A5 at 1,073 m with the collector's `/firing/latest` holding
`targets_ownship: true` was admitted once as an ordinary contact (`CONTACT_14`, presence
tier) and never became a firing contact.

Gaze gating (reason 1 in the doc) was confirmed by the user to be correct behaviour and is
untouched by this fix.

### Hypothesis
`perception/naked_eye_source.py` computed `targets_ownship_by_object_id` gated on
`result.emitter_kind is not None` — i.e. "only when the emitter bypass was actually needed".
`VisibilityResult.emitter_kind` (`perception/visibility.py` gates 3/5, "Emitter bypass"
section) is non-`None` only when the range/size or forest gate would otherwise have rejected
the candidate. A shooter in plain view at 1 km clears those gates unaided, so `emitter_kind`
stays `None` even though `check_visibility` was given a resolved, `targets_ownship=True`
`Emitter` for that candidate. The bit that should drive "taking fire" was being thrown away
exactly when the shooter was easiest to see.

Downstream, `_build_observation`'s provenance fold compounded this: `PROVENANCE_EMITTER_
FIRING_TARGETS_OWNSHIP` was only ever considered *inside* the branch gated on `member_
emitter_kinds == {"firing"}` — which is itself sourced from the same bypass-only
`emitter_kind_by_object_id` map. So even fixing `targets_ownship_by_object_id` alone would
not have been sufficient; the provenance fold never reached the `targets_ownship` check for
a non-bypassed admission.

### Evidence
- Read `perception/visibility.py` lines ~994-1060: `emitter_kind` is set only when
  `range_bypassed or forest_bypassed` is true (the tier-clamp section), confirming it answers
  "did the bypass fire", not "is there a resolved emitter for this candidate".
- Read `perception/naked_eye_source.py` lines ~872-897 (before fix): `targets_ownship_by_
  object_id[...] = result.emitter_kind is not None and emitter is not None and emitter.
  targets_ownship` — the first conjunct is the defect.
- Read `_build_observation` (lines ~1238-1268, before fix): the `targets_ownship` unanimity
  check lived inside `if only_emitter_kind == EmitterKind.FIRING.value`, itself gated by
  `member_emitter_kinds` built from the same bypass-only map.
- Added a failing test reproducing the live case exactly: a T-72B at 200 m (well inside its
  own hires threshold, no bypass needed) with `firing=_firing_active_map("unit_1",
  targets_ownship=True)`. Before the fix: `observations[0].provenance ==
  PROVENANCE_VISIBILITY_FILTER_ONLY` (assertion failure — expected
  `PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP`). Confirmed via `pytest -k
  visible_unit_firing_at_ownship`.
- Traced `belief/percept.py::percept_of`: `Percept.targets_ownship` is derived solely from
  `observation.provenance in _TARGETS_OWNSHIP_PROVENANCE` (membership test against
  `{PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP}`) — confirming `Observation.provenance` is the
  *only* carrier of this fact into `belief/`, so the fix has to land in the provenance fold,
  not just the per-candidate dict.
- Investigated the "firing-at-others" wording separately (per dispatch instruction): the same
  "only when the bypass was needed" gating on `emitter_kind_by_object_id` **does** suppress
  `PROVENANCE_EMITTER_FIRING` ("something firing... far") for a visible, no-bypass-needed unit
  firing at something other than ownship — confirmed with
  `test_a_visible_unit_firing_at_others_keeps_ordinary_provenance`, which passes unchanged
  both before and after this fix (provenance stays `PROVENANCE_VISIBILITY_FILTER_ONLY`). The
  user's doc only specifies the targets-ownship case ("Petrovich should definetely see the
  unit firing at me"); the firing-at-others case for an already-visible unit is left as-is,
  per the dispatch's explicit scope instruction.

### Fix Applied
Two changes in `body-layer/src/perception/naked_eye_source.py`, both in
`NakedEyePerceptionSource`:

1. `targets_ownship_by_object_id` (built in `poll`) no longer requires
   `result.emitter_kind is not None`. It is now `emitter is not None and emitter.
   targets_ownship` — the collector's own fact, read for every gate-admitted candidate
   regardless of whether a bypass fired.
2. `_build_observation`'s provenance fold now checks `member_targets_ownship == {True}`
   **first, independently of `member_emitter_kinds`**, producing
   `PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP` whenever every cluster member's (now
   bypass-independent) `targets_ownship` is unanimously `True`. The existing
   `member_emitter_kinds`-driven branch (plain `PROVENANCE_EMITTER_FIRING` for firing-at-
   others, and the `_PROVENANCE_BY_EMITTER_KIND` lookup for `BURNING`) is otherwise
   byte-identical to before and only reached when the targets-ownship check does not apply —
   so it still only fires when the bypass was actually needed, exactly as before.

No change to `visibility.py`'s tier clamp or gate chain: the fix does not touch whether or
when a bypass fires, only how the already-resolved `targets_ownship` fact is read downstream.
Classification/tier is unaffected, verified by asserting `classification_raw == "T-72B"`
(exact hires-tier id, not `DEFAULT_OP_CLASS`) in the new passing test.

Updated the two doc comments/docstrings this changed (the `targets_ownship_by_object_id`
comment and `_build_observation`'s own docstring section on `provenance`) to describe the new
ordering rather than leaving a stale "only meaningful when the bypass was needed" claim in
place.

### Verification
- New test `test_a_visible_unit_firing_at_ownship_sets_the_targets_ownship_provenance`:
  failed before the fix (reproduction), passes after.
- New regression tests, both pass unchanged before and after the fix (confirming no scope
  creep):
  - `test_a_visible_unit_firing_at_others_keeps_ordinary_provenance` — a visible,
    no-bypass-needed unit firing at something else still gets ordinary provenance.
  - `test_a_visible_burning_unit_keeps_ordinary_provenance` — a visible, no-bypass-needed
    burning unit still gets ordinary provenance (`BURNING` never carries `targets_ownship`
    anyway).
- Full existing suite for the touched module: `pytest tests/test_naked_eye_source.py` — 57
  passed (up from 54; 3 new tests), no existing test needed to change.
- Whole-project body-layer suite: `pytest -q` — 2242 passed, 4 xfailed. One unrelated failure
  on the first run, `test_mission_start_reset.py::test_check_for_new_mission_keeps_the_
  traceback_for_a_non_connection_failure` (a `ConnectionRefusedError` from an unrelated
  `brain_client` poll bleeding into log-capture state from a preceding test); passed in
  isolation and on a full rerun — a flake, not caused by this change.
- `ruff format --check src tests` (one pre-existing formatting diff in the new test code,
  fixed by running `ruff format`), `ruff check src tests` (clean), `mypy src` (clean, 68
  files) — all from inside `body-layer/`.
