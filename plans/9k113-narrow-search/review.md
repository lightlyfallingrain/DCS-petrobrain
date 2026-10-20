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

---

## Review — F4 follow-up

Commit reviewed: `5e9178406c65d13b90097fd527851f4f300775ad` (parent `242cf8df`), on
`feature/9k113-narrow-search`. Changes the wide sweep's idle-search far edge in
`body-layer/src/logger.py` from `SIGHT_SEARCH_MID_M` (5.647 km, binoculars' own reach / the
near-band boundary it used to share with `narrow_near`) to a new derived constant,
`_SIGHT_WIDE_SEARCH_FAR_M` (≈8.282 km), per `docs/acceptance/2026-10-20-sortie-feedback.md` F4
("wide sweep band" — user: *"use it up to where it can bring information, be it detection or
classification. At greater distances it cannot, narrow can."*).

### Derivation, checked independently

`_SIGHT_WIDE_SEARCH_FAR_M = min(SIGHT_SEARCH_NEAR_M * SIGHT_WIDE_OPTIC.presence_range_mult,
PLAYER_BUBBLE_RADIUS_M)`. Verified by direct computation against the live modules (not taken on the
commit's word):

- `SIGHT_SEARCH_NEAR_M` (2333.0) matches `tier_ranges(optic=UNAIDED_OPTIC, ...)`'s own presence
  threshold for `profile_for("T-72")` (2333.33, rounded) — confirming the claim that it already *is*
  the reference vehicle's unaided presence reach, not an unrelated number that happens to be nearby.
- Computing wide's presence threshold directly via `tier_ranges(optic=SIGHT_WIDE_OPTIC, ...)` for
  the same profile gives 8283.33 m, against the scaled derivation's 8282.15 m — a ~1.2 m (0.01%)
  difference, entirely explained by `SIGHT_SEARCH_NEAR_M` being a rounded whole number rather than
  the unrounded 2333.33. **This is the same rounding gap `SIGHT_SEARCH_FAR_M` (narrow's own analogous
  constant) already carries** against its own direct computation (13556.67 vs. the declared
  13556.0) — so the chosen base and the scaling pattern are not just plausible, they are the
  identical precedent already in this file, applied consistently rather than invented fresh. Going
  to `tier_ranges` directly would have been marginally more honest but not meaningfully more
  correct, and would have required `logger.py` to import `profile_for`/`distinctiveness_of` plus a
  reference vehicle choice, for a ~1 m difference that rounds away immediately — not a trade worth
  making against the existing convention.
- `class_threshold_m <= presence_threshold_m` is enforced structurally by `tier_ranges`'
  chained `min()`s (`perception/visibility.py` lines 632–649) — confirmed by reading the
  function, not assumed — so "the farther of detection and classification reach" is correctly
  satisfied by the presence figure alone, as the comment and
  `test_presence_reach_is_already_the_farther_of_presence_and_class` both claim.
- The clamp's base (`PLAYER_BUBBLE_RADIUS_M = 10_000.0`, `perception/association.py`) is indeed the
  tighter of the two possible caps; `SIGHT_WIDE_OPTIC.range_cap_m = 20_000.0` is looser and
  irrelevant here. At today's defaults (8282.15 < 10000) the clamp does not bind, matching the
  stated claim.
- No ordering/coupling risk across the tunable range: `far_m = near_m * 3.55` (pre-clamp) is `>
  near_m` for every `near_m` in `SIGHT_SEARCH_NEAR_M`'s declared `[1000, 4000]` bounds, and the
  clamp only ever *reduces* an already-larger value toward 10000, which still exceeds `near_m`'s
  own max (4000). So `_sight_in_regard_sweep`'s `far_m > near_m` precondition cannot be violated by
  any legal retuning of `SIGHT_SEARCH_NEAR_M` alone. (Retuning `SIGHT_SEARCH_MID_M` independently
  could put it above or below this new constant — optional note below.)

### Tuning-mechanism compliance — verified, correctly excluded

`_SIGHT_WIDE_SEARCH_FAR_M` is behaviour-affecting (it changes how far the sight's wide leg
searches) but is correctly **not** a `tuning.real()` declaration. Checked against
`plans/configurable-constants/plan.md`'s inclusion test: its RHS is an expression over
`SIGHT_SEARCH_NEAR_M` (already a tunable) and two fixed values (an optic's own calibration
multiplier, the player-bubble cap) — "**Derived constants are never keys** … Expose the inputs; the
derivation is mechanism." It fails inclusion-test criterion 1 (free parameter: moving it
independently would desynchronise it from the `SIGHT_SEARCH_NEAR_M` scaling it is defined by) by
construction, so a bare module-level constant is the correct, not merely convenient, answer.
Confirmed mechanically: `python tools/generate_defaults.py` reports `config/defaults.toml` up to
date both before and after reading the diff — the new constant does not and should not appear
there, and no `tuning.py`/`defaults.toml` diff exists in this commit (`git diff 242cf8df..5e91784
-- src/tuning.py config/defaults.toml` is empty).

### Wiring and mutation check — reproduced, not just read

Re-ran the commit's own claimed mutation myself: reverted the `sight_wide_search=` call's `far_m`
from `_SIGHT_WIDE_SEARCH_FAR_M` back to `SIGHT_SEARCH_MID_M` and re-ran `TestSightWideSearchFarM`.
Exactly one test went red — `test_run_once_passes_the_wide_legs_own_far_edge`, `assert [5647.0] ==
[8282.15]` — the other five stayed green, matching the commit message's claim precisely. Restored
the file from a saved copy and confirmed an empty `git diff` afterward.

Confirmed by reading the call site (`logger.py` ~658–682) that `sight_narrow_near_search`
(`near_m=SIGHT_SEARCH_NEAR_M, far_m=SIGHT_SEARCH_MID_M`) and `sight_narrow_far_search`
(`near_m=SIGHT_SEARCH_MID_M, far_m=SIGHT_SEARCH_FAR_M`) are byte-for-byte unchanged — only
`sight_wide_search`'s `far_m` argument moved. The search cycle still runs wide → narrow_near →
narrow_far → (Stage 2) binocular out-of-regard excursion, per `_sight_out_of_regard_sweep` and the
surrounding `decide_optic(...)` call being otherwise untouched.

### Comment prune

The docstring-comment above the `sight_wide_search=` call was edited ("a brief wide orientation
pass over the near band" → "...out to wide's own useful reach (`_SIGHT_WIDE_SEARCH_FAR_M`)"). No
durable line (date, user quote, sourced measurement) was removed — this was stale descriptive prose
about current behaviour, correctly updated to match the new behaviour. Not a `#:` block (confirmed:
the generator's `_call_target` only recognizes `tuning.*` calls, and `_SIGHT_WIDE_SEARCH_FAR_M`'s
own `#:` block sits above a `min(...)` expression, not a `tuning.*` call, so it is correctly never
rendered into `defaults.toml`).

### Checks run (this review, on `5e91784` directly)

- `ruff format --check src tests`: pass (155 files already formatted).
- `ruff check src tests`: pass.
- `cd body-layer && .venv/bin/mypy src`: pass, no issues in 68 source files.
- `pytest tests -q`: 2280 passed, 4 xfailed, 0 failed — no flakes this run, none of the task's
  known-flake tests needed a rerun.
- `python tools/generate_defaults.py`: `config/defaults.toml` up to date (no `tuning.py` change in
  this commit).

### Required Fixes

None.

### Optional Refinements

- `_SIGHT_WIDE_SEARCH_FAR_M`'s own comment documents the residual coupling with
  `SIGHT_SEARCH_NEAR_M` only implicitly (via the general note already in `optic_policy.py` about
  `SIGHT_SEARCH_NEAR_M`/`MID_M`/`FAR_M` being independently tunable within their own bounds). It
  does not mention that an independently-retuned `SIGHT_SEARCH_MID_M` could end up above or below
  this new constant, changing how much of `narrow_near`'s band `wide` also covers. Not a correctness
  issue — no invariant is violated, no crash, no assertion — purely a documentation completeness
  point for whoever retunes `SIGHT_SEARCH_MID_M` later. (Optional.)

### Verdict
APPROVED

### Review Confidence
Full read of this commit's diff (`logger.py`, `test_logger.py`, `implementation.md`). Verified the
derivation by direct computation against `perception/optics.py`, `perception/visibility.py`,
`belief/optic_policy.py`, and `perception/association.py` rather than taking the stated figures on
trust. Verified the "derived constants are never keys" exclusion against
`plans/configurable-constants/plan.md`'s own inclusion test. Reproduced the commit's mutation test
myself (one test red for the stated reason, five green, file restored and confirmed via empty
`git diff`). Ran `ruff format --check`, `ruff check`, `mypy --strict`, the full `pytest` suite, and
`generate_defaults.py` on this exact commit tip.

---

## Review — security fix

Reviewed `bb6364b0` (parent `8b656499`, `feature/9k113-narrow-search`, detached). This is the
Security-requested fix for Part 2 Required Fix 1 of `plans/9k113-narrow-search/security-review.md`
("NEEDS FIXES" — `_sight_in_regard_sweep` never enforced the sight's own elevation field of
regard). Re-entering the loop per `AGENTS.md` — this is the Reviewer pass on that fix, before DoD.

### Fix verified correct, by direct calculation and by mutation — not only by reading

- **The claimed defect is real and reproduced exactly.** `search_pattern`'s elevation
  (`atan2(altitude_agl_m, range_m)`) is unbounded below and was never checked against
  `regard_elevation_down_deg`. Ran the unfixed formula myself: at 1000 m AGL the near edge
  (`SIGHT_SEARCH_NEAR_M=2333`) gives `-23.2°`, 8.2° past the `-15°` limit — matches the security
  review's table and the implementer's own figure to four decimal places.
- **The fix is the right choke point.** `_sight_in_regard_sweep` is the one producer every caller
  of the three in-regard legs (`run_once`'s `sight_wide_search=`/`sight_narrow_near_search=`/
  `sight_narrow_far_search=`) reads from, confirmed by grep — no other call site builds these
  sequences. Filtering there, not at the consumer, matches this project's own standing rule
  (`.claude/agent-memory/implementer/feedback_declared_bound_check_at_selection_not_at_consumer.md`)
  and the precedent `look_sweep` already set for the chosen-target path.
- **Mutation reproduced myself, not taken on the implementer's word.** Reverted
  `return [step for step in steps if within_field_of_regard(optic, step[0], step[1])]` to
  `return steps`, reran `TestSightInRegardSweepElevation`: 3 of 6 red
  (`test_wide_leg_at_1000m_agl_stays_within_regard`,
  `test_narrow_near_leg_at_1000m_agl_stays_within_regard`, and the `1000.0` parametrization of
  `test_a_multi_poll_cycle_never_commits_an_out_of_regard_aim`), failing with
  `look_elevation_deg=-23.20155444616394` on `SIGHT_WIDE_OPTIC`'s `-54.5°` azimuth step — the
  review's own `-23.2°` figure, exact. Restored by `git checkout -- src/logger.py`;
  `sha1sum` before/after identical (`e384a0316174cbb7c5e82d476d0734d59b775dd1`).
- **Every path that can hand out a sight optic now stays in regard, enumerated directly (not
  trusted from the plan), at 1000 m and 2000 m AGL, for both a free scan and a commanded `left`
  split:** `_idle_sight_search`'s three legs (fixed here), `_idle_sight_rest`'s hold-last-position
  fallback (already validated or `(0,0)`, unaffected), the `home_phase is SIGHTING` hold-last-aim
  path (same argument), and `_decide_sighting`'s `look_sweep` chosen-target path (pre-existing
  `BL-B64` fix, `regard_optic=SIGHT_WIDE_OPTIC`). All four paths checked by direct call, not read
  alone — every generated `(azimuth, elevation)` satisfied `within_field_of_regard` for its own
  optic at both altitudes and both scan shapes, and the `left` split's azimuths landed correctly
  inside `(-60°, 30°)`'s own sub-span.
- **Leg-fallback composition checked by driving `decide()`, not inferred.** At 2000 m AGL,
  `narrow_near` filters to fully empty (confirmed: `nn == []`) while `wide`/`narrow_far` do not.
  Ran 40 polls through `decide()`: the cycle visits `wide` for 9 polls, correctly skips the empty
  `narrow_near` leg entirely, visits `narrow_far` for 16, returns to `wide` — every committed aim
  stayed within regard throughout, no stall, no repeated leg, no exception.
- **Binoculars genuinely have no regard, confirmed at the data, not the docstring.**
  `BINOCULAR_OPTIC.regard_azimuth_half_deg`/`regard_elevation_up_deg`/`regard_elevation_down_deg`
  are all `None` (checked the live object, not just its declaration) — `within_field_of_regard`'s
  `None`-means-unrestricted branch makes it a true no-op there, so `_sight_out_of_regard_sweep`
  correctly needs no equivalent filter.

### New finding from this re-review: filed as `BL-B86`, not a required fix

Checking "does an emptied leg cause a busy loop, a stuck search cycle, or a sight that never
searches at high altitude" surfaced a real, previously-unmeasured consequence of this (correct)
fix: for a **free scan or a commanded `ahead` scan**, `wide`/`narrow_near` empty out by
**2333 m AGL**, and `narrow_far` — the longest-reaching leg — empties out between **3630 and
4000 m AGL** (its own far edge's depression first passes `-15°` at
`13556 * tan(15°) ≈ 3630 m`). Above that altitude, **all four** search sequences
(`sight_wide_search`/`sight_narrow_near_search`/`sight_narrow_far_search`/
`sight_out_of_regard_search`) are simultaneously empty for those two sectors specifically, because
`_sight_out_of_regard_sweep` returns `[]` by construction whenever there is no commanded sector or
the commanded sector has no out-of-regard remainder (`ahead`'s span sits fully inside the regard,
per `_split_sector_by_regard`'s own worked example) — so there is nothing left for the idle cycle
to step through.

**Verified safe, not just plausible:** `_idle_sight_search`'s `first_nonempty_leg` loop is bounded
(`len(_SEARCH_LEG_ORDER)` iterations, never longer) and falls to `_idle_sight_rest` on exhaustion,
which holds the last (already-validated) aim or `(0.0, 0.0)` — both always in regard. Ran `decide()`
20 polls at 5000 m AGL with all four sequences empty: stable, no exception, every decision within
regard — it degrades to "the sight stops searching and holds a fixed aim," never to a crash, a
busy loop, or an out-of-regard commit.

**Not true of every commanded sector** — `left`/`right`/`full` each produce a genuine out-of-regard
binocular remainder by construction, so they keep searching via binoculars (no regard limit) even
at 5000 m AGL; confirmed by direct measurement, not assumed from the `free`/`ahead` case.

This is the correct, honest downstream consequence of "reject, not clamp," not a bug the fix
introduced carelessly — above this altitude there genuinely is no elevation within the search band
(2333–13556 m) the mount can still reach, for a sector with no binocular fallback. It is not a
required fix for this patch: no invariant is violated, the degradation is graceful, and ~4 km AGL
is an unusual sustained altitude for this airframe's role. Filed as **`BL-B86`**
(`body-layer/ROADMAP/BL-B86.md`, indexed in `body-layer/ROADMAP/body-layer-backlog.md`) rather than
blocking on it, the same disposition the original security review gave `BL-B85`.

One documentation gap worth closing, though not blocking: `implementation.md`'s "what the pilot
will notice" note describes only the near-edge band dropping out (true at 1000 m AGL) and does not
mention that the *entire* idle sweep for `free`/`ahead` goes static above ~3.6–4 km AGL — a reader
relying on that note alone would underestimate the effect's reach. Noted as an Optional
Refinement below rather than a required fix, since `BL-B86` itself now carries the full account.

### Checks run (this fix, on `bb6364b0` directly)

- `ruff format --check src tests`: pass (155 files already formatted).
- `ruff check src tests`: pass.
- `cd body-layer && .venv/bin/mypy src`: pass, no issues in 68 source files.
- `pytest tests -q`: 2286 passed, 4 xfailed, 0 failed — no flakes this run; none of the task's
  named known-flake tests needed a rerun.

### Required Fixes

None.

### Optional Refinements

- Update `implementation.md`'s "what the pilot will notice" note to mention the full-stop case
  above ~3.6–4 km AGL for `free`/`ahead` scans, not only the near-edge-band-drops-out case at
  1000 m AGL — or simply point at `BL-B86`, which now carries the complete account. (Optional.)
- `BL-B86` itself (filed, not blocking) — whether the idle fallback should eventually do something
  better than hold a fixed aim once every leg is empty (e.g. park at the `-15°` down-regard
  boundary, or give `free`/`ahead` a synthesized out-of-regard remainder the way `left`/`right`/
  `full` already have) is a design question for Architect/the user, not this review. (Optional,
  tracked separately.)

### Verdict
APPROVED

### Review Confidence
Full read of this commit's diff (`logger.py`, `test_logger.py`, `implementation.md`). Reproduced
the defect calculation independently against `perception/optics.py`'s live `SIGHT_WIDE_OPTIC`/
`SIGHT_NARROW_OPTIC`/`BINOCULAR_OPTIC` objects and `belief/optic_policy.py`'s `search_pattern`,
rather than taking the stated figures on trust. Reproduced the mutation myself (filter removed,
3/6 tests red for the stated reason, file restored and `sha1sum`-verified byte-identical). Directly
enumerated and exercised every code path that can hand out a sight optic, at 1000 m/2000 m AGL and
for both a free scan and a commanded `left` split, rather than trusting the plan's own path list.
Drove `decide()` through real multi-poll cycles at 2000 m and 5000 m AGL to check leg-fallback
composition and the all-legs-empty case directly, which surfaced `BL-B86` above. Ran
`ruff format --check`, `ruff check`, `mypy --strict`, and the full `pytest` suite on this exact
commit tip.

## Review — BL-B85

Reviewed `451c5c451b64f30be9526acf244073fc6bb90397` (cherry-pick of `79921b1c`, tip of
`feature/9k113-narrow-search`), against `docs/acceptance/2026-10-20-sortie-feedback.md` F4,
`body-layer/ROADMAP/BL-B85.md`, and the appended "BL-B85" section of `implementation.md`.

### What was checked, and how

- **Starvation scenario, reproduced independently** (not just trusting the committed test): three
  close contacts (50/80/120 m) held at `presence` forever, driven through `decide()` over 900
  simulated seconds (the review's own original reproduction length, not the test's 600 s). Measured
  busy 502/900 (55.8%), every leg (`wide`/`narrow_near`/`narrow_far`) visited — no starvation.
  Matches the committed `test_three_contacts_stuck_at_presence_still_let_the_search_cycle_run`
  (600 s/58% busy) in direction and order of magnitude.
- **Both halves verified load-bearing by mutation**, independently, on this exact commit (not
  re-derived from the author's own account): reverted only the `stall_cooldown_s` argument passed
  at `_decide_sighting`'s candidate filter (`SIGHT_STALL_COOLDOWN_S` → `None`) — the 600 s test
  measured exactly **88.00%** busy, matching the claimed pre-fix figure to two decimal places.
  Restored, then reverted only `_start_glance_away`'s commit (back to dropping pending marks) —
  measured **88.00%** busy again, independently. Both reversions confirmed, file restored and
  `diff`/`git status --porcelain` confirmed byte-identical afterward. The "both halves necessary"
  claim is correct, not merely plausible.
- **`SIGHT_STALL_COOLDOWN_S` declaration and bounds**: `tuning.real(..., 132.0, lo=30.0, hi=400.0,
  status="judgement")` — a real behaviour-affecting constant (how long Petrovich keeps re-granting
  one contact), correctly routed through the tuning mechanism rather than a bare literal.
- **Rendered `config/defaults.toml` read directly, not the source comment**: the rendered entry
  (`body-layer/config/defaults.toml:109-111`) is the clean first sentence of the `#:` block, ending
  at `` (`BL-B85`). ``, with no truncation and no corrupted markup across the line wrap. The
  implementer's own account of two earlier, discarded drafts (a blank-`#:`-line paragraph break
  that rendered only the paragraph nearest the assignment) is consistent with the generator's
  documented behaviour and does not affect what shipped.
- **Arithmetic checked against the code's own measurement, not the author's stated figure**: `132.0
  = 2 × 66 s` is traced to `review.md`'s own prior measurement ("33 leg transitions … each full
  cycle ~66 s" — 725 s ÷ 33 transitions ≈ 22 s/leg × 3 legs/cycle = 66 s/cycle), not a fresh,
  unverified claim by this round's author. Grounded, not circular.
- **`GLASSING` deliberately unchanged, confirmed by inspection**: `is_worth_a_look` has exactly two
  call sites — `_decide_sighting`'s candidate filter (the only one passing `stall_cooldown_s`) and
  `_decide_without_guidance`'s (GLASSING's own, no `can_improve`/`stall_cooldown_s` passed, so both
  default). `_start_glance_away` itself is called from exactly one site, `_decide_sighting`'s
  scheduled-break check — GLASSING's own natural-end/interruption commit paths are untouched. Both
  claims verified by `grep`, not assumed.
- **`SIGHT_MAX_DWELL_S` two-clocks-one-constant note**: agree with the implementer's own assessment
  — it is a real, correctly-flagged design smell (two conceptually distinct boundaries resolved by
  check order rather than intent), but this round's fix (commit on the scheduled break, same as the
  natural end) makes the two paths behaviourally equivalent for the one case that mattered here, and
  it is not a `lo`/`hi` cross-key violation in the tuning sense. No action needed from this round;
  correctly filed as a note for future sight/dwell work rather than built around.

