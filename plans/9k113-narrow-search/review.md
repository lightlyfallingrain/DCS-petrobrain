### Review Summary

Reviewed `feature/9k113-narrow-search` at tip `3a88a1cb` (implementation commit `7ab871c0`), against
`plans/9k113-narrow-search/plan.md` as overridden by its "Amendment 2" block, `implementation.md`,
and `docs/acceptance/2026-10-20-sortie-feedback.md` F4/F5.

**Mechanically clean.** `body-layer/`: `ruff format --check`, `ruff check`, `mypy --strict`, and the
full `pytest` suite (2267 passed, 4 xfailed — pre-existing/unrelated) all pass on this tip, including
the `defaults.toml` staleness gate. No debug code, no untracked files, nothing staged incorrectly.

**F5 invariant holds.** Traced every path that can hand out `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`
(`_idle_sight_rest`, `_idle_sight_search`, `_back_to_home`'s `SIGHTING` branch, `_decide_sighting`'s
look-start/continuation, `_apply_guidance`'s cap) and confirmed each always carries a non-`None` aim
inside `within_field_of_regard`. Verified by mutation, not only reading: reverting
`_apply_guidance`'s new `or decision.look_azimuth_deg is None` condition fails
`TestIdleAimInvariant::test_guidance_override_during_glance_away` as expected — the test is real,
not decorative.

**Search cycle matches Amendment 2's approved shape** (wide orientation → narrow-near →
narrow-far → binocular excursion for any out-of-regard remainder), confirmed in both
`_idle_sight_search`/`_next_search_leg` and `TestSearchCycle`'s two cycle tests. The binocular
excursion's "stays at last position" mechanism (omitting `look_azimuth_deg`/`look_elevation_deg`
from the `replace()` at entry) and the fresh-`"wide"`-on-resume priming are both exercised directly,
not just asserted.

**The binocular search centre fix** (`_search_sweep` now passes `center_azimuth_deg=center_deg`)
is real and tested for `left` and `ahead`. Verified by mutation: reverting
`_split_sector_by_regard`'s clamping fix (the latent out-span defect the implementer found and
fixed, `logger.py`) fails `TestSplitSectorByRegard::test_a_span_entirely_outside_regard_has_no_in_span`
as expected.

