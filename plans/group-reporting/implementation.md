### Implementation Summary

Implemented Stages 1-3 of `plans/group-reporting/plan.md` on top of `main` at `d1f5f89`. Stage 4
(CalloutScheduler integration / retiring `group_candidates`) and Stage 5 (common fate) are out of
scope per the dispatch and were not started.

Four commits, one per logical unit (mechanism/calibration separated per project convention, and
per the plan's own "commit per stage" instruction):

1. Stage 2 core: `belief/groups.py` (new), `ContactStore.tick`'s eighth block, `tools.py`/
   `console.py` exposure.
2. Stage 1: `CalloutScheduler`'s disclosure-signature gate.
3. Stage 3: `belief.speech.render_group_disclosure`.
4. A follow-up test-only commit adding direct `test_contacts.py` coverage of the tick wiring
   (the plan's own test-impact list named that file for this change; the first commit covered it
   indirectly via `test_tools.py`/`test_groups.py` but not directly).

### Files Changed

- `body-layer/src/belief/groups.py` (new) — `Group`, `GroupStore`: relative-gap cohesion
  (union-find over fused `Contact.position`, threshold = `GROUP_PROXIMITY_GAP_RATIO` (3.0) times
  the local median nearest-neighbour gap), `GROUP_MIN_MEMBERS` (3), majority-member-overlap
  split/merge reconciliation. Both constants are stated assumptions with no data behind them,
  documented as such in the module docstring and in comments at their declarations.
- `body-layer/src/belief/contacts.py` — `ContactStore` gains a `GroupStore` field, `groups`/
  `group_for_contact`/`mark_group_spoken` delegating accessors, and `tick()` gains an eighth,
  cross-contact block (after the seven per-contact blocks, so a group's future rendering sees
  each member's already-current attention/engagement state) that calls `GroupStore.reconcile`
  once per `tick()` call.
- `body-layer/src/belief/tools.py` — `_group_facts` (new, private): `{group_id,
  member_contact_ids, member_count}`, absent-not-null when a contact belongs to no group. Wired
  into `_contact_facts` as `facts["group"]`.
- `body-layer/src/belief/console.py` — `_SHOW_FACT_KEYS` gains `"group"`, right after
  `"cardinality"`.
- `body-layer/src/belief/callouts.py` — `CalloutScheduler` gains `_last_spoken_signature: dict[str,
  str]` and a check in `_render_group`'s singleton branch: for `CONTACT_DETECTED`/
  `CONTACT_REACQUIRED`, render the candidate via `render_contact_report` first; if it matches the
  last text actually spoken for that contact, return `None` (suppressed, never acknowledged, same
  "lost, not deferred" treatment already given to an aged-out or vanished candidate) instead of
  calling `route_event` (which would otherwise auto-acknowledge).
- `body-layer/src/belief/speech.py` — `render_group_disclosure(store, group, now_sim,
  enrichment)`, plus a private `_group_composition_clause` helper. See "Notable Discoveries" below
  for the naming decision.
- `body-layer/tests/test_groups.py` (new), plus edits to `test_contacts.py`, `test_tools.py`,
  `test_console.py`, `test_callouts.py`, `test_crew_console.py`, `test_speech.py`.
- `body-layer/ROADMAP.md` — milestone entry (`[~]`, in progress — not yet reviewed/DoD'd, not
  audible).

### Tests Added

- `test_groups.py` (11 tests) — cohesion (below-floor, tight cluster with an outlier, sparse
  desert wide gap, 180-degree bearing span), persistence across an unchanged reconciliation,
  split (majority keeps the id, minority drops below the floor and disappears), merge (higher-
  overlap survivor), disclosure-signature carry-over on `mark_spoken`, and the two constants'
  values.
- `test_contacts.py` — `tick()` reconciles a cohering trio into one group; idempotent at the same
  `now_sim`.
- `test_tools.py` — `"group"` fact absent for an ungrouped contact; present with the right
  membership for a cohering trio.
- `test_console.py` — `show <id>` includes a `group:` line for a grouped contact.
- `test_callouts.py` — a reacquisition with an unchanged render is suppressed; a reacquisition
  with a genuinely refined classification still speaks (via the competing
  `CONTACT_CLASSIFICATION_CHANGED` event, and the still-live `CONTACT_REACQUIRED` once occupancy
  clears); a brand-new contact's first detection is never suppressed (empty signature dict).
- `test_speech.py` (9 tests) — `_group_composition_clause`'s singular-article and exact-count
  behaviour directly; `render_group_disclosure`'s four ladder rows (bare "Group.", composition-led,
  threat-led, watched trailing clause), clock/range from the nearest member, and the
  stale-membership `None` guard.

### Checks

(body-layer/ — the only subproject touched)

- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (run as `cd body-layer && .venv/bin/python -m mypy src` — see note below on the venv
  path used): pass, 53 source files, no issues
- `pytest tests -q`: **1340 passed, 4 xfailed** (baseline on `d1f5f89` was 1313 passed/4 xfailed;
  +27 net new tests, 0 regressions)

### Notable Discoveries

- **The plan's own prose names two different functions `render_group_report`.** One already
  existed (`belief.speech.render_group_report(facts_list) -> OutgoingSpeech`, imported into
  `belief.callouts` for the pre-existing speech-time, report-space aggregation the plan explicitly
  does *not* retire in this pass — that is Stage 4). Implemented Stage 3's new function as
  `render_group_disclosure` instead of reusing the name, documented at the top of its own
  docstring. This is a naming collision the plan didn't anticipate, not a design disagreement —
  flagging per the "stop and report" instruction rather than silently picking a name with no note.
- **Stage 3 is not wired into any live speech path.** The plan's Implementation Plan section
  explicitly scopes `CalloutScheduler` integration to Stage 4 ("needs the `Event` shape decision
  below... do this as its own short design pass at Stage 4, not assumed now"), which this dispatch
  was told is out of scope. But the same section also describes Stage 3 as "the first stage that
  changes what the pilot hears." Those two statements are in tension: as delivered, `render_group_
  disclosure` is fully built and tested, but nothing calls it during a live poll loop, so the
  disclosure ladder is not yet audible in a running session. I did not improvise a partial Stage 4
  wiring (e.g. into `CrewConsole._handle_report`) to resolve this tension, since the plan's own
  Risks section flags the `Event`/group-id shape as a real open design question that could affect
  how any wiring should work, and inventing an interim wiring risks being redone once that design
  lands. Flagging this rather than silently reaching into Stage 4's scope, or silently declaring
  the "hear the real thing" ask satisfied when it is not yet.
- **The composition clause always speaks exact per-class member counts**, never a
  `_cardinality_phrase`-style hedge, once classification has differentiated past `presence`/
  `unknown` — this diverges from the plan's own worked-example table (which shows a bare,
  count-free "Tanks and trucks" at 3 km, with numbers only appearing at 1 km). The reasoning: a
  group's per-class count is a literal groupby over already-identified `Contact`s with real
  identity, not an estimate of how many objects one unresolved percept/cluster stands for — the
  cardinality-hedging rule exists to prevent manufacturing precision that isn't there, and none of
  that applies here, so hedging it anyway would be *less* honest, not more. Documented in
  `_group_composition_clause`'s own docstring. This is a deliberate divergence from the
  illustrative table, not from any of the plan's actually-binding decisions (mixed-precision
  register, threat-leads-the-line, and "never pair an exact count with a vague class" are all
  preserved).
- **One existing test's expected behaviour changed, and is the exact case Stage 1 targets**:
  `test_crew_console.py::test_scripted_crew_session_reproduces_the_first_useful_success_criterion`
  previously asserted that a `CONTACT_REACQUIRED` at the same believed position/classification
  re-speaks the identical "BMP-2." line already spoken for that contact's original detection. That
  is now suppressed by Stage 1's disclosure-signature gate, so the assertion was updated to expect
  silence there, with a comment explaining why. No other existing test's expected string changed.
- **`.venv` did not exist in this worktree** (agent worktrees are separate checkouts; venvs are
  gitignored per-checkout). Ran every check via the main checkout's `body-layer/.venv/bin/python -m
  <tool>` with `cwd` inside this worktree's `body-layer/` directory — confirmed this resolves
  `mypy_path`/`pytest`'s `pythonpath` correctly (both are relative to the invoking process's CWD,
  not the venv's own location) before relying on it for every subsequent check.

---

### Stage 4: wiring group disclosure into `CalloutScheduler` and `_handle_report`

Implemented the Stage 4 design (plan.md, "Stage 4 design — wiring the disclosure into
`CalloutScheduler`") on top of `6fb99b4` (base = Stages 1-3 merged + the Stage 4 design). Base was
correct: `body-layer/src/belief/groups.py` existed and the plan carried the design section.

**Two decisions arrived after the base commit, both from the coordinator mid-task, and both
implemented instead of the design's own settled positions:**

1. **A two-contact grouping is now a real, persisted `Group`** — user direction 2026-09-28,
   overturning the design's Decision 2 ("accept the below-floor residual" at a floor of 3). The
   belief-side floor is renamed `GROUP_REPORTING_MIN_MEMBERS` (2), explicitly *not*
   `perception.group_salience.GROUP_MIN_MEMBERS` (3, untouched) — the two now govern genuinely
   different questions (perceptual salience admission vs. reporting-side grouping) and must not be
   made to agree by accident; the old shared name/value was itself a latent collision.
2. **The quantity word tracks classification specificity, one ladder, not two vocabularies.** A
   two-member group's wording is `"a couple of {contacts}"` when undifferentiated (vague
   classification → vague quantity, reusing `_cardinality_phrase`'s own hedge word) and `"Pair of
   {plural}"` when every member shares one real classification (precise classification → precise
   quantity — e.g. *"Pair of T-72."*, unpluralized per `_plural_unit_type_display`'s existing
   type-level quirk). A mixed (differentiated-but-not-homogeneous) pair falls through to the
   existing `_group_composition_clause` unchanged (`"A tank and a truck."` already names each
   member once, no quantity word needed). Implemented in `render_group_disclosure` by extending the
   existing `differentiated` gate rather than adding a parallel branch, per the coordinator's
   explicit instruction.

### Files Changed (Stage 4)

- `body-layer/src/belief/groups.py` — `GROUP_MIN_MEMBERS` (3) renamed `GROUP_REPORTING_MIN_MEMBERS`
  (2); module docstring rewritten to state why it must stay distinct from `perception.
  group_salience.GROUP_MIN_MEMBERS`.
- `body-layer/src/belief/speech.py` — `_group_member_facts` (new, extracted from `render_group_
  disclosure`'s own gathering loop, shared with `belief.callouts.group_priority`'s scoring);
  `_classification_key` (new, factored out of `_group_composition_clause`, reused for the pair/
  couple homogeneity check); `render_group_disclosure` extended with the pair/couple ladder.
- `body-layer/src/belief/callouts.py` — `group_candidates` (function) and its multi-`Event`
  bucketing deleted; `_render_group` renamed `_render_event`, simplified to take one `Event`
  (its multi-member branch was dead code once nothing constructs that shape); `group_priority`
  (new) mirrors `callout_priority`'s tuple shape for `Group` candidates; `tick` rewritten per the
  design's section 4 — filters a grouped contact's own `CONTACT_DETECTED`/`CONTACT_REACQUIRED`
  before scoring, scores `Event`/`Group` candidates into one list, re-renders a chosen `Group`
  fresh at speak time, sweeps and acknowledges member events on a successful group speak. `group_
  facts`/`render_group_report` are kept as the residual report-space path (module docstring
  updated throughout to describe the new shape and retire every stale `group_candidates`
  cross-reference).
- `body-layer/src/belief/crew_console.py` — `_handle_report` resolves each in-scope contact's
  `Group` first and speaks each distinct one via `render_group_disclosure` (no `last_spoken_
  signature` gate — a report always speaks fresh); everything left over still goes through the
  pre-existing `group_facts`/`render_group_report` bucketing.
- `body-layer/tests/test_groups.py` — constant renamed; the below-floor test rewritten (a pair now
  forms a group); the split test rewritten (the below-floor remnant now founds its own fresh
  two-member group instead of vanishing).
- `body-layer/tests/test_speech.py` — three new tests for the pair/couple ladder (undifferentiated,
  homogeneous, mixed).
- `body-layer/tests/test_callouts.py` — `group_candidates`'s own four direct unit tests deleted
  (orphaned by the function's deletion); the 2C-transcript headline test's expected output and
  docstring rewritten against actually-observed behaviour (see Notable Discoveries); the
  reacquired/classification-changed tie-break test's expectation swapped (see Notable
  Discoveries); the vanished-candidate test's fixture clears group membership directly (see
  Notable Discoveries); a new "Slice C" section added covering `group_priority` directly, a fresh
  cohering trio's first-tick single-line speech + full acknowledgement, a grouped contact's
  `CONTACT_CLASSIFICATION_CHANGED` still speaking, progressive-disclosure silence/re-trigger, and
  two groups changed in one tick (one speaks, the other stays live, no expiry).
