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

---

### Fix round: `plans/group-cohesion-redesign/review.md`'s two Required Fixes (2026-10-01)

Branch `fix/group-undermerging`, review base tip `3d7d51c`, this fix round's tip is the sha reported
in the handoff below. Both findings were in what Petrovich actually says, not in the taxonomy logic.

**Finding 1 — hard-coded `"a"`.** `_group_composition_clause`'s count==1 branch unconditionally
built `f"a {_unit_type_display(...)}"`, which is wrong for `_OP_CLASS_DISPLAY`'s two vowel-initial
entries (`"armor"`, `"infantry"`): `"a armor"`, `"a infantry"`. Added `_with_indefinite_article` plus
an explicit two-word exception set, `_VOWEL_INITIAL_CLASS_WORDS = {"armor", "infantry"}`, rather than
a first-letter-is-a-vowel rule — chosen deliberately (documented in the set's own comment) because a
phonetic rule is a claim about English in general, and this vocabulary already has at least one word
(`"unit"`, `_identification_lead`'s own fallback, not reachable from this branch today but real
vocabulary elsewhere in the same file) where the vowel letter does not match a consonant sound; an
enumerable set over a known, tested, small vocabulary is honest about what it actually checks.
Checked the whole count==1-reachable vocabulary by hand (all nine `_OP_CLASS_DISPLAY` values plus
the `type`-level raw-string/respelled pass-through) — only those two words are vowel-initial;
`"AAA"` respells to `"triple A"` (consonant) before this branch ever sees it, so no further case
needed fixing.

**Finding 2 — undifferentiated members rendered as their own noun phrase.** `_render_full_group_
composition`'s `elif differentiated:` branch called `_group_composition_clause` over *every* member
fact, including still-`presence`/`unknown` ones. `_unit_type_display(None, "presence")` returns
`"ground"` (an internal fallback word, never meant to be spoken as a noun), which the per-key
groupby then counted and rendered exactly like a real class — `"a ground and a truck"` for a
2-member group with one differentiated and one undifferentiated member. Fixed inside `_group_
composition_clause` itself (not just at this one call site, so `_render_full_group_composition`'s
leading-member `rest` composition — line ~1277, which could carry the identical mix — is covered
too): undifferentiated members (`presence`/`unknown` level, the same levels `_is_differentiated`
already tests) are now counted separately and folded into one trailing phrase via a new `_undiff
erentiated_phrase` helper, matched against the user's own worked examples
(`plans/group-cohesion-redesign/explore-notes-delta-taxonomy.md`): one such member reads as
`"something"`, more than one as a spoken-number count of `"contacts"` (`"two contacts"`, etc.),
mirroring `_plural_unit_type_display`'s existing presence-level fallback for the plural case. Where
the member is the *only* one in the composition this would violate `_group_composition_clause`'s
pre-existing "do not call with only undifferentiated members" precondition — left as a defensive
`assert`, since every real caller (`_render_full_group_composition`'s `elif differentiated:` branch,
and the membership-delta branch's `delta_members`, which already filters presence/unknown out before
calling) guarantees at least one differentiated member reaches this function.

Both fixes together: `"a truck and something"` for the 2-member mixed-differentiation case the
review reproduced (was `"a ground and a truck"`), `"an armor, in the group."` / `"an armor and a
truck."` for the two now-corrected test assertions (were `"A armor..."`).

**Finding 3 (optional, done).** `tests/test_crew_console.py::test_report_speaks_a_persisted_group_
through_render_group_disclosure` named and called `render_group_disclosure` directly while
production routes "report" through `render_group_full_disclosure`, passing only because its group
had never been spoken (where the two functions coincide). Renamed to `..._through_render_group_
full_disclosure`, switched its own assertion to call the real renderer, and added a second test,
`test_report_speaks_an_already_spoken_group_in_full`, which marks the group spoken first (so `render_
group_disclosure` demonstrably goes silent on an unchanged group, proving the taxonomy gate is
actually armed) and confirms `"report"` still names the full roster regardless — the regression case
the original test gave no coverage for.

**The test-quality lesson, applied.** `test_render_group_disclosure_first_differentiation_is_full_
once` was the test that should have caught Finding 2 and did not, because its only assertions were
negative-shape conditions (`"in" not in speech.text or "o'clock group" not in speech.text`, `not
speech.text.startswith("Now leading")`) that ruled out *other* branches' shapes without ever
checking this branch's own content. Rewrote it to assert the actual string
(`"A truck and something."`). Grepped the rest of `test_speech.py` for the same shape
(`not in speech.text` / `speech.text.startswith(...)` as a sole or primary assertion): the other
hits (`"CONTACT_1" not in speech.text"`/`"CONTACT_2" not in speech.text"` at line ~212, checking the
no-omniscience invariant that ids are never spoken; `startswith("BMP-2, ")`/`startswith("armor
")`/`startswith("unit ")`/`startswith("Group, ")` elsewhere) are each a real positive assertion on
content that matters for that test, not a workaround standing in for an uninspected branch — none of
them share the defect this one did, so none needed changing.

#### Checks (body-layer/, this fix round)

- `ruff format --check src tests`: pass (113 files already formatted)
- `ruff check src tests`: pass
- `mypy src` (strict): pass, `Success: no issues found in 53 source files`
- `pytest tests -q`: pass, `1367 passed, 4 xfailed` (one test added net: the stale integration test
  was renamed in place and one new test added alongside it; baseline going in was `1366 passed,
  4 xfailed`)

#### Notable discoveries, this fix round

- The membership-delta branch (`render_group_disclosure`'s `elif delta_members:`) was already safe
  from Finding 2 by construction — it filters `presence`/`unknown`-level facts out of `delta_members`
  *before* calling `_group_composition_clause` (line ~1530), so it never needed the undifferentiated-
  aggregation fix itself. Fixing the shared function rather than only the one broken call site still
  mattered: `_render_full_group_composition`'s leading-member `rest` path (the `"Danger, {type}. Also
  {composition}"` branch) builds its own `rest` from *all* non-leading members with no such filter,
  so it carried the identical latent defect with no test yet exercising the mixed case — now covered
  by construction rather than by a new test aimed at that specific branch, since the fix lives one
  level below both call sites.
