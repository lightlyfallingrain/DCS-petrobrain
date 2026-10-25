### Debug Report

### Observed Issue

The 9K113 sight resumes dead ahead `(0.0, 0.0)` on every glance-away-triggered resume into
`SIGHTING`, instead of at its last believed position. Filed as `[[BL-B98]]`
(`body-layer/ROADMAP/BL-B98.md`), found during BL-B89 Stage 1's review and measured by that
stage's own `TestSightSearchLegs` (the "stays at last position" assertion failed against the
real code). Against the settled acceptance item `docs/acceptance/2026-10-20-sortie-feedback.md`
F4/F5 (*"Leave 9K113 at last position"*).

User direction 2026-10-25 (`BL-B98.md`, verbatim) set the governing rule:

1. OBSERV on→off, whatever the cause (Petrovich, pilot, DCS AI, `_force_observ_off`): believed
   sight aim resets to boresight `(0, 0)`.
2. While OBSERV stays on, the aim persists — through glance-away (`SIGHT_MAX_DWELL_S` and the
   BL-B89 lap-completion trigger), binocular excursion, idle, anything other than OBSERV off.
   Resume continues from the last position.
3. A zero axis write (the 2026-10-24 F1 fix, `e1d16037`) means "stop moving," not "go to
   boresight" — nothing may read a zero axis write or an idle/`None` look as the sight having
   recentred.

### Hypothesis

`_start_glance_away` (`body-layer/src/belief/optic_policy.py`) unconditionally nulled
`look_azimuth_deg`/`look_elevation_deg` to `None` on entry, for both triggers that call it (the
whole-dwell `SIGHT_MAX_DWELL_S` boundary inside `_decide_sighting`, and `_idle_sight_search`'s
lap-completion trigger) — both of which only ever fire while `home_phase is SIGHTING` (OBSERV
staying on; this is a scheduled break, never OBSERV turning off, which is `_force_observ_off`'s
separate path). The two functions that resume `SIGHTING` from that glance — `_back_to_home` and
`_enter_binocular_search` — both carry `state.look_azimuth_deg`/`look_elevation_deg` through
unchanged rather than re-deriving them, so "stays at last position" only ever held when the aim
was never nulled in the first place. Since it always was, by the time either resume function ran
the aim was already `None`, and `_back_to_home`'s own `None`-defaulting logic
(`azimuth = state.look_azimuth_deg if ... is not None else 0.0`) produced dead ahead every time.