- `body-layer/tests/test_crew_console.py` — two existing report tests (`test_report_clock_3_finds_
  the_matching_contact`, `test_report_all_groups_and_truncates_multiple_contacts`) clear group
  membership directly for the same reason as the callouts fixture above; a new test pins `_handle_
  report` speaking a real persisted group through `render_group_disclosure`.

### Tests Added

- `test_render_group_disclosure_undifferentiated_pair_says_a_couple_of`,
  `test_render_group_disclosure_homogeneous_pair_says_pair_of`,
  `test_render_group_disclosure_mixed_pair_uses_the_composition_clause` — the pair/couple ladder.
- `test_two_tightly_spaced_contacts_form_a_group`,
  `test_split_majority_child_keeps_the_id_minority_pair_founds_a_new_group` (rewritten) — floor-2
  membership behaviour.
- `test_group_priority_uses_the_highest_attention_rank_and_nearest_range`,
  `test_fresh_cohering_trio_speaks_one_group_line_and_acknowledges_all_members`,
  `test_grouped_contacts_own_classification_changed_still_speaks_on_its_own`,
  `test_progressive_disclosure_silent_until_composition_changes`,
  `test_two_groups_changed_in_the_same_tick_one_speaks_the_other_stays_live`,
  `test_ungrouped_singleton_output_is_byte_identical` — `CalloutScheduler`'s Stage 4 wiring.
