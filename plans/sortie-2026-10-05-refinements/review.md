# Review: sortie-2026-10-05-refinements, items 2/3/4

Branch `feature/sortie-refinements`. Task named expected tip `ecd3d67` (the four commits:
`0caa39e` item 2, `194b585` item 4, `329ff9b` item 3, `ecd3d67` implementation log). Reviewed
against that exact sha via `git archive feature/sortie-refinements | tar -x` into a scratch
snapshot (the branch is checked out in the main checkout, so this worktree's own HEAD landed on
`main` at `896369e`, as expected per AGENTS.md rule 4) — every check below ran with `cwd` inside
that snapshot's `body-layer`/`audio-adapter`, using the main checkout's `<subproject>/.venv/bin/*`.

**Branch has since moved past the reviewed tip.** `git log main..feature/sortie-refinements` shows
one further commit, `0de048a` ("Make capture-then-explore structural..."), sitting directly on
`ecd3d67`. It touches only `.claude/scripts/flight-feedback-*.sh`, `.claude/settings.json`,
`.gitignore` and `CLAUDE.md` — none of items 2/3/4's source or test files — so it does not affect
this review's verdict. Worth flagging anyway: it is exactly the "non-code, cross-cutting update"
root `CLAUDE.md`'s own Workflow section says belongs on `main`, not a feature branch's commits
(hooks/config/CLAUDE.md edits, no milestone code). Not this review's to fix, but the orchestrator
should know the branch's tip is no longer what was dispatched for review.

Item 1 (the location fragment) is confirmed absent from this branch's diff, as the brief said.

---

## Item 4 — `scan ahead` sweeps 11-12-1 (user's named focus)

`body-layer/src/perception/gaze.py`: `_SECTOR_LEGS["ahead"]` changed from `(12,)` to
`(11, 12, 1)`, plus docstring/comment updates. Confirmed by reading `gaze_at` directly: it is a
pure data-table change — `index = min(int(elapsed_s // FOCUS_DWELL_S), len(legs) - 1)` is the same
code path `left`/`right` already exercise, no new branch, no change to `FOCUS_CONE_HALF_WIDTH_DEG`
(15°, unchanged) or to `gaze_at`/`ScanPlan` themselves.

**Geometry vs. cadence, verified independently, not taken on the implementer's word.** Grepped
`LOOK_DIRECTION_FOV_HALF_DEG` in `body-layer/src/logger.py:1009` — it is a bare module constant,
`90`, with no dependency on which o'clock leg is active or on `_SECTOR_LEGS` at all. The claim
"this cycles cadence, not width" holds structurally: nothing downstream of `gaze_at`'s return value
reads `len(legs)`.

**The 16→3 naked-eye observation drop, independently reproduced, not just re-read.** I instrumented
`test_mock_flight_chain.py`'s determinism fixture directly (per-poll `gaze_at` label + per-poll
new-observation count, via `Edit`, run with the real venv) rather than trusting the comment's
arithmetic. Confirmed: the fixture's `scan_area("ahead")` task does land on the 12-o'clock leg at
polls 0, 5, 6, 11, 12, 17, 18 (7 of 20 polls — my own independent recompute, matching the
instrumented run exactly), but only 3 of those 7 actually produce a new naked-eye observation
(polls 0, 6, 12) — the other four are suppressed by mechanisms this item does not touch (the
cockpit occlusion mask approaching cutoff, and poll-to-poll dedup/gating already in place). The
total **23** (hybrid 20 + naked-eye 3) is correct, reproduced from a clean run, not inherited from
the implementer's count. The drop is a real, non-trivial consequence of only 1 in 3 dwell legs
landing on dead-ahead now — correctly named in the comment as a cadence tradeoff, not papered over.

**`_PERSISTENT_AHEAD_SCAN` fixture (`test_emission_pipeline.py`) is a genuine decoupling, not a
weakened test.** It switched from `commanded_sector="ahead"` to `commanded_sector=None,
commanded_legs=(12,)` — this fixture's own stated purpose is a *continuously visible* candidate for
exercising the belief pipeline, which has nothing to do with what `"ahead"` itself currently means.
Using `commanded_legs` directly instead of depending on the sector table staying one-element is the
correct fix, not a workaround.

**Non-decorative, confirmed by reverting myself** (not inheriting the implementer's claim):
reverted `_SECTOR_LEGS["ahead"]` to `(12,)` in the snapshot and reran — both
`test_gaze.py::test_commanded_ahead_cycles_its_own_11_12_1_legs_from_command_time` and
`test_mock_flight_chain.py`'s determinism test fail immediately (`'12_oclock' == '11_oclock'`
mismatch, and the observation-count assertion). Restored, full suite green again.