### Required Fixes

- **Part 2 changes semantics for every scheduled glance-away, not only stuck contacts — and the
  entry's own "realistic case" reassurance is now stale, not merely unconfirmed.** `BL-B85.md`'s
  "Realistic case, for contrast" paragraph (contacts advancing a tier per completed dwell, all
  reaching `type` by ~t=175 s, 71.5% idle thereafter) was measured **before** this round's fix, when
  the race described in `implementation.md` meant `_start_glance_away` *never* committed anything
  for `SIGHTING` — i.e. that number describes a version of the code with no retry throttle reaching
  the sight at all. After this fix, every look that ends on the scheduled dwell-boundary break now
  commits, and `is_worth_a_look`'s pre-existing `OPTIC_RETRY_INTERVAL_S` gate (not just the new
  `SIGHT_STALL_COOLDOWN_S`) engages for the first time for *any* `SIGHTING` look that reaches that
  boundary — stalled or not. A contact whose level genuinely advances between commits gets the
  shorter interval (`test_progress_since_the_last_attempt_keeps_the_fast_retry` confirms this), but
  "shorter" is still `OPTIC_RETRY_INTERVAL_S` (64 s by default), not zero, where before this fix it
  was zero for every scheduled-break-ended look (the commit never happened, so `is_worth_a_look`'s
  "never attempted" branch returned `True` unconditionally).

  **Measured directly** (single contact, toy one-step search bands matching the committed test's own
  harness, level advanced on an external schedule independent of the optic — `presence` until t=50,
  `class` until t=150, `type` from t=150): under the current code the contact is looked at at
  t=0 and **not again until t=94** (two look-starts total in the window). Reverting only the
  `_start_glance_away` commit fix (otherwise identical code) gives look-starts at t=0, 34, 67, 100,
  133 — every ~33 s (`SIGHT_MAX_DWELL_S` + `SIGHT_GLANCE_AWAY_S`), five in the same window. The
  contact crosses from `presence` to `class` at t=50, during the 44 s gap this fix newly imposes
  before it is looked at again — i.e. the sight is not watching it at the exact moment the review
  brief asked about ("a contact that would have advanced a tier on the next look").

  This is not necessarily wrong — `OPTIC_RETRY_INTERVAL_S`'s own docstring (`plans/
  sortie-2026-09-26-fixes/decisions.md` Decision 2/2a) already accepts this exact tradeoff for
  `GLASSING` ("long enough that re-looks don't dominate … search every completed scan cycle"), and
  this fix's effect is arguably just extending that same, already-shipped design intent to
  `SIGHTING` for the first time, now that the bug blocking it is fixed, rather than inventing new
  throttling. But that is an inference, not a confirmed fact: nothing in this round re-measures the
  "realistic", non-stalled case under the *current* code, and the entry's own BL-B85.md still cites
  the stale pre-fix number as evidence the normal case is unaffected. Given this feature's entire
  stated purpose is "classification at distance" (F4), a material slowdown in ordinary (non-stuck)
  multi-dwell identification is exactly the kind of thing that should be measured and stated, not
  left as an untested assumption.

  **Fix**: before `BL-B85.md` is marked `#status/done`, re-run (or have the Implementer re-run) the
  three-contact "realistic case" scenario — classification advancing a tier per completed dwell,
  not stalled — against the current code, as a committed test (not a one-off narrative number), and
  update `BL-B85.md`'s "Realistic case, for contrast" paragraph with the current figures. If the new
  numbers show a material regression in time-to-`type` versus the ~175 s figure, that is a decision
  for the user: accept the tradeoff (consistent with `GLASSING`'s own precedent), or narrow the
  retry gate so a contact whose level is actively moving is not penalised at all (rather than
  merely penalised less than a stalled one).

### Optional Refinements

- **Cross-key coupling, undocumented and unenforced**: `is_worth_a_look` assumes
  `OPTIC_RETRY_INTERVAL_S < SIGHT_STALL_COOLDOWN_S` (the whole point of the `stall_cooldown_s`
  branch is "longer than the fast path"), but nothing enforces this. `OPTIC_RETRY_INTERVAL_S` is
  not itself a `tuning.real` with bounds — it's `4.0 * SCAN_CYCLE_PERIOD_S`, derived at import from
  `FOCUS_DWELL_S` (`lo=0.5, hi=5.0`) and `SCAN_PLAN`'s length, both independently tunable. At
  `FOCUS_DWELL_S`'s own `hi=5.0` with the default 8-entry `SCAN_PLAN`, `OPTIC_RETRY_INTERVAL_S`
  reaches 160 s — already past `SIGHT_STALL_COOLDOWN_S`'s own `lo=30.0`, so a `SIGHT_STALL_COOLDOWN_S`
  tuned toward its low end while `FOCUS_DWELL_S` is tuned toward its high end silently inverts the
  intended relationship (a stalled contact would then get the *shorter* wait of the two). Does not
  crash, and the shipped defaults have a comfortable 2× margin (64 s vs 132 s) — same risk class as
  the `OBSERVED_WINDOW_S`/`POSITION_HALF_LIFE_S` coupling `body-layer/CLAUDE.md`'s "Tuning" section
  already documents as unprotected under multi-key tuning. An import-time assertion (the same
  pattern `belief/decay.py` uses) would close it cheaply if this is worth doing now; otherwise worth
  a line in that same "known residual coupling" note. (Optional — single-key tuning, the normal
  case, is unaffected.)

### Verdict
CHANGES REQUIRED

Both fixes in this commit are correctly built, independently verified by mutation, and the starvation
problem F4 asked for is genuinely solved — this is not a rejection of the approach. What is missing
is verification that the fix for the stuck case did not quietly regress the common case, for a
feature whose whole point is faster classification at distance. That verification is cheap (one
measurement, ideally captured as a permanent test) and should land before this entry moves past
`#needs-flight`/`#status/in-progress` — it does not need another full implementation round, just the
missing number.

### Review Confidence
Full read of the diff (`optic_policy.py`, `test_optic_policy.py`, `BL-B85.md`,
`implementation.md`'s appended section, `defaults.toml`). Reproduced the 900 s/three-contact
starvation scenario independently (not just re-running the committed test). Reproduced both
mutations myself directly on this commit's source (not re-derived from the author's account),
confirming 88.00% busy for each in isolation, file restored and verified byte-identical
(`diff`/`git status --porcelain`) after each. Independently measured the progressing-contact
re-look cadence under both the current code and a locally-reverted `_start_glance_away`, which is
the basis for the Required Fix above — this is new evidence this review produced, not a restatement
of the commit message. Confirmed `GLASSING`'s two relevant call sites by `grep`, not by trusting the
docstrings. Ran `ruff format --check`, `ruff check`, `mypy --strict`, and the full `pytest` suite
(2323 passed, 4 xfailed, 0 failed, no flakes this run) on this exact commit tip from inside
`body-layer/`.

## Review — F5 boresight + BL-B85 refinement

Reviewed two commits on `feature/9k113-narrow-search`, tip `9cba4943fdca82e69335b1f605b5b9c9b32689ff`:
`49f92738` (F5, boresight-relative regard) and `9cba4943` (the "Review — BL-B85" required fix above,
plus the suggested cross-key assertion). Against `docs/acceptance/2026-10-20-sortie-feedback.md` F5
("boresight-relative limits: explore answers", "sequencing"), `plans/9k113-narrow-search/
implementation.md`'s F5 and BL-B85 sections, this file's own "Review — BL-B85", and
`body-layer/ROADMAP/BL-B85.md`/`BL-B86.md`.

### F5 — frame correctness: verified independently, not read off the docstring

**Derived the sign convention by hand, not trusted from the comment.** `perception.geometry.
body_relative_direction`'s own docstring documents a three-step yaw→pitch→bank removal;
`perception.source.OwnshipState`'s docstring states the sign convention (`pitch_deg` positive =
nose up). Worked the algebra for `heading_relative_to_body_relative` symbolically: substituting its
own yaw re-application into `body_relative_direction`'s yaw-removal step cancels exactly for *any*
heading (not just the tested cases) — `forward0 = forward`, `right0 = right`, `up0 = up` — confirming
the claimed "yaw cancels exactly" property as a general identity, not a coincidence of the chosen test
numbers. Then hand-computed the user's own worked example independently: a 1000 m AGL target at
2333 m range (level-flight depression −23.2°) with 10° nose-down pitch gives −13.2° by the same
rotation matrix — matches `test_geometry.py`'s committed figure exactly, derived before looking at the
test, not fitted to it. Nose-up (−10° → −20°) and the bank-30 case checked the same way.

