### Review Summary

Reviewed commit `01a6fadd` (parent `23898e70`) on `feature/9k113-scan-procedure`, the debugger's
fix for `[[BL-B98]]` — the 9K113 believed sight aim resetting to dead-ahead on a glance-away resume
instead of staying at its last position, against the user's 2026-10-25 rule (`body-layer/ROADMAP/
BL-B98.md`):

1. OBSERV on→off, any cause → believed aim resets to boresight `(0, 0)`.
2. While OBSERV stays on → aim persists through glance-away, binoculars, idle.
3. A zero axis write is "stop moving," not "go to boresight."

The fix is two one-line-scope changes plus test updates:

- `optic_policy.py`'s `_start_glance_away` no longer nulls `look_azimuth_deg`/`look_elevation_deg`
  on entry (both its call sites — `SIGHT_MAX_DWELL_S` and `_idle_sight_search`'s lap-completion
  trigger — only ever fire while `home_phase is SIGHTING`, i.e. OBSERV staying on).
- `body.py`'s `run_once` OBSERV-observed-off branch (the `elif observ_observed is False and
  home_phase is not SCANNING` edge) now also nulls both fields in the same `replace()`, closing a
  second gap: previously only `home_phase` changed there, so OBSERV turning off while a
  glance-away was already in progress (`phase is SCANNING`, `home_phase` was `SIGHTING`) left the
  pre-glance aim on `self.optic_state`, to be read back on the next OBSERV-on instead of boresight.

**Traced every OBSERV-stays-on path by hand and confirmed each against rule 2, then mutation-tested
both fix halves independently** (reverted each in turn, confirmed the test suite catches the
regression, restored, confirmed a clean diff and a green suite):

- `_start_glance_away` (both triggers) — carries the aim through; `_back_to_home` and
  `_enter_binocular_search` both read the un-nulled value. **Reverting the removed nulling fails
  both updated `TestSightSearchLegs` assertions** (`20.0 == None`, `None == 20.0`).
- `body.py`'s observed-edge branch — **reverting the added nulling fails the new regression test**
  (`35.0 is None` → `AssertionError: assert 35.0 is None`, the test's own `fake_decide_optic` isolates
  this to `run_once`'s pre-dispatch handling, not `decide_optic`).
- `lower_binoculars` (phase is home_phase, in-progress SIGHTING look dropped to idle): nulls the
  aim, but the very next poll's `_idle_sight_search` always recomputes `azimuth, elevation =
  steps[index]` from `sight_search_leg`'s own sequence — confirmed by reading that function
  (lines 1989-1997) — so the nulled value is never read back as a decision; no dead-ahead artifact
  surfaces. No defect here; the debugger's claim in `debug-bl-b98.md` item 3 checks out.
- `_decide_sighting`'s natural-look-finished commit (line ~2097) nulls the aim, but falls through
  in the *same call* to either `_idle_sight_search` (fresh step-derived aim) or a newly chosen
  target's own sweep — the `None` never escapes as an `OpticDecision`. Transient, not a resume
  path; correctly left alone.
- `_force_observ_off` (violent-manoeuvre OBSERV-off) — unchanged, already nulls via
  `_back_to_home`'s non-SIGHTING branch; this is rule 1's other trigger and is consistent with the
  new `body.py` edge-trigger (same effect, different cause).

**Edge-triggering and double-up**: the `body.py` branch's guard (`home_phase is not SCANNING`)
makes it self-resetting — once it fires, `home_phase` becomes `SCANNING`, so it will not refire on
a subsequent poll with OBSERV still off. It fires on the genuinely new case the debugger
identified (OBSERV off while `home_phase` was already `SIGHTING` mid-glance-away, i.e.
`phase is SCANNING, home_phase is SIGHTING` — the condition's `home_phase is not SCANNING` is true
throughout a glance-away, since `home_phase` is deliberately left at `SIGHTING` across it). It does
not double up destructively with `_force_observ_off`: both set `home_phase=SCANNING` and null the
aim, and nothing calls both in the same poll for the same transition — one is a command-driven/
observed-edge path inside `run_once`, the other is read inside `decide_optic` from a violated rate
limit. Idempotent either way.

**Rule 3 / SightHead boresight check**: confirmed in `sight_head.py`'s `advance_sight_head`
(pre-existing, unchanged by this fix) that a `None` desired body aim while OBSERV stays on makes
the head **hold its current direction**, not snap to boresight (`"Nothing sight-tier desired this
poll and no seen/held track -- hold the head's own current direction rather than snapping to a
fabricated 'belief' goal of (0, 0)"`, lines 390-399). Only `not observ_observed` (OBSERV genuinely
off) returns a fresh all-`None` `SightHead()`. So even where a transient internal `None` exists
(the look-finished commit case above), it was never going to read as a boresight command if it had
leaked — the layer below already enforces rule 3 independently.

**BL-B89 lap-completion / `choose_sighting_look`/`current_level` interaction**: a completed lap
resets `sight_search_leg` to `"wide_near"` and calls `_start_glance_away`, which (post-fix) leaves
the aim at the lap's last position. The glance-away resume then briefly reports that last position
for one poll (`_back_to_home`'s SIGHTING branch), and the following poll's `_idle_sight_search`
immediately recomputes from the new `"wide_near"` leg's own first step — matching the updated test
`test_the_cycle_resumes_a_fresh_wide_near_pass_after_the_glance_away`'s own sequencing. `choose_
sighting_look`/`current_level` (target selection, classification specificity for commit purposes)
are untouched by this fix and have no interaction with the aim-persistence mechanism.

**Comment pruning**: the three touched docstrings (`_back_to_home`, `_start_glance_away`,
`_enter_binocular_search`) read as genuine supersession, not deletion — each keeps the
pre-fix behaviour described ("Before that fix... dead ahead (0.0, 0.0)") alongside the new
behaviour and its attribution to `[[BL-B98]]`, satisfying the dated/attributed-record rule. No
`#:` tuning block touched (correctly — no `tuning.py` constant involved, this is a correctness fix
to existing transitions). No boundary case silently dropped from a comment with no accompanying
test — both touched functions' prior defect descriptions are now covered by the updated/new tests
above.

**Checks run** (from `body-layer/`, this worktree had no `.venv`, resolved against the main
checkout's venv per `body-layer/CLAUDE.md`):

- `ruff format --check src tests` — 173 files already formatted.
- `ruff check src tests` — All checks passed.
- `mypy src` — Success: no issues found in 74 source files.
- `pytest tests -q` — 2588 passed, 4 xfailed (unchanged from the debugger's own reported count).

Performance and security passes are waived for this fix per user direction ("skip perf and sec
now, do them with stage 2 code") and were not run.

### Required Fixes

None.

### Optional Refinements

- None found. Scope is tight — two call-site-local changes plus the tests that pin them; no
  unrelated refactoring, no scope creep into `_force_observ_off`/`lower_binoculars`/the
  natural-look-finished commit, each of which was explicitly checked and correctly left alone with
  a stated reason in `debug-bl-b98.md`.

### Verdict
APPROVED

### Review Confidence
Full read — every OBSERV-stays-on path named in the review brief was traced by hand in
`optic_policy.py`/`body.py`/`sight_head.py`, both halves of the fix were independently
mutation-tested (revert → confirm red → restore → confirm clean diff and green suite), and the
full subproject check suite (`ruff format`/`ruff check`/`mypy`/`pytest`) was run directly rather
than taken from the debugger's report.
