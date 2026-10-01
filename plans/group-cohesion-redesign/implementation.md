### Implementation Summary

Implemented all three stages of `plans/group-cohesion-redesign/plan.md`: Stage 1 (per-class
cohesion policy, infantry `EAGER`), Stage 2 (installation kind-coherence on the corrected
`installation_component` key), and Stage 3 (the delta taxonomy rebuilt against worked utterances).
Branch `fix/group-undermerging`, tip `fc74e90`.

### Files Changed

- `body-layer/src/perception/object_model.py` — `ObjectTypeProfile.installation_component: bool =
  False`; set `True` on the `"s-125"` and `"kub "` keyword rows only (per the plan's settled §1
  list — every other entry, including the two S-300/`OP_LRSAM` rows, keeps the `False` default).
- `body-layer/src/belief/groups.py` — `CohesionBackstop` enum (`STRICT`/`EAGER`),
  `_OP_CLASS_COHESION_BACKSTOP` (`OP_INFANTRY` -> `EAGER`), `AIR_DEFENSE_OP_CLASSES` (`OP_SRSAM`/
  `OP_MRSAM`/`OP_LRSAM`/`OP_SPAAG`/`OP_ZU23`), `GROUP_REPORTING_INSTALLATION_COHESION_CAP_M`
  (500.0); `_profile_for_contact`/`_pair_backstop_m` factor the per-pair backstop-selection
  priority (installation cap -> `EAGER` -> ordinary unit-widths) out of `_cluster_contacts`; `Group`
  gains `last_spoken_member_contact_ids`/`last_spoken_leading_contact_id`/
  `last_spoken_differentiated`; `GroupStore.mark_spoken`/`reconcile` carry them; `ContactStore.
  mark_group_spoken` passes them through.
- `body-layer/src/belief/speech.py` — `render_group_disclosure`'s trigger rewritten per the §4
  taxonomy (priority order: never-spoken -> leader-changed -> first-differentiation -> membership-
  delta -> silent). New helpers: `_member_contacts_for`, `_leading_index`, `_is_differentiated`,
  `_classification_level`, `_is_air_defence`, `_nearest_clock_position`, `group_membership_state`
  (the three signals a caller needs to persist via `mark_group_spoken` after a successful
  disclosure), `_render_full_group_composition` (the full-roster composition, factored out so it
  has one implementation), and a new public `render_group_full_disclosure` for the pull-based
  "report" path (see Notable Discoveries).
- `body-layer/src/belief/callouts.py` — imports `group_membership_state`; the speak-time
  `mark_group_spoken` call site now computes and passes the three new fields.
