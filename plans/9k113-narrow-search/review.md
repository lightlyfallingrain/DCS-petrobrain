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

---

### Re-review — required-fix commit `33a5238a` (parent `4c815cb8`)

Checked out detached at `33a5238af718a5c4076fc7c00a13fc3fae3ab189` in an isolated worktree (clean
tree, confirmed before and after). Reviewed `optic_policy.py`'s and `test_optic_policy.py`'s diffs
against this commit's own message, `implementation.md`'s appended "Required fix round" section, and
the original review's required-fix spec above.

**Shape matches the recommendation exactly.** `sight_can_still_improve` is the single upper-bound
check against `SIGHT_NARROW_OPTIC`'s own class/type threshold, no lower bound, built the same way
as `sight_look_optic` (`profile_for`/`apparent_extent_m`/`distinctiveness_of`/`tier_ranges`). `is_
worth_a_look` and `look_is_finished` both gained the injectable `can_improve` keyword, defaulting
to `can_still_improve` — a true no-op confirmed by inspection of the diff (every other caller is
textually unchanged). `_decide_sighting`'s two call sites (the `worth_looking` filter and the
`look_is_finished` continuation check) both pass `can_improve=sight_can_still_improve`; the
`SCANNING`-at-home call sites (`:2045`'s `look_is_finished(state, now_sim, targets)` and `:2150`'s
`is_worth_a_look(target, state, now_sim)`) carry no new keyword at all.

**Mechanical checks, this subproject (`body-layer/`) only, on `33a5238a`:**
- `ruff format --check src tests`: pass.
- `ruff check src tests`: pass.
- `cd body-layer && .venv/bin/mypy src`: pass, no issues in 68 source files.
- `pytest tests -q`: 1 failure on first run —
  `test_connection_reporter_reannounces_after_a_recovery_and_a_second_drop` — on the task's own
  known-flake list; passed alone on rerun (2.46 s). No other failures. `test_tuning_defaults_toml.py`
  (the `defaults.toml` staleness gate): pass. No tunables touched this round, consistent with the
  commit's own claim.

**Verified by mutation myself, both call sites, independently** (restored each time; `git diff`
empty after, confirmed):
- Reverting the `look_is_finished` call at `:1796` (dropping `can_improve=sight_can_still_improve`)
  leaves `test_a_far_contact_is_picked_for_a_sight_look` green but fails `test_the_look_survives_
  past_the_poll_that_started_it` — `state.look_contact_id` goes to `None` on the second poll,
  exactly the "ends one poll after it starts" defect the commit message describes.
- Reverting the `is_worth_a_look` call at `:1872` (dropping the keyword there) fails **both**
  tests — the far contact is never picked at all (`look_contact_id` stays `None` from the first
  poll), confirming the candidate-filter call site is the one doing the actual admission.

Both mutations reproduce exactly the two distinct failure modes the commit message and `plans/
9k113-narrow-search/implementation.md` claim for them — not merely "a test goes red somewhere."

**Far contact, regard, completion — reproduced directly**, not only via the shipped tests: a 5000 m
T-72 presence target is picked (`decision.optic is SIGHT_NARROW_OPTIC`, as `sight_look_optic`
requires beyond wide's 3500 m threshold) and the look survives at least one further poll. Confirmed
with a standalone `decide()` call outside the test file as well as via the shipped `TestFarSight
CandidateIsAdmittedAndSurvives`.

**Close-contact / no-lower-bound question, exercised directly (not only read):**
- A close contact (80 m, presence) under `SIGHTING` is picked for a look with `decision.optic is
  SIGHT_WIDE_OPTIC` — confirmed by direct `decide()` call. Matches the user's "least capable optic
  that suffices" and `sight_look_optic`'s own close-range branch; the no-lower-bound admission does
  not misroute it to narrow.
- **Search-cycle starvation, both directions tested with real `search_pattern`-built sequences for
  all three legs (not empty placeholders) over 900 simulated seconds, three simultaneous close
  contacts (50/80/120 m, T-72, presence) in regard:**
  - *Pessimistic stress case* — contacts held at `presence` forever (classification never
    advances, which does not reflect how the real belief layer behaves but isolates the gate's own
    worst case): the sight is busy on a look for 792/900 polls (88%), idle/search-eligible for only
    27/900 (3%), and `sight_search_leg` never advances past its initial `"wide"` for the whole run —
    **the narrow search cycle is fully starved** in this scenario.
  - *Realistic case* — each contact's belief level is bumped one tier (`presence → class → type`)
    the poll after its look naturally completes, modelling what the real classification pipeline
    does with a completed dwell (not modelled by `optic_policy` itself, which only decides where to
    look): all three contacts reach `type` and permanently exit candidacy by ~t=175 s. From there
    the search cycle runs freely — 644/900 polls (71.5%) idle/search-eligible overall, and `sight_
    search_leg` cycles `wide → narrow_near → narrow_far → wide → …` repeatedly (33 leg transitions
    across the run, each full cycle ~66 s) for the remaining ~725 s.

  **Acceptable, for two reasons, neither of which is new to this fix:** (1) "identification takes
  priority over search" is this module's own stated, pre-existing rule for the `SCANNING`-at-home
  path too (`_decide_without_guidance`'s own docstring, unchanged by this commit) — extending it to
  the sight is applying an existing precedent, not inventing a new one. (2) The pessimistic case
  requires a contact that is looked at repeatedly at close range (well inside even the naked eye's
  own classification reach) and never gains a tier — that is already a pre-existing systemic risk
  for any stuck contact under the *old* gate too (a mid-range contact stuck at `presence` inside
  the binocular window could starve `GLASSING` the same way before this fix shipped); the no-lower-
  bound change widens *which* contacts can trigger it (now close ones too, previously excluded by
  `can_still_improve`'s lower bound), it does not create the failure mode. Worth a one-line note in
  `implementation.md` or a backlog item flagging that a contact which never gains a classification
  tier despite repeated close-range looks will monopolise the sight — genuinely possible if the
  belief layer's own classification logic stalls for some reason — but not a blocker: the realistic
  case (classification does advance, which is what the belief layer is built to do) recovers search
  within minutes and keeps it running the large majority of the time after.

**OBSERV-off path, reproduced directly (not only read):** with `home_phase is SCANNING`, neither a
close contact (80 m) nor a far one (5000 m) is picked for a look (`look_contact_id` stays `None`,
`decision.optic` stays `unaided` for both) — identical to pre-fix behaviour, confirming the two
untouched call sites really are untouched in effect, not only in source text.

**Stale-claim corrections landed as required.** `implementation.md`'s Notable Discovery 1 is marked
superseded with the fix's own shape; `TestSightLookOptic`'s class docstring no longer asserts the
now-false "narrow is unreachable" claim.

---

### Re-review Verdict
APPROVE

### Re-review Confidence
Full read of this commit's diff (`optic_policy.py`, `test_optic_policy.py`, `implementation.md`).
Verified by mutation, both call sites independently, restored and confirmed via empty `git diff`.
Ran the full `body-layer` check suite on this exact tip (one known timing flake, reproduced and
cleared on rerun — unrelated to this change's call paths). Exercised the far-contact pick/survive
path and the OBSERV-off path directly via `decide()`, outside the shipped tests. Constructed and
ran two independent close-contact scenarios (pessimistic and realistic) over 900 simulated seconds
each to answer the search-starvation question empirically rather than by inspection alone; flagged
the pessimistic case's full-starvation result as a disclosed, pre-existing-class risk rather than a
blocker, with a recommended one-line note for `implementation.md` (optional, not required).
