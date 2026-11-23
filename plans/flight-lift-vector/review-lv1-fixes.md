### Review Summary

Reviewed the LV-1 fix round answering `review-lv1.md`'s three required fixes, on
`feature/bl16-lift-vector-law` tip `3fd0358f6f95d9e76579128d2aec469e6e586566` (one commit on top of
the reviewed `84cbc24`). Full read of the tip commit's diff against `implementation.md`'s "LV-1
fixes" section, the plan's amendment (LAW_HZ interleaved law, axis write every frame, model time),
and `docs/acceptance/2026-11-23-sortie-feedback.md`'s velocity-source row.

**Required fix 1 — `law_update` gated to `profile.law_hz`, never the same frame as the
estimator.** Built as described: `law_due`/`fc_law_last_update_t` mirror `est_due`'s own shape;
`law_dt` is time since `law_update` itself last ran (DCS model time via the caller's own `t`,
never the per-frame `dt`), falling back to `nil`/"due immediately" at every site that already
clears `fc_law` (take/release/park/stop/reset), plus at `law_init_at_take` itself. `law_outputs`
stays per-frame and is the one piece of the law that is not gated — read it directly: it is the
cheap `u = T + k*(target-attitude) - k_d*rate` combination only, no integrator, no trig beyond the
existing wobble, never the shapers/chain/trig `law_update` owns, and the axis write underneath it
is unconditional every frame — matches the plan's own amendment ("the axis write itself may have
to stay every frame -> this is true") exactly.

**Collision rule — "defer once, then force."** Traced the actual branches in
`run_active_frame`: `if law_is_due and estimator_due_this_frame and not fc_law_deferred_last_frame
then` (defer, set the flag) `elseif law_is_due then` (run, regardless of
`estimator_due_this_frame`). I mutated this to an unconditional defer (dropped the `not
fc_law_deferred_last_frame` clause) and re-ran `TestUnparkTakeSeedClampsToMode1Limits` plus
`TestLawHzScheduling`: three tests failed exactly as the commit message claims (starvation —
`fc_in_band_speed` never flips true because `law_update` never runs after the take). Reverted and
confirmed the full suite green again. The fix is real, not merely claimed.

**Can the force-through branch itself land on the same frame as the estimator, at a realistic
40–200 Hz jittery rate?** Worked through it by hand rather than trusting the test's own 0 ms-jitter
140 Hz loop. The force-through only collides if `estimator_due_this_frame` is *also* true on the
very frame after a deferral — i.e. the estimator becomes due again within one single frame step
of having just run. The estimator's own period is `1/law_hz ≈ 33.3 ms`; even at the stated floor
of 40 Hz, one frame step is `25 ms < 33.3 ms`, so the estimator cannot become due again within a
single ordinary frame after firing. At the stated 40–200 Hz envelope, the force-through path is
therefore unreachable in practice — the collision-on-force case only exists when two *consecutive*
frames each exceed the law's own ~33 ms period (sub-30 fps for two frames running), which is
below the stated realistic floor. **This is the right answer to the review's open question, but
it rests on an assumption (DCS frame rate never sustains two consecutive sub-30 fps frames) that is
asserted, not measured from a live sortie.** A real performance hitch (heavy scene, explosion) is
exactly the scenario most likely to produce two slow frames in a row, and is also the worst moment
to add a second module's worth of trig/integrator work to one frame. Not a required fix — the
fallback behavior if it does happen is "law runs on schedule, one frame costs a bit more," not a
correctness defect, and the user's own instruction (correctness/never-starve over soft real-time
niceness) is satisfied — but worth a one-line note in a future performance pass if a flight log
ever shows a correlated frame-time spike. See Optional Refinements.

**`DT_CAP` guard on `law_dt`.** Mutated the guard (removed the `<= DT_CAP` clause, so `law_dt`
always resolves to the full stale gap) and re-ran
`TestPauseRowHolds::test_the_resume_frame_after_a_huge_jump_takes_no_giant_law_step`: failed
(`0.0401 > 0.01`), matching the implementer's own measured "red" figure almost exactly. Reverted,
confirmed green. The guard is real and the test catches its removal.

**Required fix 2 — `t0` rebases periodically, sums re-derived, not just shifted.**
`est_ring_rebase` recomputes `sum_t`/`sum_t2`/`sum_tv` from scratch by iterating every live sample
(`ring.count`, never the full `EST_RING_CAPACITY`) and shifting each stored `rt` by `-shift` —
`sum_v`/`count`/`head`/the stored values are untouched, a pure time-shift. This is "re-derive the
sums," not "shift the old sums," which is the form that actually resets the cancellation error
rather than carrying it forward. Order in `est_ring_push` is correct: rebase happens (if due)
*before* the new sample is folded in and *before* the window-eviction loop runs, so eviction always
operates on consistent, already-rebased timestamps. Mutated the trigger (`if false then` in place
of the interval check) and re-ran `TestRingRebasing`: failed at the first checkpoint
(`3.0345`, 1.15% relative error vs. the 1% bound) — matches the implementer's own measured "red"
figure. Reverted, confirmed green (all four checkpoints <1%, the end-of-run figure ~0.08% as
claimed). The long-run test is meaningful, not decorative, and the periodic-rebase answer (vs. a
one-time refit) is the one the plan's own alternative named.

