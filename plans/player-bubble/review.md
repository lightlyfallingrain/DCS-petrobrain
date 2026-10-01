### Review Summary

Branch `feature/player-bubble`, tip `6e3a2b7` (verified via `git rev-parse HEAD` before reading
anything; one commit, `main..feature/player-bubble`). Reviewed against `todo/todo.md`'s "Player
bubble: 10 km, settled 2026-09-28" section (the spec), `plans/player-bubble/implementation.md`
(implementer's log), and root/`body-layer` `CLAUDE.md`.

The commit itself (`git show --stat 6e3a2b7`) touches exactly: `association.py`,
`detection_trace.py`, `hybrid_source.py`, `naked_eye_source.py`, `tools/summarize_detection_trace.py`,
`tests/test_association.py`, `tests/test_player_bubble.py` (new), `plans/player-bubble/
implementation.md` (new), `todo/todo.md`. The wider `main..feature/player-bubble` diff also shows
`run-scripts/*` and `world-model/ROADMAP.md` changing — these are **not** in the commit; the branch
was cut from `53f8b0b`, before `edbe6ac` ("Run script updates") and `708ce11` ("Unpark WM-B6")
landed on `main`, so a straight diff against current `main` makes those two unrelated commits look
reverted. That is a merge-mechanics artifact of branch staleness, not something this feature
touched — confirmed by `git show --stat 6e3a2b7` listing only the nine files above. Worth a plain
merge (not a rebase that would silently drop the WM-B6 un-park) when this lands, but it is not a
review finding.

All four scope constraints hold:

1. **Ground/air only, no reach into world features.** `association.py`/`naked_eye_source.py`/
   `hybrid_source.py` have no import of `query.describe_position` or `belief.enrichment` anywhere
   near the new code (`describe_position` is only reached from `perception/geometry.py`'s
   `elevation_at`, for terrain LOS — pre-existing, untouched). `test_enrichment_module_never_
   references_the_player_bubble` pins the reverse direction (enrichment doesn't know the bubble
   exists). Verified by reading, not just the test.
2. **Memory outlives the bubble.** `test_contact_that_drifts_outside_the_bubble_is_not_forgotten`
   uses a real `NakedEyePerceptionSource` and a real `ContactStore` across two polls — not a stub.
   `filter_player_bubble` lives entirely in `perception/`, has no reference to `belief.contacts` at
   all, so there is no code path by which it could reach into the store; the test demonstrates the
   invariant end-to-end rather than merely by layering argument. (The gap tested is 1 simulated
   second against `belief.decay.LOST_THRESHOLD_S = 120.0`, so this test is not exercising decay
   timing — correctly so, since decay/removal correctness is BL-8's own concern, not this feature's.
   It is exactly testing what it claims: the bubble filter itself does not clear anything.)
3. **Independence from `NAKED_EYE_RANGE_CAP_M`.** The two structural `dir()` tests
   (`test_player_bubble_radius_is_not_imported_from_visibility` /
   `test_naked_eye_range_cap_is_not_imported_from_association`) do fail under the aliasing case the
   todo item actually warns about — a `from perception.visibility import NAKED_EYE_RANGE_CAP_M`
   (or the reverse) binds the name into the importing module's `dir()`, which the test catches. A
   subtler collapse (e.g. `NAKED_EYE_RANGE_CAP_M = association.PLAYER_BUBBLE_RADIUS_M` via a whole-
   module import, which would bind a *different* local name) would slip past a `dir()` name check;
   this is a real residual gap but it's also precisely what the todo item itself prescribed ("two
   tests assert neither module imports the other's constant by name") — the implementer built
   exactly the guard that was asked for, not a weaker one. Noted as an optional refinement, not a
   required fix. Both constants' docstrings explain the *why* (computation-scope vs. perception
   sanity bound, divergence at the 9K113 sight) in detail.
4. **Earliest point / "never considered."** Both `poll()`s call `filter_player_bubble()`
   immediately after `filter_ownship()`, before any gaze/salience/clustering/association work —
   confirmed by reading both call sites directly (`naked_eye_source.py:471`, `hybrid_source.py:209`),
   not by trusting the file list. One real upstream per-candidate cost exists in
   `naked_eye_source.poll()`: `_resolve_velocity_by_object_id()` runs a join over *all* raw objects
   (velocity lookup by `unit_name`, a skew check, a same-poll-uniqueness check) before
   `WorldObjectCandidate.from_dict()`/`filter_player_bubble()` run, so units beyond the bubble still
   get a velocity resolved for them this poll. This is pre-existing architecture (not introduced by
   this change) and is a cheap hash-join, not comparable to the gaze/visibility/clustering work the
   spec is actually worried about — same category as the coordinate transform the implementer
   already justified as unavoidable upstream work. Noted as an observation, not a required fix.