**The nine flipped narrow→wide tests and the two F5-pinning rewrites are justified**, each tied to
a real, documented cause (`sight_look_optic`'s wide-vs-narrow threshold for the fixture's default
1000 m target; Stage 3's active default search closing the "no aim" pinned bug) — not silent
weakening.

**Tunables**: `SIGHT_SEARCH_NEAR_M`/`MID_M`/`FAR_M` declared correctly with `lo`/`hi` bounds and a
`#:` comment; checked the **rendered** `defaults.toml` directly (not the source comment) — all
three lines are intact, the previously-found backtick-asymmetry defect (flagged in the
implementer's own memory note) does not recur here. The documented cross-key coupling
(`NEAR < MID < FAR`, not enforced by per-key bounds) is disclosed in both the tunable's own comment
and the plan's Risks, consistent with this project's existing `belief.decay` precedent — acceptable
as scoped.

**One required fix outstanding** — a user decision delivered mid-review (see below), which also
surfaced a second, more severe consequence of the same root cause that the original report did not
name. Everything else in this review stands independent of it.

---

### Required Fixes

- **The "worth a look" gate that admits a contact to `_decide_sighting`'s candidate list is bound
  by the naked-eye/binocular pair, not the sight's own reach — so a contact beyond binocular's
  classification range never becomes a sight candidate at all, and narrow is never triggered live.**
  User direction (mid-review): *"Fix it, otherwise the whole point of narrow is missed."* Spec: with
  OBSERV on and the contact inside the sight's regard, "worth a look" must consider what the sight
  (wide, then narrow) could achieve; `sight_look_optic` then picks the least-capable sight setting
  that achieves the gain.

  **Where it lives.** `is_worth_a_look` (`optic_policy.py:1119`) delegates to `can_still_improve`
  (`:1099`), which delegates to `improvement_window_m` (`:874`) — hardcoded to
  `UNAIDED_OPTIC`/`BINOCULAR_OPTIC` via its internal `ranges()` closure. `_decide_sighting`'s own
  candidate filter (`worth_looking = [...]`, `:1811`) calls `is_worth_a_look` with no way to
  override that pair. This is also wider than the implementer's own "narrow is unreachable" framing
  stated it: because binocular's own class/type threshold is *lower* than wide's too (`class_range_mult`
  3.50 vs. wide's 7.00), today's gate already excludes some targets wide could resolve, not only
  ones narrow could — the gap is at the candidate-admission step, not only at the wide-vs-narrow
  choice downstream of it.

  **Recommended fix shape — reuse, don't duplicate the retry/pending bookkeeping:**

  1. Add `sight_can_still_improve(target: LookTarget) -> bool` next to `can_still_improve`, built
     the same way `sight_look_optic` already is (reuse `profile_for`/`apparent_extent_m`/
     `distinctiveness_of`/`tier_ranges`), but **as a single upper-bound check against
     `SIGHT_NARROW_OPTIC`'s own class/type threshold, with no lower bound.**
     **Do not mirror `improvement_window_m`'s lower-bound shape by using `SIGHT_WIDE_OPTIC` as the
     "lower" instrument** — that pattern's lower bound exists because the naked eye reaches the same
     tier "for free" on its own next dwell, making a *binocular* look below it wasted; while
     `SIGHTING`, nothing dwells in parallel to resolve a close contact for free (the sight *is* the
     active instrument), so there is no equivalent exclusion. Using wide's own threshold as a lower
     bound would incorrectly exclude close targets and **breaks
     `test_a_worthwhile_target_is_picked_immediately_no_scan_boundary`** (range 1000 m, inside
     wide's own 3500 m class threshold — a target that must stay "worth a look").
  2. Parameterize `is_worth_a_look` and `look_is_finished` with an injectable predicate, e.g.
     `can_improve: Callable[[LookTarget], bool] = can_still_improve`, defaulting to today's function
     (a true no-op for every existing caller). `look_is_finished` already takes caller-overridable
     keywords for the `SIGHTING` case (`started_sim`/`max_dwell_s`, see its own docstring) — this is
     the same pattern, not a new one.
  3. `_decide_sighting`'s two call sites both pass `can_improve=sight_can_still_improve`: the
     candidate filter (`:1811`) **and** `look_is_finished`'s call at `:1733`. `_decide_without_
     guidance`'s `SCANNING`-at-home call sites (`:1987`'s `look_is_finished`, `:2091`'s `is_worth_a_
     look`) are untouched, so the OBSERV-off path is provably unchanged.

  **Why step 3's second call site is not optional, and is the part most likely to be missed.**
  `look_is_finished` (not `is_worth_a_look`) governs whether an *in-progress* look continues past
  its first poll (`:1733`, checked once `state.look_contact_id is not None`). If only the candidate
  filter is widened and `look_is_finished` keeps calling the plain `can_still_improve`, a newly-
  admitted far contact gets picked on poll N (the "starting a new look" branch, which does not call
  `look_is_finished` at all), and on poll N+1 `look_is_finished` evaluates `can_still_improve`
  against the *eye/binocular* window, finds the target already outside it, and reports the look
  finished — one poll after it started, before the sweep has progressed meaningfully. Worse,
  `look_is_finished`'s "finished" path commits `attempted_at_range_m`/`attempted_at_time_sim` for
  that contact as if the look had actually resolved something, which then suppresses `is_worth_a_
  look` from re-selecting it (`RETRY_RANGE_FRACTION`/`OPTIC_RETRY_INTERVAL_S`) until it closes range
  or a retry interval elapses — silently reintroducing the exact defect this fix is meant to close,
  just one poll later and harder to notice. Fixing only `is_worth_a_look` would look correct in a
  quick test (a target gets picked) and fail in exactly the way the user's complaint describes (no
  sustained narrow use at distance).

  **Required test**: a target beyond `BINOCULAR_OPTIC`'s own class/type threshold but within
  `SIGHT_NARROW_OPTIC`'s, while `SIGHTING`, asserting it is picked (`chosen is not None`) **and**
  that the look survives at least one poll past the one that started it (i.e. `look_is_finished`
  does not end it immediately) — the second assertion is the one that would have caught the gap
  above if it were missed.

  **Stale claims to correct once this lands** — both currently assert the gap as a known, accepted
  limitation, and will read as a false claim once fixed: `TestSightLookOptic`'s class docstring
  (`test_optic_policy.py`, "a live `_decide_sighting` look therefore never reaches `sight_look_
  optic`'s narrow branch today") and `implementation.md`'s "Notable Discoveries" item 1. Update or
  remove both as part of this fix, not left dangling.

---

### Optional Refinements

- **Amendment 2's wide/narrow band assignment, as built** (`sight_wide_search` sweeps
  `[NEAR_M, MID_M]`, the same band as `sight_narrow_near_search`, just at wide's coarser
  resolution) is a reasonable, disclosed reading of a genuinely ambiguous spec — the final approved
  wording ("narrow sweeps both bands, near first, wide only to orient") does not itself say whether
  wide should still fully sweep the near band or merely pass through it once as orientation. The
  implementer flagged this explicitly in `implementation.md`'s Notable Discoveries with a localized
  fix path (one `near_m`/`far_m` pair in `logger.py`) if the reading is wrong. Worth a one-line
  confirmation with the user before/at acceptance testing, since it is a live behavioural choice,
  but not a blocker — the disclosed reasoning is sound and reversible cheaply.
- **`_search_sweep`'s centre fix has no direct test for `right` or `full`** (only `left` and
  `ahead`) — low risk, since `right`/`full` share the exact same code path and the geometry is
  already covered from the other direction by `TestSplitSectorByRegard`/`TestSightOutOfRegardSweep`.
  A `right`-sector test for `_search_sweep` itself would close the symmetry gap cheaply.

---

### Verdict
NEEDS REVISION

### Review Confidence
Full read of `optic_policy.py`'s and `logger.py`'s diffs, `implementation.md`, both acceptance
documents, and the full test diffs for both files. Verified by mutation (not only by reading) the
two most behaviour-critical fixes: `_apply_guidance`'s fourth aim-safety path, and
`_split_sector_by_regard`'s out-of-regard clamp. Did not mutate every test individually (the diff
is large); spot-checked the rewritten range-sensitive tests against `sight_look_optic`'s actual
thresholds rather than re-deriving each one by hand.
