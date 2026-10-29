## Reviewer: BL-B67 Stages 1-2 (run skeleton + single-unit aim)

Branch `feature/bl-b67-atgm-run` @ `5033afc5b1971c4d3f6b7107c8ef39b8c7d56573`, fast-forwarded into
this worktree from `ca69f8ec` (tree was clean, HEAD was a strict ancestor of the tip). Diff under
review: `e523f2b3..5033afc5` on `body-layer` — stage commits `7aee88de`, `3fc1ab59`, plus the
implementer-memory commit `5033afc5` (the merge `178c4348` only brings an unrelated main-side
header-comment fix, confirmed by `--stat`, not re-reviewed).

Inputs read in full: `plans/bl-b67-atgm-run/plan.md`, `explore-notes.md`, `implementation.md`
(all 6 flagged deviations), `security-plan-review.md` (approved, two items explicitly passed to
Reviewer with no verdict). Source diff read in full (965 lines across `atgm_run.py`,
`attack_run.py`, `crew_console.py`, `optic_policy.py`, `percept.py`, `sight_head.py`, `speech.py`,
`body.py`, `naked_eye_source.py`, `source.py`) plus the full `test_body.py` diff (the four
Co-moving-Fields integration tests).

### Checks run

`ruff format --check`, `ruff check`, `mypy --strict` (via `cd body-layer && .venv/bin/mypy src`),
`pytest tests -q` — all pass, matching the implementer's reported numbers (2733 passed, 4 xfailed).

### Mutation verification (not just reading)

- Appended a stray `aim_unit_direction` reference to `crew_console.py` → the `belief/`-wide grep
  fence in `test_attack_run.py::test_belief_never_references_relative_direction_except_sanctioned_readers`
  failed correctly (glob over every `belief/*.py` file, not a hardcoded list). Reverted.
- Reordered `_decide_sighting` so `sight_lock_contact_id` is checked before `sight_steady` (i.e.
  simulated the regression "lock overrides the violent-manoeuvre OBSERV-off") →
  `TestSightLock::test_a_forced_observ_off_still_fires_under_the_lock` failed correctly. Reverted.
- Confirmed `git status --porcelain` clean after both reverts.

These two were the highest-risk invariants named in the dispatch (no-omniscience boundary, gyro
safety vs. tracking lock) and the security review explicitly passed both to Reviewer with no
verdict of its own. Both are real, falsifiable tests, not decorative ones.

### Findings by checklist item

- **Single-unit aim never uses the cluster centroid while locked**: `aim_unit_direction` is
  computed from the cluster member nearest the gaze centre, falls back to the centroid only when
  unset (never silently picks the centroid while the sight-tier gate is satisfied), and a
  single-member cluster trivially reduces to the centroid (tested:
  `test_aim_unit_direction_equals_the_centroid_for_a_single_member_cluster`,
  `test_single_unit_prefers_aim_unit_direction_over_the_centroid`). Confirmed in code, not just
  the test names.
- **Sight lock vs. violent-manoeuvre OBSERV-off**: verified correct by mutation above. The lock is
  reached only after the pre-existing `sight_steady` check in `_decide_sighting`, so
  `_force_observ_off` still wins.