- `test_report_speaks_a_persisted_group_through_render_group_disclosure` — `_handle_report`'s own
  Stage 4 wiring (§6).

### Tests removed / behaviour changed (called out per dispatch instruction)

- **Deleted, orphaned by `group_candidates`'s deletion**: `test_group_candidates_is_a_thin_
  wrapper_over_group_facts`, `test_mixed_type_pair_does_not_merge`, `test_very_close_never_
  merges_with_a_kilometre_range`, `test_group_candidates_never_groups_classification_changed_
  events`. Nothing else was lost with them — `group_facts` (the function they exercised
  indirectly) keeps its own direct tests untouched.
- **`test_reacquired_with_changed_render_is_still_spoken`**: which of a reacquisition's own
  `CONTACT_REACQUIRED` and its co-occurring `CONTACT_CLASSIFICATION_CHANGED` speaks first is now
  the *other* order. Root cause: `group_candidates`'s deleted construction (`groups: list[list
  [Event]] = [[event] for event in singles]`, `singles` built from a first pass that always put
  `CONTACT_CLASSIFICATION_CHANGED` ahead of a same-tick `CONTACT_REACQUIRED`) incidentally
  resolved every scoring tie in classification's favour. Nothing in `callout_priority`'s tuple
  ever encoded that preference; it was a construction-order artefact of the retired function, not
  a rule. `tick` now scores events in their natural `unacknowledged_events` emission order
  (`ContactStore.tick`'s own "lifecycle → classification" ordering), so `CONTACT_REACQUIRED` wins
  the tie now. Test updated to assert the natural order, with the mechanism explained in its own
  docstring.
- **`test_vanished_contacts_candidate_is_skipped_and_the_next_is_taken`**,
  **`test_report_clock_3_finds_the_matching_contact`**,
  **`test_report_all_groups_and_truncates_multiple_contacts`**: none of these intended to test
  group formation, but their fixtures' contacts incidentally cohere into a real `Group` under
  Stage 4 (see Notable Discoveries below), which would have hijacked each test's own scenario.
  Each now clears `store._groups._groups` directly after `store.tick`, with an explanatory comment,
  rather than fighting the (correct, intended) cohesion algorithm with contrived geometry.
- **`test_2c_transcript_fixture_renders_four_lines_not_seven`**: still speaks exactly four lines,
  but the content is materially different — see Notable Discoveries. Rewritten against the
  actually-observed output (confirmed by print-instrumenting the test, not guessed), with the
  docstring explaining why.

### Checks (body-layer/ — the only subproject touched)

- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src`: pass, 53 source files, no issues
- `pytest tests -q`: **1347 passed, 4 xfailed** (baseline on `6fb99b4` was 1340 passed/4 xfailed;
  net effect: -4 deleted `group_candidates` tests, +11 new, 0 unexplained regressions — every
  changed assertion is accounted for above)

