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

---
---

## Round 2 -- review change requests (Security finding 1, Performance finding 1)

Loop re-entry per `AGENTS.md`: the two reviews' change requests are implementation work, so they
take the Implementer -> Reviewer -> DoD path rather than going straight to DoD. Branch
`feature/sortie-refinements`, applied on tip `6467067` (both review documents are on it).

Two commits, because mechanism and calibration -- and here, two independent mechanisms -- do not
share a commit (body-layer convention).

### Files Changed

- `body-layer/src/belief/crew_console.py` -- `_mark_watched_with_group` now counts the members it
  actually marked and returns that, instead of `len(member_ids)` (the *intended* count). The two
  call sites (`_handle_watch_nearest`, `_handle_follow`) rename their local to `marked` so the
  variable does not read as a group size it no longer is. Docstring rewritten: it promised "the
  real member count" and now states the shrunken-group fallback and why.
- `body-layer/src/belief/speech.py` -- new `group_callout_member_id(store, group)`: which single
  member of a group speaks for it on a `_WATCHED_ONLY_KINDS` event. Shares `_leading_index` with
  `group_membership_state`/`render_group_disclosure`, so "the leader" has one definition.
- `body-layer/src/belief/callouts.py` -- `tick`'s filter extends the existing grouped-contact
  suppression to `_WATCHED_ONLY_KINDS`: a grouped contact that is not the group's keeper has its
  event `_consumed` *before* the filter's `describe_contact`, which is the call being avoided.
  Memoised per group per tick (`group_keeper`). `_WATCHED_ONLY_KINDS`' own docstring records the
  wording tension (below).

### Decisions made during implementation

- **`group_callout_member_id` resolves the leader with zero `describe_contact` calls, and that is
  the whole design.** The obvious implementation calls `group_membership_state`, which is what the
  performance review names -- but that goes through `_group_member_facts`, i.e. one
  `describe_contact` per member, which is precisely the ~51 ms call the finding exists to remove.
  Calling it from the filter would have made the fix cost O(members) describes to save O(2 x
  members), a far weaker result than the review's "2N to 2". `_leading_index` needs only
  `Contact.classification`, and `describe_contact` returns `None` under *precisely* the condition
  `ContactStore.contact` does (an id that no longer resolves -- checked, not assumed), so the
  describe-free path resolves the same member set, in the same order, with the same
  fewer-than-two-members guard.
- **It falls back to the first still-resolving member when no member has a resolvable threat
  envelope**, unlike `group_membership_state`'s `leading_contact_id`, which is legitimately `None`
  there. The two answer different questions: "who leads the disclosure line" may have no answer,
  but "which single event survives" must always have one once there is a group at all -- `None`
  there would silence the entire group. In practice this fallback is the common path in tests,
  because `envelope_for` needs a threat table none of the fixtures load.
- **`_consumed`, not a bare `continue`, for the suppressed peers** -- as the review specifies.
  Lost, not deferred, the same treatment `WATCH_REPORT_MIN_GAP_S` already gives a suppressed
  watched-only event. A bare `continue` would re-offer every peer on every tick, which is the
  cost being removed.

### Tests Added

- `test_watch_nearest_group_readback_counts_only_members_actually_marked`
  (`tests/test_crew_console.py`) -- a `Group` whose membership names an id the store has lost must
  fall back to the single-contact readback, not say "Watching two.", and must register exactly one
  task. Monkeypatches `store.group_for_contact` to return the stale `Group`, which is the exact
  condition `GroupStore.reconcile` can leave behind between a reconcile and a command.
- `test_a_watched_group_that_starts_moving_speaks_one_line_not_one_per_member`
  (`tests/test_callouts.py`) -- three watched grouped members start moving on the same tick (three
  real `CONTACT_MOTION_CHANGED` events, asserted); three scheduler ticks spread across the window
  must yield exactly one spoken line.
- `test_group_callout_member_id_names_exactly_one_live_member` -- the keeper is deterministic, is
  one of the live members, and is stable across calls.
- `test_group_callout_member_id_is_none_when_the_group_has_shrunk` -- the fewer-than-two guard: a
  stale group suppresses nothing, rather than silencing the one real member.
- `test_an_ungrouped_watched_contacts_motion_callout_is_untouched` -- regression guard; the
  suppression keys off group membership only.

### Non-decorative test verification (revert-and-confirm)

Done on a scratch copy of `callouts.py` (never `git checkout --`, which would discard unstaged
work). With the suppression's condition forced false,
`test_a_watched_group_that_starts_moving_speaks_one_line_not_one_per_member` fails with
`assert 3 == 1` and the three identical lines `['ground, moving.', 'ground, moving.', 'ground,
moving.']` -- i.e. the flood itself, reproduced.

