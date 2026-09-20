### Review Summary

Reviewed the final state of `feature/detection-cones-slice1` against `plans/detection-cones-slice1/plan.md`'s
"Final shape: naked eye by default" section (the authoritative target, per the coordinator's
framing — the branch was redirected four times mid-session and the plan text is current).

The delivered code matches the final intended shape exactly: `check_visibility`'s default optic
resolves to `UNAIDED_OPTIC` (M=1.0); `BINOCULAR_OPTIC` is a Б-6 6×30 with `magnification=4.0`
(derived, not restored) and a real `fov_half_angle_deg=4.25`; `BINOCULAR_RANGE_MULTIPLIER`
completed its 4.0 → 8.0 → 4.0 round trip and lands on 4.0; no 9K113 entries, no field-of-regard
fields, no `handheld_effectiveness`/`effective_magnification` remnants anywhere in source or
tests. `cockpit_mask.py` is untouched, `perception` still does not import `belief`, and
`body-layer/CLAUDE.md` is fully updated and consistent with the shipped code.

Independently re-ran the full verification sequence (not taken on the implementer's word):
- `ruff format --check src tests`: pass (78 files)
- `ruff check src tests`: pass
- `mypy src` (from `body-layer/`): pass, 36 source files
- `pytest -q`: **732 passed**, 0 xfailed — matches the implementation notes exactly

Test-integrity audit (the top priority for this review) came back clean. Every rewritten
assertion in `test_mock_flight_chain.py`, `test_naked_eye_source.py`, and
`test_vision_calibration.py` was independently re-derived from the arithmetic and cross-checked
against a live run, not just trusted:
- `test_mock_flight_chain.py`'s 2/56 → 1/36 count change is arithmetically correct: object 102
  (Infantry, 1.8 m) has a `lowres` threshold of 600 m at the new default (`1.8/0.003*1.0`), and
  its closest approach across the fixture's 20 frames is ~689 m slant range — genuinely never
  admitted. Object 101 (truck, 6 m) has thresholds of 428.57 m (medres) / 214.29 m (hires); the
  fixture's own track never gets that close before the cockpit mask cuts it off, so it stays
  `lowres` throughout — consistent with 16 naked-eye + 20 hybrid = 36.
- `test_naked_eye_source.py`'s two rescaled geometry fixtures (`_CAP_TEST_RANGES_M`/
  `_CAP_TEST_CROSS_OFFSETS_M` and the cluster-splitting scenario) were genuinely re-derived, not
  flat-rescaled — offsets were grown relative to range specifically because apparent angular size
  is not range-invariant, and the accompanying `_high_ownship()` AGL offset was rescaled by the
  same factor as its range spread to preserve the depression-angle relationship the split test
  depends on. Ran green.
- `test_vision_calibration.py`'s `_STALE_AT_8X_MULTIPLIER` `xfail` set is fully gone (grepped for
  `xfail`/`STALE` in the file — the only hits are historical prose in a comment block), the test
  function is a plain assertion again, and it passes in full: 46 passed, 0 xfailed, independently
  confirmed.

One real drift found outside the diff itself, in `body-layer/ROADMAP.md` (see Required Fixes).

### Required Fixes

- **`body-layer/ROADMAP.md`'s "Cones, calibration and the sortie are interdependent" entry is now
  factually backwards and not marked done.** Line 773 still reads: "enough to make 'scan north'
  mean something and to make **the binocular default an explicit choice**" — but the shipped
  outcome is the opposite: slice 1 made naked-eye the *default* and binoculars an explicit,
  non-default choice. This isn't a stale aside; it's the roadmap's own description of what slice 1
  accomplishes, and it's inverted relative to what the code now does. Per root `CLAUDE.md`'s
  "Session Start" flow, the next session reads this file to find "the next actionable milestone,"
  and per `body-layer/CLAUDE.md`, ROADMAP.md is the canonical milestone-status source, not
  `plan.md`. Right now nothing in ROADMAP.md marks slice 1 done at all — a reader has no way to
  tell from this file that slice 1 shipped, and the one sentence describing its outcome says the
  wrong thing. Needs: mark slice 1 done, correct the "binocular default" framing to "naked-eye
  default," and apply the Milestone Completion one-liner root `CLAUDE.md` asks for (does this
  change what slice 2 should be, or invalidate a downstream assumption — the plan's own Decision 4
  and Risks section already have the raw material for this).

### Optional Refinements

- **Stale git sequencer state in the repo (`.git/sequencer/`, no active `CHERRY_PICK_HEAD`) makes
  `git status` report "Cherry-pick currently in progress"** even though the working tree is clean
  and matches `HEAD` (`acbb8eb`) exactly — confirmed no staged/unstaged diff against `HEAD`. The
  sequencer's own `todo` file references commits unrelated to this feature (9K113 research/docs
  commits), so this looks like leftover housekeeping from an earlier session, not something this
  branch's work depends on. Harmless to this review's findings, but worth a `git cherry-pick
  --quit` before further work on this repo, since a stray `git status`-trusting operation by
  another agent could misread the state (optional — not this feature's responsibility, and
  destructive-git-op caution argues for leaving the call to the user rather than the reviewer
  acting on it).
- `clustering.py`'s separability floor (`theta_sep * BINOCULAR_RANGE_MULTIPLIER >=
  LOWRES_ANGULAR_RADIUS_RAD`) still hardcodes the binocular constant while the live default gate
  now runs at M=1.0. Checked the algebra: the floor stays provably non-binding as long as
  `BINOCULAR_RANGE_MULTIPLIER >= optic.magnification` for whatever optic is actually in the live
  path, which holds today (1.0 and 4.0 are both ≤ 4.0) — so this is not a live bug. This is exactly
  the risk the plan's own "Risks & Unknowns" section already names and explicitly defers
  (`clustering.py` was correctly left untouched per the plan's "Not touched" list). No action
  needed now; flagging only so slice 2 doesn't have to rediscover the algebra from scratch.

### Verdict
APPROVED WITH MINOR FIXES

### Review Confidence
Full read — plan, both implementation-notes passes, full source diff (`optics.py`,
`visibility.py`), all five changed/new test files read in full or diffed and independently
re-derived where the top-priority test-integrity concern applied, `body-layer/CLAUDE.md` read in
full, `body-layer/ROADMAP.md`'s relevant section read. Verification commands re-run directly
(ruff format/check, mypy --strict, pytest -q), not taken from the implementation notes.