### Notable Discoveries

- **`belief.groups._cluster_contacts`'s relative-gap cohesion has a degenerate case at low contact
  counts, now reachable for the first time at `GROUP_REPORTING_MIN_MEMBERS`=2.** Confirmed directly
  (not inferred): with only two contacts in the whole store, each is the other's *sole* nearest
  neighbour, so the cohesion threshold (`GROUP_PROXIMITY_GAP_RATIO` × that mutual gap) is always
  some multiple of their own separation — meaning **any** two contacts, however far apart (tested
  at 500 km), cohere as a group whenever they are the only two contacts that exist. This is the
  intended, documented "relative gap, not an absolute radius" rule (`belief.groups`'s own module
  docstring, the "sparse desert" cohesion case already tested for 3+ members) — not a bug I found,
  but a consequence of the floor change that is worth the architect/user knowing about explicitly:
  a sparse scene (very plausible early in a real sortie, and the default shape of almost every
  existing unit-test fixture in this codebase) will now report *any* two nearby-ish contacts as a
  "pair," and — combined with `_handle_report`'s design (§6: the whole group speaks once any
  in-scope member triggers it) — can pull a contact **outside the requested clock/sector into the
  answer** (demonstrated in `test_report_clock_3_finds_the_matching_contact`'s original fixture,
  where a clock-3 request would have also named a clock-12 contact). I did not alter the cohesion
  algorithm or `_handle_report`'s "whole group speaks" design to address this — that is a
  mechanism decision beyond this dispatch's scope, flagged here rather than decided silently.