**Mutated `heading_relative_to_body_relative`'s internal `pitch_deg` to a hardcoded `0.0` myself**
(not re-running the implementer's own mutation, a fresh one on this commit's source) — 5 tests go red
(`test_geometry.py`'s two pitch tests, `test_logger.py`'s three `TestSightInRegardSweepBoresightRelative`
tests), matching the implementation note's claimed count. Restored, `sha1sum`-verified byte-identical
to the pre-mutation file.

**Consumer consistency, checked by grep, not assumed from the file list:**
- `grep -rn "look_target_for("` — one real caller (`logger._look_targets`), passing `ownship.
  pitch_deg`/`ownship.bank_deg` correctly; the rest are test call sites exercising the new keyword
  arguments.
- `_sight_in_regard_sweep`/`_sight_out_of_regard_sweep`/`_search_sweep` (binoculars) all route through
  the one shared `_to_body_relative_steps` helper; `_sight_in_regard_sweep` converts **before**
  filtering through `within_field_of_regard`, so the gate and the committed aim are the same numbers.
  Binoculars (`_search_sweep`) convert too, even though they have no regard to filter against — the
  binocular gaze consumer is therefore also body-relative, closing the "gaze and aim frame for
  binoculars" question the dispatch brief raised.
- `belief.attack_run.py` was never affected by this bug at all — it already called
  `alignment_direction`/`body_relative_direction` directly (`grep` confirms), never the old
  heading-relative hand derivation `look_target_for`/`search_pattern` used. `sight_can_still_improve`
  only reads `target.range_m`/`current_level`, never azimuth/elevation, so it is unaffected by
  construction.