## Items 2 and 3 — lighter pass, both checked structurally and behaviourally

**Item 2 (`describe`).** Confirmed by reading `belief/voice_commands.py`'s own docstring and
`crew_console.py`'s `_TOKEN_DESCRIPTIONS` and `belief/utterance.py`'s `_PATTERNS`: body-layer
genuinely holds no second phrase table, so the one-file `audio-adapter/src/vocabulary.py` change
is the whole of it — the implementer's correction of the brief's premise is right.
`TestDescribeSynonym` covers both phrasings, separation, and three adversarial near-misses
("describe the mission to me", "describing the situation", "the scribe wrote it down"). Reverted
`PHRASES["report_all"]`'s edit myself: `test_both_phrasings_resolve_to_report_all` fails
(`token=None`) as claimed. Restored, suite green.

**Item 3 (group watch).** `_mark_watched_with_group` keys off `self.store.group_for_contact(...)`
→ `belief.groups.Group` (`groups.py:258`/`contacts.py:705`) — verified this is the real
`GroupStore`-reconciled type, not the `_descriptor_score` "group" classification branch
(`cardinality.lo > 1`), which is a different, pre-existing concept the plan explicitly warned not
to confuse with this one. `render_watch_group_readback` reuses `_SPOKEN_NUMBERS` and its "many"
overflow fallback (same convention `_group_composition_clause` already uses) — confirmed by
reading both definitions in `speech.py`, not a parallel ladder. The updated
`test_follow_with_descriptor_only_picks_the_matching_class` is a correct behaviour update, not a
bent assertion — the old assertion (`"armor" in lines[0].lower()`) is genuinely false under the new
readback (`"Watching two."`), and the test now checks both group members end up watched, which the
old single-contact test could not have expressed. Reverted `_handle_watch_nearest`'s call to
`_mark_watched_with_group` myself (back to the old direct `watch_contact_task`/`set_attention`
call): `test_watch_nearest_tags_every_group_member_watched` fails as claimed (readback stays
single-contact). Restored, suite green.

**Grepped for every other `watch_contact_task`/`set_attention(..., "watch")` call site** in
`body-layer/src` to check nothing else needed the same group-tagging treatment the plan didn't
claim for it. Found one other direct call, `belief/console.py`'s typed debug `watch <id>` command
— it takes an explicit single id from the operator, not a resolver pick, so group-tagging doesn't
apply the same way there and the plan never claimed parallel treatment for it. Not a gap.

---

## Mechanical checks (body-layer, audio-adapter — both from inside the scratch snapshot, real
venvs)

**body-layer**: `ruff format --check src tests` pass (115 files), `ruff check src tests` pass,
`mypy src` pass (53 files, no issues), `pytest tests -q` → **1470 passed, 4 xfailed** (matches
claim; main baseline 1466/4).

**audio-adapter**: `ruff format --check src tests` pass (29 files), `ruff check src tests` pass,
`mypy src` pass (15 files, no issues), `pytest tests -q` → **222 passed, 1 skipped** (matches
claim; main baseline 219/1).

All four actuals match the implementer's reported numbers exactly.

---

### Required Fixes

None.

### Optional Refinements

- `0de048a` (the commit now sitting on top of the reviewed tip) is cross-cutting hook/config/
  CLAUDE.md bookkeeping with no feature code — per root `CLAUDE.md`'s own Workflow section this
  belongs on `main`, not a feature branch. Not a defect in items 2/3/4; flagged for the
  orchestrator to move or rebase off before merge if it matters to them (optional).
- `test_mock_flight_chain.py`'s 16→3 comment is correct but its own stated poll numbers ("lands on
  polls 0, 6, 12, 18") don't match what I actually measured (0, 5, 6, 11, 12, 17, 18 land on the
  12-o'clock leg; only 0, 6, 12 produce a new observation) — the *count* (3) is right and the test
  passes, but the comment's own per-poll narration is off by more than rounding. Worth a follow-up
  comment fix next time this file is touched; does not affect correctness or the test's validity
  (optional).

### Verdict

**APPROVED**

### Review Confidence

Full read — plan.md (including both appended user-decision sections), implementation.md, and all
six changed files' diffs read in full. All three "revert and re-confirm" checks performed
independently (not inherited from the implementer's report) and all three mechanical gates rerun
from a clean snapshot at the exact reviewed sha, with actuals matching claims exactly.