- **The 2C-transcript headline test's synthetic geometry, once inert against `group_candidates`'s
  report-space bucketing, is directly exposed to the above discovery.** All five detections in
  that fixture sit within a few hundred metres of each other and nothing else is ever tracked in
  the whole scene — exactly the sparse-scene shape above. By the time all five have been detected,
  they cohere into **one** persisted `Group` (three infantry, a BTR-70, and a truck) and speak as
  one composite line, `"Three infantry, a BTR-70 and a truck, 1 o'clock, very close."` — a
  materially different outcome from the plan's original (Stage-4-unaware) report-space-only
  expectation. The test now pins this actually-observed sequence and explains why in its own
  docstring; reworking either the cohesion algorithm or this fixture's geometry to keep visually
  distinct unit types apart in a sparse scene is flagged for follow-up, not decided here.
- **Association ambiguity blocks re-detection-based classification refinement inside a tight
  group.** Attempting to refine one member of a 3-member cohering group via a second `store.ingest`
  (the natural way every other classification-refinement test in this file works) spawns a
  *fourth* contact instead, at any tested spacing up to 800 m: `belief.association_over_time.
  passes_gate` returns `True` against all three existing members for a fresh percept (their
  covariance is wide enough that the ambiguous-match safety rule correctly declines to guess which
  one it means). Not a defect — the ambiguous-merge refusal is doing its job — but it meant two new
  tests needed to mutate `Contact.classification` directly (bypassing association) to isolate the
  event-derivation/speech-wiring behaviour they were actually testing; both say so in their own
  docstrings.
- **`speech.py`'s existing `differentiated`/composition-clause branch was the right extension
  point for the pair/couple wording**, exactly as the coordinator predicted — no parallel gate was
  needed, only a `len(member_facts) == 2` + homogeneity check layered onto the same boolean that
  already chose between "Group"/composition-clause.

---

### Fix: sparse-scene cohesion backstop (two commits)

