---
name: project_terrain_callout_stage5_wiring_gap
description: Recurring pattern (3x as of 2026-10-21) — a leaf module/pure function is thoroughly unit-tested but its wiring into the poll loop/consuming site is not; verify by mutating the wiring, not just grepping or reading it. Started as terrain-feature-probing Rev3 Stages 3a-5.
metadata:
  type: project
---

Reviewed `feature/terrain-callout-stages-345` tip `4da9758` (Stages 3a/3b/4/5 of
`plans/terrain-feature-probing/plan.md` Revision 3 — dominance rule, `query/divides.py`,
`bearing_deg`, the divide-relative callout). Mechanism code was clean: dominance-factor boundary and
`DIVIDE_MERGE_M` merge step both failed their own tests when empirically disabled, no-omniscience
boundary held (`contact.last_position` only), caching containment held (never in
`WorldEnrichmentCache`), mechanism/calibration split was real (`d1d4a88`/`9125fe1`).

**The gap: `terrain_divide_qualifier`'s pure function was unit-tested (5 cases in
`test_enrichment.py`), but the *wiring* carrying its result into the spoken callout was not tested
anywhere.** `tools.py::_add_enrichment_facts` writes `facts["terrain_qualifier"]`;
`speech.py::_contact_report_text` reads it and overrides the semantic-fragment selection. `grep -rn
"terrain_qualifier" body-layer/tests/` returned zero hits. Confirmed empirically by wrapping each
side's logic in `if False and ...` independently — both left the full suite at 1430/4, unchanged.
The five fixture files that gained a `divides_between` stub all stub it to `0` unconditionally
(to stop an unrelated `sqlite3.OperationalError` against a schema-less fake conn), which means none
of them ever exercise the branch they were touched for.

**Pattern for future review**: a well-tested pure function feeding a one-line "wire it into the
output" change is exactly the shape that skips a test, because the function's own tests look like
sufficient coverage on a file-list skim. The check is the same standing one as the sibling-channel
rule ([[reviewer-wiring-grep]] if that memory exists) — grep for the *consuming* site's own key
string across `tests/`, not just the producing function's test file.

**Milder variant, found 2026-10-23 on the `switch-reference-values` fix pass
(`generate_effector_registry.py`'s `_unknown_value_ranges`/run-report/header count): the
end-to-end fixture that would trigger the new field already existed and was already run by an
existing test (`clean` fixture has one `default_button_tumb`-caused unknown value range), but
that test's own assertions simply never looked at the new string** (`"N value range(s) unknown"`
in stdout, `"Value ranges unknown: N"` in the TOML header). Not a missing wiring path — running
the generator against the fixture live showed the feature works correctly — just a printed
field nobody asserted on, in a test that already exercises the exact condition. Grep for the
*literal format string* across `tests/`, not just for whether a fixture triggering the condition
exists: a fixture that triggers it is necessary but not sufficient if the assertion list wasn't
extended alongside the new field.

See [[precise_position_belief_hybrid_gap]] for the sibling case this generalizes (a channel
skipped, not a wiring seam skipped) — same root cause, different shape.

Full detail: `plans/terrain-feature-probing/review-rev3.md`.

**Third occurrence, 2026-10-21, `feature/9k113-effectors` (BL-B66 Stages 1-4):** same shape again.
`sight_effector.py`'s sequencer/`sight_ready`/write functions were thoroughly unit-tested (21
tests against fake `AircraftLayerClient`s), and `CrewConsole.drain_guidance_unit_ready` had correct
logic read by eye — but the ~130 lines wiring both into `logger.py`'s `_run_crew_text_poll_loop`
(takeoff rising-edge detection, the sequencer-advance/readback-refresh/`sight_ready`-refresh/
`drain_guidance_unit_ready` call chain, and the OBSERV/weapons-safety write-through) had zero test
coverage at the wiring point. Confirmed by mutation, not just grep this time: forcing the
rising-edge `if` to `False` left `test_logger.py` at 160/160; removing the `announced` guard from
`drain_guidance_unit_ready` (so "Guidance unit ready." would speak every poll, not once) left the
full body-layer suite at 2383/2383. The implementer's own `implementation.md` had even added a
`cockpit_switch_writes` recorder to the fake client "so a test can assert on the... actual writes"
— and then no test used it. **The tell to watch for**: when an implementer adds test-enabling
plumbing (a recorder, a hook) and the diff's own test files never call it, that is as strong a
signal as a zero-grep-hit on the consuming site's key string. Full detail:
`plans/9k113-effectors/review.md`.