- **Guns/rockets regression (BL-14, missing `missiles` weapon word)**: `attack_run_weapon` is read
  but only `"missiles"` is gated or starts an ATGM run; any other value (including a bare
  `engage`) runs the unchanged BL-14 path. `test_engage_guns_never_gated_on_guidance_unit` and
  `test_engage_accepts_and_ignores_the_weapon_slot` (updated per Decision 15's supersession) cover
  this directly.
- **Guidance-ladder floor deferral (implementer's deviation 1)**: the plan's "Keeping the look
  through launch" section is written as part of Stage 1's design ("Keeping the look through
  launch... the guidance ladder's floor is `SIGHT_WIDE_OPTIC`"), but Stage 1's own numbered task
  list only names `sight_lock_contact_id` in `optic_policy.decide`, not the
  `attack_run.decide(..., floor=...)` change. The implementer's read — defer it, since no Stage
  1/2 test exercises the ladder's floor and `attack_run.py`'s `guidance_request_for(...,
  floor=UNAIDED_OPTIC, ...)` call is untouched — is a reasonable reading of an ambiguous stage
  boundary, correctly flagged rather than silently dropped, and genuinely has no observable effect
  until Stage 3 wires the InFlight guidance path. **Accepted as deferred, not a defect**, but
  Stage 3 must make an explicit decision here (plan already says so); this is not optional to
  forget.
- **No new tunables, so no tuning.py / `defaults.toml` gap** — confirmed: no behaviour-affecting
  literal was added this stage (`SHTURM_SPEED_MPS` etc. are Stage 3's). `test_tuning_defaults_toml.py`
  passing unchanged corroborates this rather than merely asserting it.
- **Co-moving Fields table**: the four rows Stage 1 claims (fresh construction on `engage
  missiles`; both cleared on `engage` without `missiles`; both cleared on disengage; both cleared
  when `drain_attack_run` returns `None` for drop-target/lost-contact) are each driven through the
  *real* threaded `_run_crew_text_poll_loop`, not a unit-level stand-in — this is exactly the
  "verify by mutation per entry, not per set" standard this project asks for, and it is met. The
  table's "mission (re)start" row and the general invariant row (`atgm_run_state is not None ⇒
  attack_run_state is not None`, asserted generically rather than per-scenario) have no dedicated
  test, but both are structurally guaranteed: `reset_for_new_mission` re-invokes `__init__`
  wholesale (so an un-listed field reverts to its dataclass default with no extra code needed —
  the same mechanism that protects every other field on that class), and every engage-apply branch
  sets or clears the pair together by construction. Low risk; noted as optional, not required.

### Required fixes

1. **`body-layer/CLAUDE.md`'s invariant text, "The ownship-relative channel has exactly two
   consumers, and neither is a position," is now incomplete, not just unchanged.** It still
   describes only `Percept.relative_direction`; `aim_unit_direction` is a second field on the
   *same* structural no-omniscience boundary, fenced to the same two files
   (`percept.py`/`attack_run.py`), and the `test_attack_run.py` fence docstring itself says so in
   almost these words ("the same ownship-relative boundary's second field, not a second
   exception"). This is exactly the invariant class the file's own header warns about ("break
   these and the failure is silent") and exactly the kind of staleness this project has been
   burned by repeatedly (root `CLAUDE.md`'s "a list in this file has now gone stale four times").
   A reader who checks only CLAUDE.md before adding a third reader of `aim_unit_direction` would
   have no reason to know it is under the same fence as `relative_direction`. Fix: extend the
   bullet (or add one sentence) naming `aim_unit_direction` as the sibling field under the same
   two-file fence, citing `[[BL-B67]]`.
2. **`body-layer/docs/STRUCTURE.md` has the matching gap, twice over.** The `src/perception/
   source.py` entry still says only `RelativeDirection`/`relative_direction` are the fenced
   ownship-relative datum (no mention of `aim_unit_direction`), the `src/belief/attack_run.py`
   entry still says `attack_run.py` and `percept.py` are "the only two files under `belief/`
   allowed to mention `relative_direction`/`RelativeDirection`" with no update, and there is **no
   entry at all for the new `src/belief/atgm_run.py` module** — STRUCTURE.md's own header says "the
   per-module detail for `body-layer/`... read the entry for any module before you modify it," which
   presumes every module has one. Fix: a short entry for `atgm_run.py` (Stage 1 scope: `contact_id`
   only, Stage 3 owns the rest — the new file's own docstring already has this text verbatim and
   can be summarized), and a one-line addition to the `source.py`/`attack_run.py` entries naming
   `aim_unit_direction`.

Neither fix touches `src/`; both are small, mechanical doc edits with no code or test risk, and
both can be made directly rather than looping back through Implementer.

### Optional refinements

- A single generic test asserting `atgm_run_state is not None ⇒ attack_run_state is not None`
  across the four Co-moving-Fields scenarios (parametrized over the existing fixtures) would catch
  a future fifth transition path the per-scenario tests don't happen to cover. Not required: the
  invariant currently holds by construction in every branch that touches either field, and Stage 3
  adds several more transition rows anyway, which is a more natural point to add a combined
  check.
- `plans/attack-run/plan.md` Decision 15 and `body-layer/ROADMAP/BL-B74.md`/`plans/
  emitter-visibility/plan.md`'s amend-on-merge notes (plan's "Second-order effect") are still owed
  — implementation.md deviation 4 flags this correctly as out of the Implementer's remit ("does
  not own that plan file"). Worth doing at merge time, not blocking this review.

### Verdict

**APPROVED WITH MINOR FIXES** — both required fixes are documentation-only (CLAUDE.md invariant
text, STRUCTURE.md module entries), cost no code change, and do not need to loop back through
Implementer; they can be applied directly before merge.

### Review Confidence

Full read. All ten touched `src/` files read in full diff, both new tests files' fence/lock/
single-unit sections read, the four real-poll-loop Co-moving-Fields tests read in full, two
targeted mutation tests run against the two highest-risk invariants named in the dispatch
(no-omniscience fence, sight-lock-vs-OBSERV-off), and all four mechanical checks (`ruff format`,
`ruff check`, `mypy --strict`, `pytest`) run and confirmed green. Not spot-checked.