Fixes the defect Stage 4 discovered and deliberately left undecided (above): at exactly two
tracked contacts, `belief.groups._cluster_contacts`'s relative-gap cohesion is mathematically
tautological — each contact is the other's sole candidate nearest neighbour, so the local median
always equals their own mutual separation, and the ratio threshold is always some multiple of the
very distance being tested against it. User direction (given three options: always-on absolute
backstop, backstop only when the scene is too sparse for a meaningful median, or raise the floor
back to 3): chose the second, with a stated-assumption backstop of 300.0 m (convoy/outpost scale,
off the user's own twelve-units-over-~200m calibration group).

**Mechanism (commit `9ecedaf`, mechanism-first, behaviour-preserving):** added
`GROUP_PROXIMITY_ABSOLUTE_BACKSTOP_M` and `_MIN_CONTACTS_FOR_MEANINGFUL_MEDIAN` (3) to
`belief/groups.py`; `_cluster_contacts` now caps `threshold` at the backstop when
`len(contacts) < 3`. Shipped first at `math.inf` — `min(threshold, math.inf) == threshold` always
— and verified by full-suite parity (1347 passed / 4 xfailed, identical to baseline) before the
real number went in.

**Calibration (commit `b0f9518`):** set the constant to 300.0 m and updated the module/function
docstrings with the reasoning above. `GROUP_PROXIMITY_GAP_RATIO`, `GROUP_REPORTING_MIN_MEMBERS`,
and the relative rule itself are untouched — the backstop only bounds the n=2 case where the
relative rule's input is degenerate, and `test_sparse_desert_group_can_span_a_wide_gap` (n=3, its
own 800 m span exceeding the 300 m backstop and still cohering) is direct proof the fix does not
leak into scenes with 3+ tracked contacts.

**Why the predicate is "total tracked contacts < 3", not "cluster size == 2":** the median is
computed once per `reconcile()` call over the *whole* tracked set, not per candidate cluster. The
tautology is specifically that at exactly two points in that whole set, neither has a third point
to draw a genuinely different nearest-neighbour distance from. At three or more tracked contacts
(even if a candidate pair within them is being tested for cohesion), at least one point's nearest-
neighbour distance comes from a different pair, so the median is not self-referential — this is
exactly the intended figure-ground behaviour, not something the fix should touch.

**Tests added** (`tests/test_groups.py`): `test_two_distant_contacts_do_not_form_a_group` (500 km,
the distance the defect was confirmed at, in an otherwise-empty store — no group) and
`test_two_close_contacts_within_the_backstop_still_form_a_group` (250 m — still groups). Existing
`test_two_tightly_spaced_contacts_form_a_group` (10 m) continues to pass unchanged.

**Workaround audit** (the two `store._groups._groups = {}` sites the dispatch asked about, plus a
third that was never in question):

- `test_crew_console.py::test_report_clock_3_finds_the_matching_contact` — **workaround removed.**
  Its two contacts are ~1.4 km apart (verified directly: `Contact.position` is (1000, 1000) and
  (2000, 0)), past the 300 m backstop, so they no longer cohere and the test is naturally isolated
  to clock-scoping again.
- `test_callouts.py::test_vanished_contacts_candidate_is_skipped_and_the_next_is_taken` —
  **workaround kept, and this is a real finding, not an oversight.** I initially removed it on the
  same reasoning (dwp_x/dwp_z 50 km apart), and the suite caught it: `describe_contact` still spoke
  `"A BMP-2 and a T-72."` instead of the expected `"T-72."` I instrumented the actual fixture
  directly and found `Contact.position` for both contacts is `(1000, 0)` — **identical** — because
  `_observation`'s `dwp_x`/`dwp_z` only drive spatial-gate matching (per that helper's own
  docstring); `Contact.position` is instead derived from `bearing_deg`/`range_m` projected off
  `ownship_at_observation`, which both observations in this fixture share (bearing 0, range
  1000 m, ownship at the origin, `ownship_x`/`ownship_z` left at their defaults). So this pair is
  genuinely co-located and legitimately coheres — the backstop is not in play, and clearing group
  membership is still the right isolation for this test's own vanished-candidate scenario. Comment
  updated to say so, so a future reader doesn't repeat my first (wrong) instinct.
- `test_crew_console.py::test_report_all_groups_and_truncates_multiple_contacts` — **not touched**,
  and correctly so: four contacts spaced 1 km apart (3 km total span), `len(contacts) == 4`, so the
  backstop never applies; they cohere by the legitimate sparse-desert rule, same as before the fix.

### Checks (body-layer/ — the only subproject touched)
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (strict): pass
- `pytest tests -q`: 1349 passed, 4 xfailed (baseline 1347/4 + 2 new tests)