A second, related gap: `home_phase`'s SIGHTING→SCANNING transition driven by the *observed*
arg-886 edge (`body.py`'s `run_once`, `[[BL-B80]]`) only ever changed `home_phase` itself, never
nulling the aim — unlike `_force_observ_off`'s manoeuvre-triggered path, which already nulls it
via `_back_to_home`'s non-SIGHTING branch. This is a real gap distinct from the glance-away bug:
if OBSERV turns off (observed edge, any cause) while a glance-away is already in progress
(`phase is SCANNING`, `home_phase` was `SIGHTING`), nothing in `decide_optic`'s dispatch revisits
that already-`SCANNING` phase to null the aim — `decide_optic` only nulls on a phase transition
*into* `SCANNING`, not on an `home_phase` change observed while already there. Left unfixed, a
later OBSERV-on would resume at the stale pre-glance position instead of boresight, violating
rule 1.

### Evidence

- Read `_start_glance_away`, `_back_to_home`, `_enter_binocular_search`, `_force_observ_off`,
  `_decide_sighting`, `_idle_sight_search`, and `_decide_without_guidance`'s glance-away resume
  point in `body-layer/src/belief/optic_policy.py` — confirmed both call sites of
  `_start_glance_away`, and that both resume functions carry the (already-nulled) aim through
  without re-deriving it.
- `body-layer/tests/test_optic_policy.py::TestSightSearchLegs::
  test_the_cycle_resumes_a_fresh_wide_near_pass_after_the_glance_away` and
  `test_an_out_of_regard_remainder_is_swept_once_the_glance_away_ends` explicitly asserted the
  buggy `(0.0, 0.0)` resume (comments: "resumed, dead ahead") — pre-existing tests pinning the
  defect rather than catching it.
- After removing the nulling from `_start_glance_away` (see Fix below), both tests failed with
  `assert (20.0, -3.0) == (0.0, 0.0)` and `assert 20.0 is None` — i.e. the fix produced the
  correct last-position value (`narrow_far_sweep`'s own step, the leg active when the lap
  completed), proving the hypothesis.
- Read `body.py`'s `run_once` (lines ~699–709) — confirmed `home_phase`'s observed-edge
  transition only ever changed `home_phase`, never the aim fields, for both directions.

### Fix Applied

1. **`body-layer/src/belief/optic_policy.py`, `_start_glance_away`**: removed
   `look_azimuth_deg=None, look_elevation_deg=None` from its `replace()` call. The function is
   only ever reached while `home_phase is SIGHTING` (a scheduled break, not OBSERV turning off),
   so the believed aim now survives it — `_back_to_home` (home_phase SIGHTING branch) and
   `_enter_binocular_search` (which deliberately omits these fields from its own `replace()`) now
   both correctly resume from the real last position, with no change needed to either of them.
   Docstrings on `_start_glance_away`, `_back_to_home`, and `_enter_binocular_search` updated to
   describe the fixed behaviour and attribute it to `[[BL-B98]]`.
2. **`body-layer/src/body.py`, `run_once`'s OBSERV-off branch**: the `elif observ_observed is
   False and home_phase is not SCANNING` branch now also sets `look_azimuth_deg=None,
   look_elevation_deg=None` in the same `replace()` that flips `home_phase`. This is the single
   place the observed on→off edge is detected regardless of cause (pilot command, DCS AI, or a
   readback that simply changed), closing the gap described above — the manoeuvre-triggered
   `_force_observ_off` path already nulled the aim via `_back_to_home`, so this makes both
   OBSERV-off paths behave identically per rule 1.
3. **No change to `_force_observ_off`, `_back_to_home`'s non-SIGHTING branch, `lower_binoculars`,
   or `_decide_sighting`'s natural-look-finished commit** (`look_azimuth_deg=None` at line ~2097):
   these already null the aim in cases that are either genuine OBSERV-off (correct per rule 1) or
   immediately followed by picking a fresh target / recomputing from the idle search cycle's own
   steps (never surfaced as a visible "dead ahead" resume, so not `[[BL-B98]]`'s defect).
   `lower_binoculars` dropping an in-progress `SIGHTING` look back to idle while OBSERV stays on
   was checked specifically against rule 2 and left alone: the very next poll's idle-search branch
   computes a fresh, legitimate aim from `sight_search_leg`'s own steps rather than reading the
   nulled `look_azimuth_deg`, so no dead-ahead artifact is produced on this path.
4. **Tests** (`body-layer/tests/test_optic_policy.py`): updated the two pre-existing assertions
   that pinned the buggy dead-ahead resume to instead assert resume at
   `_NARROW_FAR_SWEEP_STEPS[0]` (the last position before the lap-completion pause), with
   docstrings rewritten to describe the fixed behaviour.
5. **New regression test** (`body-layer/tests/test_body.py`,
   `test_run_once_resets_the_believed_sight_aim_to_boresight_on_observed_observ_off`): drives
   `run_once` with `decide_optic` faked to echo its input unchanged, seeds `optic_state` with a
   mid-look aim held off boresight and `home_phase is SIGHTING`, then flips
   `guidance_unit_state.observ_observed` to `False` and confirms `run_once`'s own pre-`decide_optic`
   transition handling (not `decide_optic` itself) resets both `home_phase` and the aim fields —
   covering the gap in Fix 2 above, which the pre-existing `TestSightSearchLegs` suite (entirely
   within `optic_policy.py`, never through `run_once`) could not reach.

No `tuning.py` constant was needed — this is a correctness fix to existing state transitions, not
a new behaviour-affecting threshold.

### Verification

From `body-layer/` (resolving `.venv/bin/` tools against the main checkout's venv, since this
worktree has none of its own):

- `pytest tests -q` — **2588 passed, 4 xfailed** (was 2587 passed before the new regression test;
  no regressions, the two updated assertions now pass against the fixed behaviour).
- `ruff format --check src tests` — **173 files already formatted**.
- `ruff check src tests` — **All checks passed**.
- `mypy src` — **Success: no issues found in 74 source files**.

No aircraft-layer changes were needed: the 2026-10-24 F1 fix (zeroing the AI slew axes in
`Export.lua` on the OBSERV on→off edge) is a physical-servo concern entirely inside
`aircraft-layer/dcs-export/Export.lua`, independent of body-layer's *believed* aim — this fix only
changes what Petrovich believes the sight is pointed at, which is the half of the F1 open question
("whether zero recentres or only halts the mark") that belongs to this layer. `aircraft-layer`'s
own test suite was not run since no file under `aircraft-layer/` was touched.

**Left for flight**: whether the resumed-at-last-position behaviour reads correctly to the pilot
in practice — a believed aim is not itself observable, only its downstream effects (what Petrovich
reports, and the simulated `SightHead`'s own slewing back to that aim) are. No `#needs-flight`
marker beyond what `BL-B89`'s own roadmap entry already carries for the wider feature.