**Required fix 3 — the trivial fixes.** `flight_profile.lua`'s `velocity_source` default is now
`"vector"`, `"position"` stays selectable, and the comment correctly cites the sortie trace's row
(e) and the turn-window-lag caveat — matches `docs/acceptance/2026-11-23-sortie-feedback.md`'s own
"Decision (main loop, from this data)" line verbatim in substance. `aircraft-layer/CLAUDE.md`'s
`flight_control` bullet is updated accurately (names the default, the scheduling split, matches
the code). `body-layer/ROADMAP/BL-16.md` lines 701–703: the duplicated sentence is gone and the
paragraph now reads correctly ("The user's control principles, verbatim, are in
`plans/flight-desired-state/explore-notes.md` (\"Mode 1 control principles\"): the cyclic
tilts...") — read the rendered text directly, not just the diff, to confirm the join across the
two edited hunks reads as one sentence; it does.

**The three pre-existing tests given an extra `run_flight_control` call.** Read each: only the
driver gained one more call (`flight_control.run_flight_control(0.4)` before the final
`push_flight_control_state`); no assertion changed. The added docstrings correctly explain why —
at this driver's 0.1 s step (coarser than `law_hz`'s ~0.033 s period), the first post-take ordinary
frame always collides and defers once, so a second ordinary frame is needed to reach the frame
`law_update` (which computes `in_band_speed`, what these tests check) actually runs on. Legitimate,
not weakened — confirmed by reverting the scheduling fix (the starvation mutation above) and
watching exactly these three tests fail.

**Bumpless take, anti-windup, primed-estimator gating.** All three are unchanged by this diff
(no edits inside `law_init_at_take`, the anti-windup integrator guards, or the
`fc_est.primed`/`law_init_at_take` priming gate) and all pass in the full re-run (996 passed).

### Required Fixes

None.

### Optional Refinements

- **The force-through branch's "collision allowed after one defer" is unreachable at the stated
  40–200 Hz floor by the arithmetic above, but that rests on DCS never sustaining two consecutive
  sub-30 fps frames — asserted here, not measured from a live sortie.** Worth a one-line note (in
  this plan or a backlog item) to check a flight's own frame-time log the next time one is taken
  with the new scheduler live, specifically for a same-frame `law_update`/estimator collision
  landing during a performance hitch. Not a blocker: the fallback is extra one-frame cost, not an
  incorrect result, and it is exactly the tradeoff (never-starve over never-same-frame) the user's
  own direction prioritized.
- `fc_debug_estimator_sample_count`/`fc_debug_law_update_count` and `M.debug_scheduling_counts()`
  are diagnostic-only and grepped clean of any wire use — fine as is, no action needed.

### Verdict

APPROVED

### Review Confidence

Full read of the tip commit's diff (`flight_control.lua`, `flight_profile.lua`, both touched test
files, `aircraft-layer/CLAUDE.md`, `body-layer/ROADMAP/BL-16.md`, `implementation.md`'s new
section) against `review-lv1.md`'s three required fixes and the plan's own amendment text.
Verified by mutation, not just by reading: temporarily removed the `DT_CAP` guard on `law_dt`, the
periodic-rebase trigger in `est_ring_push`, and the "defer-once" exit condition in the collision
rule, one at a time, confirming each regression reproduces the implementer's own measured "red"
figures (or the exact three starvation failures named in the commit message) before reverting and
re-confirming green. Worked the force-through collision question by hand against the stated
40–200 Hz envelope rather than trusting the scheduling test's own fixed-140 Hz, zero-jitter loop.
Ran, in this worktree (`aircraft-layer/.venv` symlinked from the main checkout, removed before
commit): `ruff format --check`/`ruff check` (clean, 90 files), `cd aircraft-layer && .venv/bin/mypy
src` (clean, 29 files), `.claude/scripts/fast-tests.sh aircraft-layer` (996 passed), `luac5.1 -p` on
both touched Lua files (clean), and the `luac5.1 -l -p` GETGLOBAL check on both (every global is
Lua stdlib, a genuine DCS API, or a legitimate cross-module global — `client`, `flight_desired`,
`flight_profile`, `ai_pilot_wheel`, `safe_call`, `debug_log`, `json_escape_string`,
`extract_json_number_field`, `fmt_num_or_null`/`fmt_int_or_null`, `GetDevice`, `io`/`lfs`; none is
this file's own local referenced before declaration — `flight_profile.lua` reads no global at
all). `body-layer` untouched by this diff, not re-run (matches `implementation.md`'s own note).