- `grep -rn "true_bearing.*-.*heading\|heading_true_deg -"` across `src/` turns up exactly one
  remaining heading-relative derivation outside this fix's reach: `eyesight_view.py`'s
  `relative_bearing_deg` (the debug cockpit-view renderer, a display concern, not a regard/aim
  decision) and `logger.py`'s own `absolute_center - heading_true_deg` (building a *heading-relative*
  commanded-sector centre that is deliberately fed into `search_pattern` *before* the new conversion —
  this is the documented architecture, not a missed site: raw steps are heading-relative by design,
  and the one shared helper converts them once). Neither is a second, inconsistent frame reaching
  `within_field_of_regard`.

Frame correctness is solid, and more thoroughly checked than the diff alone would show — this is not
a rubber stamp of the implementer's own account.

### BL-B85 required fix: verified correct by mutation, independently reproduced

Re-ran `test_a_progressing_contact_is_relooked_near_the_pre_bl_b85_cadence` after reverting
`_start_glance_away`'s conditional commit back to an unconditional one (my own mutation, on this
commit's source): fails with a measured **94 s** gap, matching the exact pre-fix figure the review's
prior round measured and the one this fix's own commit message cites. Restored, `sha1sum`-verified
byte-identical. The required fix is real and does what it claims for the single-contact case.

