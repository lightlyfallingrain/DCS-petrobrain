### Implementation Summary

Second half of the fix, dispatched separately from `debug.md`/`review.md` above (which closed
the targets-ownship half of F6). Scope: a unit Petrovich can SEE (admitted without needing the
emitter bypass) that is firing at someone OTHER than ownship must now be reported as firing, at
whatever classification tier the ordinary admission already earned -- never raised by the
emitter fact. The existing bypass-needed case ("something firing... far", no type, no range)
is untouched.

The design mirrors the targets-ownship fix exactly: a third `PROVENANCE_EMITTER_FIRING_VISIBLE`
value, produced only when every cluster member is (a) currently firing, (b) was *not*
emitter-bypass-admitted, and (c) not targeting ownship (case (a) of the existing
`PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP` branch, checked first and unchanged); carried across
the `belief/` no-omniscience boundary through a second closed mapping (`Percept.firing_visible`,
alongside the existing `Percept.targets_ownship`); threaded through `Contact`/`Event` the same
way `firing_targets_ownship`/`targets_ownship` already are; rendered in `belief/speech.py` by
reusing `_contact_report_text` (the ordinary contact-report line) with `event_clause="firing"` --
not a new bespoke line, per the dispatch's "reuse the existing machinery" instruction.

### Files Changed

- `body-layer/src/perception/naked_eye_source.py` -- new `PROVENANCE_EMITTER_FIRING_VISIBLE`
  constant; a new bypass-independent `firing_by_object_id` dict built in `poll()` (mirrors
  `targets_ownship_by_object_id`'s own bypass-independent read of `emitter_by_object_id`);
  threaded through `_build_observations`/`_build_observation`; `_build_observation`'s provenance
  fold gained a second priority tier (`member_firing_visible == {True}`) between the existing
  targets-ownship check and the existing bypass-gated `member_emitter_kinds` check. Pruned/updated
  three comments this change stood next to and made stale: the `PROVENANCE_EMITTER_FIRING`
  declaration comment (used to claim unconditionally that a mixed-targets cluster "keeps the
  ordinary `PROVENANCE_EMITTER_FIRING` value" -- now true only when every member still needed the
  bypass), the `targets_ownship_by_object_id` comment's closing sentence (used to claim the
  "firing at others" wording was wholly unaffected by that change -- true only for the
  bypass-needed half of it now), and `_build_observation`'s own provenance docstring (rewritten as
  a three-step priority list rather than two).
- `body-layer/src/belief/percept.py` -- new `_VISIBLE_FIRING_PROVENANCE` frozenset (mirrors
  `_TARGETS_OWNSHIP_PROVENANCE`) and `Percept.firing_visible: bool = False` field, populated in
  `percept_of`. `_EMITTER_KIND_BY_PROVENANCE` gained the third mapping entry (still -> `FIRING`).
- `body-layer/src/belief/contacts.py` -- new `Contact.firing_visible: bool = False` field, written
  in `record`/`from_percept` the same "written only when `is_firing` is also being set this look"
  way `firing_targets_ownship` already is; `tick`'s `CONTACT_FIRING_SEEN` emission now passes
  `firing_visible=contact.firing_visible` to the `Event`.
- `body-layer/src/belief/events.py` -- new `Event.firing_visible: bool = False` field (mirrors
  `targets_ownship`); updated the stale "two `PROVENANCE_EMITTER_FIRING*` values" count in
  `CONTACT_FIRING_SEEN`'s own docstring to three.
- `body-layer/src/belief/speech.py` -- `CONTACT_FIRING_SEEN`'s rendering gained a third branch:
  `event.firing_visible` -> `_contact_report_text(result["facts"], event_clause="firing")`,
  checked after `event.targets_ownship` ("Taking fire...") and before the fallback bypass-needed
  "Something firing... far." wording. No new bespoke line.
- `body-layer/src/belief/callouts.py` -- **not changed.** `callout_priority`'s existing
  `_FIRING_THREAT_BAND` branch already applies to every `CONTACT_FIRING_SEEN` event with
  `targets_ownship=False`, which the new `firing_visible` case is a member of (it is a different
  *wording* branch at speech time, not a different *kind* or *target* at callout time). That
  already outranks `_DEFAULT_THREAT_BAND` (ordinary contact reports) unconditionally, and within
  the shared band, `range_m` already sorts the nearer one first -- satisfying "especially if
  close" without a new band. The pre-existing
  `test_callout_priority_firing_not_targeting_still_outranks_default_band` already pins this for
  any non-targeting `CONTACT_FIRING_SEEN`, the new case included, so no new callouts test was
  needed either.

### Tests Added

- `test_a_visible_unit_firing_at_others_gets_the_firing_visible_provenance` (renamed from
  `test_a_visible_unit_firing_at_others_keeps_ordinary_provenance`, same single-member fixture) --
  **existing test rewritten, not just extended: its expectation flips.** It used to pin
  `PROVENANCE_VISIBILITY_FILTER_ONLY` as the deliberate scope boundary of the targets-ownship fix;
  it now pins `PROVENANCE_EMITTER_FIRING_VISIBLE` as this fix's own positive case, with
  `classification_raw == "T-72B"` still asserted to prove the emitter fact never raised or
  lowered the tier.