**The first version of that test passed with the fix disabled**, and it is worth recording why,
because it is a trap any test of this filter will hit: `tick` speaks at most one line per call, so
a single tick asserts nothing about suppression, and a later tick far enough away to be past
`busy_until_sim` is also past `CALLOUT_MAX_AGE_S`, so the peers expire rather than being
suppressed. The test only has teeth across *several* ticks that are each past the previous line's
`busy_until_sim` and all inside `CALLOUT_MAX_AGE_S` -- which the final version asserts explicitly
rather than leaving to the reader.

### Test-impact check (role step 1b)

Both change requests named exact file:line locations, and both existed. Grepped the suite for
tests touching the modified modules: every existing `_WATCHED_ONLY_KINDS` test
(`test_callouts.py`'s motion/range-crossing/engagement family) uses a **single** contact, which
cannot form a `Group` (`GROUP_REPORTING_MIN_MEMBERS` is 2), so none of them changes behaviour --
consistent with the suite going 1470 -> 1475 with no failures and nothing needing modification.
No existing test was modified in this round.

### Checks

**body-layer/** (`cd body-layer`):
- `ruff format src tests`: pass (115 files unchanged)
- `ruff check src tests`: pass
- `mypy src`: pass (53 source files, no issues)
- `pytest tests -q`: pass -- **1475 passed, 4 xfailed** (branch baseline `1470 passed, 4 xfailed`;
  +1 for the security fix, +4 for the performance fix)

**audio-adapter/**: not touched this round (`git diff --name-only` confirms the diff is three
`body-layer/` files), so its suite was not re-run; its round-1 result of 222 passed / 1 skipped
stands.

### Notable Discoveries

- **The performance review's option A -- "the group is moving" -- contradicts
  `_WATCHED_ONLY_KINDS`' own existing docstring, which neither review cites.** That docstring
  already explains why these kinds are *not* folded into a group's line: they render through
  `_contact_report_text`'s `event_clause`/`lead` affixes ("Getting closer, ", ", moving"), which
  `render_group_report`/`render_group_disclosure` have no concept of, "so folding one into a
  group's own line would silently drop the very fact the event exists to report." So the
  suppression is implemented as specified -- one line, the leading member's, affix intact -- which
  satisfies the decided "one line for the group" in *cardinality*. The line's **wording** still
  names one member. Building a group-level rendering of these kinds would need new templates that
  carry the affix at group grain, which is well beyond the ~6-line mitigation and is a product
  question, not an implementation one. Flagged rather than resolved unilaterally; the docstring now
  records the tension in-code so it is not re-discovered.
- **The security fix's own call sites were already shaped to absorb it.** `if group_size > 1` /
  `if not found` needed no change: a group that has shrunk to one marked member now takes the
  single-contact branch automatically, and `found` already covered the resolved-contact-failed
  case. This is why the fix is three lines -- the branch structure was right, only the number
  flowing into it was wrong.
- **No overlap with `fix/callout-observability-gate`.** That branch adds an observability gate at
  `CalloutScheduler.tick`'s `callout_observable` call sites; this change touches only the
  grouped-contact suppression earlier in the same filter loop and adds no `callout_observable`
  call. The two should merge without conflict beyond adjacent-line context in `tick`.

  **Corrected in round 3 (review round 2's optional refinement 3): "without conflict" was too
  strong and must not be read as licence to resolve blind.** A trial merge
  (`git merge-tree --write-tree`) confirms `body-layer/src/belief/callouts.py` auto-merges cleanly
  and coherently, which is the claim that matters, but **six other files conflict**:
  `body-layer/tests/test_callouts.py`, `body-layer/BACKLOG.md`,
  `docs/acceptance/2026-10-05-sortie-feedback.md` (add/add), and the `implementer`,
  `performance-reviewer` and `security` `MEMORY.md` files. All look append-shaped, but
  `test_callouts.py` is where both branches add test blocks and must be read rather than resolved
  by taking either side.

---

## Round 3 -- review round 2's two required fixes

Spec: `plans/sortie-2026-10-05-refinements/review-round2.md`. Two commits, mechanism and docs kept
apart per the body-layer invariant.

### Files Changed

- `body-layer/src/belief/speech.py` -- new `may_be_callout_keeper(store, contact)` predicate, and
  `group_callout_member_id` now elects the keeper among members that satisfy it, returning `None`
  when none does. The "fewer than two members still resolve" guard still counts *every* resolving
  member (it asks whether there is a cluster to speak for, which eligibility has no bearing on);
  `_leading_index` is applied to the eligible subset, so an ineligible member can neither become
  keeper nor shift which eligible member does.
- `body-layer/src/belief/callouts.py` -- docstrings only. The two falsified claims corrected, the
  new paragraph's back-reference narrowed to the no-folding half it actually endorses, and
  `may_be_callout_keeper` named as what decides the surviving member.
- `body-layer/tests/test_callouts.py` -- one new test, plus a one-line extension to each of two
  existing ones (see Notable Discoveries).

### Why a named predicate rather than an inline condition

Required by the spec and worth restating: `fix/callout-observability-gate` adds an observability
gate to this same filter loop, and once both land an *unobservable* keeper reaches the identical
dead end -- peers consumed, keeper dropped, nothing spoken. The sibling branch already solved this
shape for its group path (*"any one member observable is enough … requiring every member would
silence a visibly-present group for the sake of one straggler behind the doorframe"*). With
eligibility behind one named predicate, extending it is `and observable` in one place; with an
inline condition it is a second special case bolted beside the first. The docstring says it is the
single place keeper eligibility is decided, and why.

### Tests Added

- `test_a_watched_peer_still_speaks_when_the_groups_keeper_is_unwatched` -- the mixed-watched group
  the review identified as uncovered: three cohering members, `min(member_contact_ids)` left
  unwatched (precisely the member the old election kept, asserted rather than assumed), the other
  two watched, all three starting to move. Asserts the keeper is one of the watched peers, and
  that exactly one line is spoken -- the group is still suppressed to a single line, so the
  2N-describes-to-2 saving is intact, but that line exists.

### Counterfactual -- run, not reasoned

Neutered the eligibility filter in place (`if True or may_be_callout_keeper(...)`) against a
scratch backup of `speech.py`, restored by checksum afterwards (`8c8b79a6…`, verified identical):

- The new test fails: `AssertionError: assert 'CONTACT_1' in {'CONTACT_2', 'CONTACT_3'}`.
- A standalone probe over the same fixture reproduces the Reviewer's own observable exactly --
  `keeper = CONTACT_1`, `watched = ['CONTACT_2', 'CONTACT_3']`, **`spoken = []`** reverted, against
  `spoken = ['ground, moving.']` with the fix. So the test bites on the behaviour, not only on the
  intermediate keeper assertion.

### Checks (body-layer; `audio-adapter` not in this diff)

Main checkout's binaries borrowed by absolute path, `cwd` inside the worktree's `body-layer/`.
Imports proven worktree-local first: `belief.callouts.__file__`, `belief.speech.__file__`,
`belief.attention.__file__` all under `.claude/worktrees/agent-a889ea41fda46b00a/body-layer/src/`,
and `query.describe.__file__` under the worktree's own `world-model/src/`.

- `ruff format --check src tests`: pass -- 115 files already formatted
- `ruff check src tests`: pass -- All checks passed
- `mypy src`: pass -- no issues in 53 source files
- `pytest tests -q`: pass -- **1476 passed, 4 xfailed** (round-2 baseline 1475/4, +1 for the new
  test)

### Notable Discoveries

- **Two existing tests broke on the contract change and neither was in the review's impact list.**
  `test_group_callout_member_id_names_exactly_one_live_member` and
  `test_group_callout_member_id_is_none_when_the_group_has_shrunk` are direct unit tests of
  `group_callout_member_id`, and their fixtures leave `Contact.attention` at its `"normal"`
  default -- so with eligibility enforced the function correctly returns `None` and both fail.
  Measured before touching them: `2 failed, 1473 passed, 4 xfailed`. Extended with one
  `set_attention` call each, intent preserved, and each docstring now states why its members are
  watched: in the first so eligibility is not what the test isolates, in the second so the `None`
  under test is the shrunken-group guard rather than ineligibility. Flagged rather than silently
  worked around -- the review named one new test as the gap and these two as nothing, which is the
  "missing entry" direction of a test-impact mismatch.
- **The `None` return now has two independent causes**, group incoherence and no-eligible-member,
  and they answer different questions. Keeping the first counted over all resolving members is
  deliberate: making it count only eligible members would let a watched pair inside a larger mostly
  unwatched group fall below the threshold and lose its suppression, which is a different bug in
  the flood direction.
- **`may_be_callout_keeper` is the designed extension point, not a convenience.** The silence mode
  it closes is reachable from any gate the filter applies after electing a keeper, so the next such
  gate belongs inside this predicate. Stated in its docstring so the next author does not have to
  re-derive it from the review.