`current_level_by_id`/`targets` wiring checked: `_decide_sighting` now threads `targets` (the same
live `LookTarget` list `decide()` is called with, recomputed fresh every poll by `logger._look_targets`
from current belief) into `_start_glance_away`, so "current level" really is the level at the instant
the dwell boundary fires, not a stale snapshot. A contact absent from `targets` (dropped out of
candidacy mid-look) falls back to `look_start_level`, correctly treated as "no evidence of progress,
commit" — same as the stalled case, matching Fix B1's own precedent for a genuine interruption.
`pending_attempted_at_range_m`/`pending_attempted_at_level` are unconditionally cleared to `{}` in the
return `replace(...)` regardless of which branch fires, so a dropped mark is genuinely gone, not
silently retained — checked by reading the full function body, not just the diff hunk.

### Required Fixes

- **The new `OPTIC_RETRY_INTERVAL_S < SIGHT_STALL_COOLDOWN_S` assert is an uncaught, unprotected
  bare `assert` — a single in-bounds tuning override crashes the whole process at import, which the
  project's own tuning policy says must never happen.** Reproduced directly, not inferred: with only
  `belief.optic_policy.SIGHT_STALL_COOLDOWN_S = 40.0` in a `PETROBRAIN_TUNING` file — one key,
  comfortably inside its own declared `lo=30.0, hi=400.0` bounds, no second key touched —
  `import belief.optic_policy` raises `AssertionError` and the process never starts. The commit
  message and the comment above the assert call this "the same pattern `belief/decay.py` uses," but
  that is only half true: `decay.py`'s bare `assert OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S` is safe
  **only** because `tuning.py`'s `_check_scan_decay_coupling` runs first, rejects whichever override
  would violate the invariant, and falls back both keys to their code defaults before the assert ever
  sees a bad combination — `tuning.py`'s own docstring: *"a bare `assert`... [is] a disguised refusal
  to start, exactly the thing Decision 4 REVISED exists to prevent."* `_check_scan_decay_coupling`'s
  `_COUPLED_KEYS` is hardwired to exactly the three `decay.py` keys and is explicitly documented as
  *"Not a general mechanism... nothing generalises this to a second coupling without writing a second
  named check."* No equivalent check exists for `OPTIC_RETRY_INTERVAL_S`/`SIGHT_STALL_COOLDOWN_S`, so
  the new assert reintroduces the exact anti-pattern the `decay.py` precedent was built to eliminate,
  for a new pair of keys, with zero protection. This also isn't a narrow cross-key edge case requiring
  two overrides at once (the shape the prior review's Optional Refinement anticipated) — because
  `OPTIC_RETRY_INTERVAL_S` defaults to 64 s, roughly half of `SIGHT_STALL_COOLDOWN_S`'s own declared
  **single-key** range (30–400) is already unsafe to tune into alone, at every other constant left at
  its code default. Directly violates `body-layer/CLAUDE.md`'s "Tuning" section ("A bad value warns
  and continues on the code default — it never refuses to start") and `tuning.py`'s own Decision 4
  REVISED ("There is no case in this module that raises past accessor/`validate_against_defaults()`
  call time"). **Fix**: either extend `tuning.py` with an analogous named cross-key check (mirroring
  `_check_scan_decay_coupling`) for this pair, wired into `SIGHT_STALL_COOLDOWN_S`'s (and, if needed,
  `FOCUS_DWELL_S`'s) accessor call so a violating override is rejected and falls back to defaults
  before the bare assert runs — or otherwise ensure a bad tuning combination warns and falls back
  rather than crashing the process, per policy. No test in the suite currently exercises this path at
  all (`grep` of `test_tuning*.py`/`test_optic_policy.py` for this key pair finds nothing), so the gap
  shipped with zero coverage.

- **The prior review's required fix explicitly asked that the "realistic case" re-measurement be
  captured "as a committed test (not a one-off narrative number)"; this round shipped only prose
  numbers in `BL-B85.md`/`implementation.md`, with no test asserting them.** The implementer's own
  note in `implementation.md` says this was deliberate ("a standalone measurement, not added as a
  second committed test"), narrowing scope against the review's explicit wording. Attempted an
  independent reproduction (same one-step `wide`/`narrow_near`/`narrow_far` legs, three contacts at
  50/80/120 m, each advancing one classification tier "the poll after their own look ends," 900 s):
  the look-start count per contact matched the claim (2 each), but the overall busy fraction (10.4%
  measured vs. 19.4% claimed) and the time each contact reaches `type` (97/262/427 s measured vs.
  130/163/196 s claimed) did not — plausibly because "the poll after the look ends" is ambiguous
  enough (which exact event counts as "the look ending," and how late a tier-bump may land relative to
  the `_start_glance_away` commit/drop comparison it is meant to influence) that an independent
  attempt and the implementer's own uncommitted script resolved it differently. This is not offered as
  proof the shipped figures are wrong — it's exactly the situation a committed, deterministic test
  exists to prevent: right now neither I nor a future reader can mechanically confirm `BL-B85.md`'s
  "realistic case" numbers describe what the current code actually does. **Fix**: commit the
  realistic-case scenario as an actual test (as the prior review asked), so the figures in `BL-B85.md`
  are reproducible and protected against regression, not a narrative that two independent attempts
  already disagree on.

### Optional Refinements

- The new assert's own comment ("the same residual-coupling shape `belief.decay.py`'s own asserts
  guard") reads as claiming parity with `decay.py`'s protection level, which is the "X, so Y" pattern
  reviewer memory warns about — the shape is the same, the protection is not. Worth a one-line
  correction once the Required Fix above is resolved, so the comment doesn't mislead the next reader
  the way it did this one. (Optional — folds naturally into whichever fix is chosen above.)

### Verdict
CHANGES REQUIRED

`49f92738`'s frame-correctness fix is solid — independently re-derived, mutation-verified on fresh
mutations (not just re-running the implementer's own), and consistently wired through every real
consumer. `9cba4943`'s core fix (the progressing-contact throttle) is also solid, independently
mutation-verified. What is not solid is the new import-time assert: it is reachable by a single,
realistic, in-bounds tuning value and crashes the whole process, which is a direct policy violation,
not a style nit — this needs to be closed before merge. The missing committed test for the
realistic-case numbers is the second, lower-severity gap; both are cheap relative to the risk they
leave open.

### Review Confidence
Full read of both commits' diffs (`geometry.py`, `logger.py`, `optic_policy.py`,
`test_geometry.py`, `test_logger.py`, `test_optic_policy.py`, `BL-B85.md`, `BL-B86.md`,
`implementation.md`'s two appended sections). Verified the frame-correctness algebra by hand
(general cancellation identity, not just the tested case) before reading the tests, then confirmed
the tests agree. Ran fresh mutations on this exact commit tip (not re-running or trusting the
implementer's own two mutation claims) for both the geometry conversion and the BL-B85 commit/drop
logic; both restored and `sha1sum`-verified byte-identical afterward. Reproduced the tuning-crash
finding directly by running `import belief.optic_policy` under a constructed `PETROBRAIN_TUNING`
file, not inferred from reading `tuning.py`. Attempted an independent reproduction of the
"realistic case" numbers and flagged the discrepancy rather than silently accepting the narrative
figures; this is new evidence this review produced, not a restatement of `implementation.md`. Ran
`ruff format --check`, `ruff check`, `mypy --strict` (from `cd body-layer`), and the full `pytest`
suite (2340 passed, 4 xfailed, 1 failed on first run — `test_log_live_los_coverage_summary_logs_
zero_over_evaluated_when_healthy`, a named known flake, passed alone on rerun) on commit
`9cba4943fdca82e69335b1f605b5b9c9b32689ff` from inside `body-layer/`. `tools/generate_defaults.py`
confirmed `config/defaults.toml` already current.