**The claimed hybrid no-op, checked against the actual code**: `associate()`'s `RANGE_CAP_M` check
(`if candidate_range_m > RANGE_CAP_M: continue`, `association.py:306`) runs *before*, and
independently of, the forward-hemisphere bearing check — it is not "forward-hemisphere only," it
rejects on range alone regardless of aspect. `implementation.md` and one `hybrid_source.py` comment
call it a "forward-hemisphere" bound, which is loose; the accurate description is "an unconditional,
omnidirectional 5000 m range cap, ANDed with a separate forward-hemisphere bearing check." This
loose wording happens not to break the implementer's conclusion — it strengthens it: since
`RANGE_CAP_M` is omnidirectional and strictly tighter (5000 < 10000), the bubble is a genuine
behavioural no-op for the hybrid channel in *every* direction, not just the forward hemisphere, so
rear-aspect candidates are not treated differently than the implementer assumed. Correct outcome,
imprecise reasoning stated along the way — worth a wording fix in `implementation.md` (it's a log,
not shipped code) but not a required fix since nothing downstream relies on the wrong framing.

**`GateOutcome.PLAYER_BUBBLE` and trace consumers**: grepped every reader of `outcome`/`GateOutcome`
in `src/` and `tools/` (not just the one the implementer already found). `tools/
summarize_detection_trace.py`'s fix (excluding `"player_bubble"` alongside `"cockpit_mask"` from the
"cleared the mask" determination) is correct and necessary. `eyesight_view.py` and
`belief_truth_log.py` only ever test `is GateOutcome.ADMITTED` — unaffected. `tools/
eyesight_replay.py` round-trips the enum value generically (`GateOutcome(row["outcome"])`) —
unaffected by a new member. No other outcome-value consumer exists.

**Boundary and omnidirectionality**: exactly 10 000 m is kept (`<=`), matching `associate()`'s own
`>`-rejection convention, and is explicitly tested
(`test_filter_player_bubble_keeps_a_candidate_exactly_at_the_radius`). No heading/gaze term appears
anywhere in `filter_player_bubble()` — it reads only `ownship.x/z/alt_m`, never
`ownship.heading_true_deg`; confirmed by reading the function body, not just the omnidirectionality
test.

### Required Fixes

None.

### Optional Refinements

- `plans/player-bubble/implementation.md`'s description of `association.RANGE_CAP_M` as
  "forward-hemisphere only" is inaccurate — it's an unconditional range cap ANDed with a separate
  forward-hemisphere bearing check (`association.py:306-312`). The conclusion drawn from it (hybrid
  no-op) still holds, and holds more strongly than stated. Worth a one-line correction since this
  log is what a future implementer will read when the 9K113 sight separates the two constants.
- The two structural independence tests guard against the named-import form of aliasing (exactly
  what the todo item specifies), but not a value-derivation form (`CONST = other_module.OTHER_CONST`
  via a whole-module import). Low value to close now — raise it only if the 9K113 work actually
  needs to touch either constant.
- `naked_eye_source.poll()`'s velocity-resolution join runs over the full raw-object list before the
  bubble filter, so out-of-bubble units still get velocity resolved this poll. Pre-existing
  architecture, not expensive, not worth reordering for this feature.

### Verdict
APPROVED

### Review Confidence
Full read — all five touched source/tool files read in full via `git show`, both call sites of the
new mechanism grepped directly, every `GateOutcome`/`outcome` consumer in `src/` and `tools/`
enumerated and checked (not just the one the implementer flagged), `associate()`'s `RANGE_CAP_M`
logic read line-by-line to verify the "forward-hemisphere" claim, and `belief/decay.py`'s
`LOST_THRESHOLD_S` checked to characterize what the memory-persistence test does and does not
exercise. Checks run from a fresh `.venv` built from `body-layer/pyproject.toml` inside this
worktree (Python 3.14, no version pin issue): `ruff format --check` clean, `ruff check` clean,
`mypy src` clean (53 files), `pytest tests -q` → 1379 passed, 4 xfailed, matching the claimed
1367/4 baseline + 12 new tests, no regressions. `.claude/scripts/gq.sh` returned "no graph yet" as
expected in a worktree.