- `body-layer/src/belief/crew_console.py` — `_handle_report`'s group branch now calls `render_
  group_full_disclosure` instead of `render_group_disclosure` (see Notable Discoveries).
- `body-layer/src/belief/contacts.py` — `mark_group_spoken` gains the same three keyword-only
  parameters, permissive defaults so existing call sites are unaffected.
- `body-layer/tests/test_groups.py` — `_contact` fixture gains an optional `class_raw` param; new
  tests for Stage 1 (EAGER infantry pair, non-infantry pair at identical geometry, the chaining
  consequence) and Stage 2 (Osa+S-125 non-merge, two S-125 merge/non-merge at the cap boundary, a
  real-ground-truth S-300 test); `test_constants_are_the_stated_assumptions` extended.
- `body-layer/tests/test_speech.py` — new tests for every delta-taxonomy branch plus `render_
  group_full_disclosure`'s pull-path behaviour; new `_direct_contact`/`_store_with_direct_contacts`
  helpers (see Notable Discoveries for why two tests needed them instead of the existing
  `Observation`-based `_cohering_group_store` pattern).
- `body-layer/tests/test_callouts.py` — `test_2c_transcript_fixture_renders_four_lines_not_seven`
  rewritten (AGENTS.md escalation, user-confirmed) — docstring and final assertion updated to the
  real, confirmed-by-running output.
- `body-layer/ROADMAP.md` — milestone entry.
- `plans/group-reporting/plan.md` — Decision 8 (the "no spoken split/merge event" bullet) amended
  with a pointer note, per this plan's own "Settled" instruction.

### Tests Added

- `test_infantry_pair_merges_eagerly_past_the_ordinary_backstop` — EAGER drops the backstop.
- `test_non_infantry_pair_at_the_identical_geometry_still_does_not_merge` — STRICT unaffected.
- `test_infantry_eager_policy_bridges_a_non_infantry_pair_that_would_not_merge_alone` — pins the
  single-link chaining consequence found while verifying Stage 1 (see Notable Discoveries).
- `test_osa_and_s125_launcher_400m_apart_do_not_merge_as_an_installation` — the regression test
  for the bug this plan's §1 found (mixed-pair falls through to the ordinary backstop).
- `test_two_s125_launchers_400m_apart_merge_as_one_installation` — positive installation-cap case.
- `test_two_s125_launchers_past_the_500m_cap_do_not_merge` — the cap is a cap, not unconditional.
- `test_real_s300_site_ground_truth_geometry_forms_a_three_member_cluster` — real emplacement
  geometry from the 2026-10-01 trace's own ground truth, not a hand-built fixture.
- `test_cohesion_backstop_enum_members` — pins the enum's two values.
- `test_render_group_disclosure_leader_change_speaks_a_delta_not_full_restatement`
- `test_render_group_disclosure_first_differentiation_is_full_once`
- `test_render_group_disclosure_new_class_arrival_is_a_delta`
- `test_render_group_disclosure_air_defence_repeat_arrival_is_a_delta`
- `test_render_group_disclosure_non_air_defence_repeat_arrival_is_silent`
- `test_render_group_disclosure_departure_only_is_silent`
- `test_render_group_full_disclosure_ignores_the_delta_taxonomy` — the pull-path fix.
- `test_2c_transcript_fixture_renders_four_lines_not_seven` — rewritten, not new.

### Checks (body-layer/)

- `ruff format src tests --check`: pass
- `ruff check src tests`: pass
- `mypy src` (strict): pass, `Success: no issues found in 53 source files`
- `pytest tests -q`: pass, `1366 passed, 4 xfailed` (branch baseline was `1351 passed, 4 xfailed`)

mypy was not run against `tests/` — per this subproject's own convention (`CLAUDE.md`'s Commands
section only lists `mypy body-layer/src`, and project memory records `mypy --strict` skips
`tests/`), confirmed still the case: a baseline check showed `_cohering_group_store`'s own
pre-existing `-> tuple[ContactStore, object]` return type already produces `object`-typed-group
mypy errors against every existing caller, unrelated to this change.

### Notable Discoveries

- **The "report" pull path broke silently under the new taxonomy, and this is a real design gap
  the plan itself did not name.** `CrewConsole._handle_report`'s own pre-existing comment states
  "a report is pull-based, so it always speaks fresh — no gate here," and it called `render_group_
  disclosure` directly on that assumption, which held only because that function used to always
  render the full composition. Once `render_group_disclosure` gained a taxonomy that can return a
  delta or `None` for an already-spoken group, the pull path would have started returning a terse
  delta or silently dropping a group from a report — directly contradicting the delta taxonomy's
  own worked "report" roll-up example, which always names the full current roster regardless of
  what was last pushed. Fixed by factoring the full-composition logic into `_render_full_group_
  composition` and adding a new taxonomy-free `render_group_full_disclosure` for the pull path.
  Flagging this because it is exactly the class of thing a plan's Affected Modules list can miss —
  a function's contract changing underneath an existing caller that happened to depend on the old
  one's total behaviour, not just its name.

- **The plan's own Stage 2 acceptance wording for the real S-300 replay is stale and cannot be
  satisfied under the settled design.** It asks for "a synthetic fixture pinned to the real
  236-838 m S-300 spacing... confirmed to form one group" and "one offline replay of the 2026-10-01
  trace's S-300 segment... confirmed to form one four-member group at its true spacing." Both
  assume `OP_LRSAM` gets the 500 m installation cap (the only way to bridge the real 830 m `SR`<->
  `SR_19J6` gap). But this plan's own §1 settled list is explicit that only `"s-125"`/`"kub "` get
  `installation_component=True` — S-300/`OP_LRSAM` is not in it, and the SAM-geometry research note
  explicitly treats S-300/mobile-TELAR batteries as a *different*, wider-spacing case the 500 m cap
  is deliberately not sized for. I did not add `installation_component=True` to the S-300 rows —
  that would be deviating from a decision the task told me not to re-raise. I instead verified
  against the real ground-truth geometry (extracted from `/Users/sg/dcs-belief-truth.jsonl`'s
  `true_x`/`true_z`, object ids 16785152/16784640/16784896/16785408) what the settled mechanism
  actually produces: a 3-member cluster (`TR`/`CP`/`SR_19J6`, bridged through `TR` via the ordinary
  unit-widths backstop, since `TR`'s 24 m size and the unknown-size 7 m fallback for `CP`/
  `SR_19J6` give a large enough backstop) with the fourth component (`SR`, "64H6E sr") isolated.
  Pinned this as the real, tested, correct-per-the-settled-design behaviour rather than writing a
  test asserting the stale acceptance wording. This is a plan-vs-settled-decision inconsistency
  worth flagging to the user, not something I resolved unilaterally by changing the flag
  assignment.

- **Single-link chaining plus the infantry `EAGER` release bridges non-infantry members too, wider
  than a literal "the infantry pair merges" reading.** Confirmed while rewriting `test_2c_
  transcript_fixture_renders_four_lines_not_seven`: an infantry-involving edge with no backstop at
  all can connect two non-infantry contacts whose own direct pairwise gap would not itself clear
  the ordinary backstop. In that fixture's own sparse geometry this pulls three infantry, a BTR-70,
  and a truck into one five-member group, not a bounded infantry-only pair or triple. This is not
  a bug — `_cluster_contacts`'s own docstring already documents single-link chaining letting a
  convoy cohere end-to-end even when its full span would not — but it is a real, easy-to-miss
  consequence of the infantry release specifically, now pinned at the smallest scale in `tests/
  test_groups.py::test_infantry_eager_policy_bridges_a_non_infantry_pair_that_would_not_merge_alone`.

- **`object_model.profile_for`'s substring matching and `association_over_time`'s spatial gate
  interact in a way that made two of the delta-taxonomy tests impossible to write with the existing
  `Observation`-based test helper.** A second observation with the *same* `classification_raw`
  string, placed close enough to cohere into the existing group under `belief.groups`'s cohesion
  test, consistently folded into the *existing* `Contact` (association's spatial/class-compatibility
  gate, not a groups.py concern) rather than founding a new one — confirmed empirically, not
  guessed, after several bearing-offset attempts. Worked around by building `Contact` fixtures
  directly (mirroring `test_groups.py`'s own `_contact` pattern and the `# type: ignore[attr-
  defined]` precedent already used in `test_belief_truth_log.py`/`test_crew_console.py` for
  reaching into `ContactStore._contacts`), bypassing `Observation` ingestion entirely for just
  those two tests.

- **`AIR_DEFENSE_OP_CLASSES`'s membership uses `OP_ZU23`, not `OP_ZU`.** The task's own settled-
  decisions list named the air-defence set as `OP_SRSAM, OP_MRSAM, OP_LRSAM, OP_SPAAG, OP_ZU` and
  explicitly invited correcting against the real vocabulary. `perception.object_model`'s actual
  `op_class` string for gun-based AAA (ZU-23) is `"OP_ZU23"` — `"OP_ZU"` does not exist in that
  module's vocabulary. Used `OP_ZU23`.
