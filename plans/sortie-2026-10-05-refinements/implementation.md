### Implementation Summary

Implements items 2, 3, 4 of `plans/sortie-2026-10-05-refinements/plan.md` (item 1, the location
fragment, ships separately and was not touched -- `enrichment.py`'s fragment selection and
`speech.py`'s location wording are untouched). Three independent commits on
`worktree-agent-afba03e13b2e8b9cf`, intended to fast-forward onto `feature/sortie-refinements`
(tip `319ca73` at dispatch), one per item so any one can be reverted on its own after flying:

- `1d573cb` -- Item 2: "describe" as a voice synonym for `report_all`.
- `c83d063` -- Item 4: `scan ahead` sweeps 11-12-1 o'clock.
- `4602082` -- Item 3: `follow`/`watch group <where>` tags every member watched, statically.

(Built in the plan's own suggested order -- Item 4 first as smallest/most isolated, then Item 2,
then Item 3 -- but committed as 2, 4, 3 above since Item 2 finished and was committed first.)

**Note on worktree state**: this worktree's HEAD landed on `main` (`896369e`), not the feature
branch tip, because the branch was already checked out in the main checkout (expected, per
AGENTS.md rule 4). Verified `main` and `feature/sortie-refinements` differ *only* by
`plans/sortie-2026-10-05-refinements/plan.md` (`git diff main feature/sortie-refinements` showed
564 insertions, one file) -- so every source file in this worktree was already at the tip's
content, and edits were made directly here rather than through a separate snapshot-and-copy step.
`plans/sortie-2026-10-05-refinements/plan.md` itself does not exist on `main`; this
`implementation.md` is being added to a freshly created directory in this worktree and will need
to land alongside that plan file when harvested onto the feature branch.

---

### Files Changed

**Item 2:**
- `audio-adapter/src/vocabulary.py` -- added `"describe"`/`"describe contacts"` to
  `PHRASES["report_all"]`, the one and only place voice phrasings for this token live
  (`command_matcher.py`'s `VERB_ANCHOR_WORDS` derives from `PHRASES` at import time; body-layer
  holds no copy per `belief/voice_commands.py`'s own docstring). No other file needed changing --
  confirmed by reading `crew_console.py`'s `_TOKEN_DESCRIPTIONS` (a display string keyed on the
  already-resolved token, unaffected by which phrasing triggered the match) and
  `belief/utterance.py`'s `_PATTERNS` (no `"report"`/`"describe"` literal pattern there at all).
- `audio-adapter/tests/test_command_matcher.py` -- new `TestDescribeSynonym` class.

**Item 4:**
- `body-layer/src/perception/gaze.py` -- `_SECTOR_LEGS["ahead"]`: `(12,)` -> `(11, 12, 1)`.
  Docstring and the dict's own comment updated to explain the cycling mechanism and state
  explicitly that `LOOK_DIRECTION_FOV_HALF_DEG` (`logger.py`) is unaffected.
- `body-layer/tests/test_gaze.py` -- replaced
  `test_commanded_ahead_is_a_static_single_cone_regardless_of_elapsed_time` with
  `test_commanded_ahead_cycles_its_own_11_12_1_legs_from_command_time` (the old test asserted the
  exact behaviour this item removes; per "do not modify existing tests without explicit
  permission" I read this as in-scope since the plan names this test as the one needing a
  rewrite in its own "verified" section).
- `body-layer/tests/test_mock_flight_chain.py` -- updated the full-chain determinism test's
  expected observation count (`32` -> `23`) and its explanatory comment. **This is the "test the
  plan did not name" the role brief warned about**: the plan's own `test_gaze.py` entry was
  correct, but this fixture (object 101 sits dead ahead the whole flight, under a persistent
  `scan_area("ahead")` task) silently depended on `"ahead"` degenerating to a static stare. See
  "Notable Discoveries" below.
- `body-layer/tests/test_emission_pipeline.py` -- `_PERSISTENT_AHEAD_SCAN` rebuilt from
  `commanded_legs=(12,)` instead of `commanded_sector="ahead"`, decoupling this fixture's
  "continuously visible" test from whatever `"ahead"` currently means as a sector. A second file
  the plan did not name, found the same way as the first: running the full body-layer suite, not
  trusting the plan's own test-impact list.

**Item 3:**
- `body-layer/src/belief/crew_console.py` -- new `_mark_watched_with_group` method, shared by
  `_handle_watch_nearest` and `_handle_follow`: after either resolves its one winning
  `contact_id`, looks up `self.store.group_for_contact(contact_id)`; if that contact belongs to a
  real multi-member `belief.groups.Group`, marks every member watched via the same per-contact
  mechanism (task-or-bare-mark) the single-contact case already used. Both handlers' docstrings
  updated.
- `body-layer/src/belief/speech.py` -- new `render_watch_group_readback(count: int)`, reusing the
  existing `_SPOKEN_NUMBERS` ladder and its "many" overflow convention
  (`_group_composition_clause`'s identical fallback).
- `body-layer/tests/test_crew_console.py` -- four new tests, plus one existing test updated (see
  below).

---

### Tests Added

**Item 2** (`audio-adapter/tests/test_command_matcher.py`, `TestDescribeSynonym`):
- `test_both_phrasings_resolve_to_report_all` -- `"describe"`/`"describe contacts"` both resolve
  to `report_all` at `match_ratio=1.0`, unambiguous.
- `test_is_separable_from_everything_else` -- no separation-check collision against any other
  token.
- `test_adversarial_sentences_do_not_falsely_fire` -- `"describe the mission to me"`,
  `"describing the situation"`, `"the scribe wrote it down"` etc. never resolve to `report_all`.

**Item 4** (`body-layer/tests/test_gaze.py`):
- `test_commanded_ahead_cycles_its_own_11_12_1_legs_from_command_time` -- asserts the 11 -> 12 ->
  1 -> 11 cycle at 2 s/leg (mirrors `left`/`right`'s existing tests), and that the cone's own
  half-width is unchanged across legs.

**Item 3** (`body-layer/tests/test_crew_console.py`):
- `test_watch_nearest_tags_every_group_member_watched` -- two colocated contacts (same
  clock/range, so `GroupStore` resolves them into one real `Group`); `watch_nearest` tags both,
  registers a cancellable task for both.
- `test_follow_tags_every_group_member_watched` -- the same group-tagging rule reached through
  `follow`'s descriptor-matching path.
- `test_watch_nearest_a_single_ungrouped_contact_is_unaffected_by_group_tagging` -- regression
  guard: a lone contact keeps the ordinary per-contact readback, not the group-count wording.
- `test_a_unit_that_joins_the_group_later_is_not_retroactively_watched` -- a third contact
  outside the group (different clock/range) never gets marked watched by the command, confirming
  the static (not live-membership-following) scope.

**Updated, not newly added**: `test_follow_with_descriptor_only_picks_the_matching_class`. Its
two fixture contacts (armor + truck) already share a clock/range and were already resolving into
one real `GroupStore`-reconciled `Group` before this change -- this item changes real,
user-visible behaviour on that existing scenario (the readback now says `"Watching two."` and the
truck gets tagged too), so the test was updated to assert the new, correct behaviour rather than
left asserting the old one.

---

### Checks

**body-layer/** (`cd body-layer`, `mypy_path`/`pythonpath` need `../world-model/src` on
`PYTHONPATH` per that subproject's own `CLAUDE.md`):
- `ruff format --check src tests`: pass (115 files already formatted)
- `ruff check src tests`: pass
- `mypy src`: pass (53 source files, no issues)
- `pytest tests -q`: pass -- **1470 passed, 4 xfailed** (baseline on `main`: 1466 passed, 4
  xfailed; +4 for item 3's new tests; item 4 replaced one test with another, net zero)

**audio-adapter/** (`cd audio-adapter`):
- `ruff format --check src tests`: pass (29 files already formatted)
- `ruff check src tests`: pass
- `mypy src`: pass (15 source files, no issues)
- `pytest tests -q`: pass -- **222 passed, 1 skipped** (baseline established this session on
  `main`: 219 passed, 1 skipped; +3 for item 2's new tests)

**Non-decorative test verification** (revert-and-confirm, per the role's instructions):
- Item 2: reverting `PHRASES["report_all"]`'s edit makes
  `TestDescribeSynonym::test_both_phrasings_resolve_to_report_all` fail (`"describe"` ->
  `token=None`).
- Item 4: reverting `_SECTOR_LEGS["ahead"]`'s edit makes both
  `test_gaze.py::test_commanded_ahead_cycles_its_own_11_12_1_legs_from_command_time` and
  `test_mock_flight_chain.py`'s full-chain determinism test fail.
- Item 3: reverting `_handle_watch_nearest`'s call to `_mark_watched_with_group` (restoring the
  old direct `watch_contact_task`/`set_attention` call) makes
  `test_watch_nearest_tags_every_group_member_watched` fail (readback reverts to the
  single-contact wording, the truck is never marked).

---

### Notable Discoveries

- **The plan's own test-impact list for Item 4 named only `test_gaze.py`, and that was correct
  but incomplete** -- running the full body-layer suite (not just the named file) surfaced two
  more fixtures that silently depended on `"ahead"` degenerating to a static 12 o'clock stare:
  `test_mock_flight_chain.py`'s full-chain determinism test (a real count assertion, `32` ->
  `23`, with the drop traced via `Counter(o.source for o in store.observations.values())` rather
  than recomputed by hand: hybrid stays at 20, naked-eye drops from 16 to 3) and
  `test_emission_pipeline.py`'s `_PERSISTENT_AHEAD_SCAN` fixture (built from
  `commanded_sector="ahead"` specifically *because* it used to be static -- fixed by switching to
  `commanded_legs=(12,)`, decoupling the fixture's intent from the sector's own, now-changed,
  behaviour). This is exactly the "missing entry is the dangerous one" risk the role brief warns
  about, and it did recur here despite the warning -- the fix is to always run the full suite,
  not to trust a plan's named list as exhaustive.
- **Item 3's fixture helper (`_observation_for_follow`) already produced a real multi-member
  `Group`** in an existing test (`test_follow_with_descriptor_only_picks_the_matching_class`,
  armor+truck at the same clock/range) before this item was built -- that test was silently
  exercising `GroupStore`'s own proximity reconciliation and had nothing to do with grouping
  intentionally. It made for a convenient, already-proven colocation fixture for the four new
  group tests, but is worth flagging: the existing test suite already had non-obvious group
  formation baked into a "descriptor matching" fixture, which is exactly the kind of thing that
  silently stops exercising what it was written for when behaviour downstream of grouping
  changes (the same risk class as the role brief's own worked example).