- `test_two_clustered_visible_units_both_firing_at_others_get_the_firing_visible_provenance` --
  genuine 2-member cluster (same down-range clustering recipe as
  `test_two_close_candidates_emit_one_clustered_observation`), both members visible and firing at
  others: unanimous `True` -> `PROVENANCE_EMITTER_FIRING_VISIBLE`. Closes the reviewer's
  "every fold test uses a single-member cluster" gap for this new branch specifically.
- `test_a_mixed_firing_cluster_degrades_to_ordinary_provenance` -- same 2-member cluster, only one
  member firing: disagreement degrades to `PROVENANCE_VISIBILITY_FILTER_ONLY`.
- `test_a_cluster_mixing_targets_ownship_and_firing_at_others_degrades` -- same 2-member cluster,
  one member targeting ownship and the other firing at others (both visible, both firing):
  neither `member_targets_ownship` nor `member_firing_visible` is unanimous, so this degrades to
  `PROVENANCE_VISIBILITY_FILTER_ONLY` rather than picking either firing wording -- the interaction
  between the two new/existing unanimity checks that no single-member test could ever exercise.
- `test_percept_of_maps_visible_firing_provenance_to_firing_visible_true` /
  `test_percept_of_maps_every_other_provenance_to_firing_visible_false` -- `Percept.firing_visible`
  mapping, mirroring the existing `targets_ownship` mapping tests; the latter also checks the
  other two `FIRING` provenance values map to `firing_visible=False` (it is "admitted without the
  bypass", not "is firing" in general).
- `test_percept_of_maps_both_firing_provenance_values_to_firing_kind` -- **existing test extended**
  (not rewritten): added the third `PROVENANCE_EMITTER_FIRING_VISIBLE` case alongside the existing
  two, and corrected its docstring's "both"/"two" wording to "three".
- `test_route_event_contact_firing_seen_visible_firing_at_others_says_type_and_range` -- the
  speech wording itself: asserts `startswith("BMP-2, ")`, `"o'clock" in text`,
  `endswith(", firing.")`, and that neither "far" nor "taking fire" appear. The exact range figure
  is deliberately not pinned -- `_enrichment_context`'s faked `project_terrain_aware` (an identity
  stub standing in for a real world-model DB) collapses the believed position onto ownship's own,
  producing `_format_range_km`'s `"very close"` branch regardless of the observation's own
  `range_m`; the same fixture quirk `test_route_event_contact_detected_includes_clock_range_when_
  enriched` already works around with a loose check rather than the literal text (verified by
  running the test against the fixture before choosing the assertion style -- the first attempt,
  pinning the literal rendered string, is what surfaced this).

### Checks

(all run from inside `body-layer/`; worktree has no `.venv`, borrowed
`/mnt/e/DCS-petrobrain/body-layer/.venv/bin/`)

- `ruff format --check src tests`: pass (155 files already formatted)
- `ruff check src tests`: pass
- `mypy src`: pass (68 files, no issues)
- `pytest -q` (whole subproject): pass -- 2248 passed, 4 xfailed (up from 2242 passed before this
  change; +6 new tests, as listed above). No flake observed this run (the two documented
  intermittent connection-reporter flakes did not trigger).

### Notable Discoveries

- **`callout_priority` needed no change at all.** The urgency ordering is keyed on
  `event.kind`/`event.targets_ownship`, not on which `PROVENANCE_EMITTER_FIRING*` value produced
  the event, so the new `firing_visible` case automatically inherits `_FIRING_THREAT_BAND`'s
  existing "outranks every ordinary report, nearer sorts first within the band" behaviour. Worth
  recording because it would have been easy to add a redundant third band here by analogy with
  the targets-ownship case, when the dispatch's own "especially if close" requirement is already
  satisfied by the existing `range_m` tie-breaker.
- **Mutual exclusivity between `firing_visible` and `firing_targets_ownship` is by construction
  (fold order), not enforced as an invariant on `Percept`/`Contact`/`Event`.** Both default to
  `False` and nothing asserts they cannot both be `True` on the same object -- following the
  project's existing precedent (`targets_ownship` is likewise not asserted mutually exclusive with
  `emitter_kind == BURNING`, say). If a future change ever lets both become `True` simultaneously,
  `belief/speech.py`'s `if event.targets_ownship: ... ; if event.firing_visible: ...` ordering means
  `targets_ownship` silently wins -- flagging this coupling per the tuning-constants convention's
  spirit (cross-field relationships should be stated even when not guarded).
- **`mission_memory/admission.py`'s `_write_fired_on_entries` needed no change.** It already writes
  one `fired_on` memory entry per `CONTACT_FIRING_SEEN` event generically (reading only
  `event.contact_id`/`event.targets_ownship`), so the new `firing_visible` case is covered for
  free -- confirmed by reading, not assumed, since mission memory is otherwise out of this fix's
  stated scope.
