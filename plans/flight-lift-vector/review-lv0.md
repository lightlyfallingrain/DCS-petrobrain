### Review Summary

Reviewed BL-16 lift-vector Stage LV-0 ("instruments and shadow, no behaviour change") on
`feature/bl16-lift-vector-law` (merged fast-forward, tip `56a5426ce72ead0eb1914796680d119499a54599`),
diff `4ccd3227..56a5426c` (3 commits: `b7efdc91`, `5ecf618c`, `56a5426c`), against
`plans/flight-lift-vector/plan.md`'s LV-0 section + amendments, `explore-notes.md`,
`implementation.md`, and `docs/acceptance/2026-11-23-bl16-lv0-card.md`. Full read of the diff and
every file listed in `implementation.md`'s "Files Changed"; all checks re-run directly rather than
trusted from the implementer's own report.

**No-behaviour-change claim holds, structurally, not just by the implementer's own say-so.** Grepped
every `fc_est`/`est_sample`/`est_due`/`read_estimator_raw` call site in `flight_control.lua`: the
estimator is invoked once in `run_flight_control`, writes only `fc_est`'s own module-level table and
the new wire fields in `push_flight_control_state`, and is reset on the same transitions
(`dt > DT_CAP`, `on_stop`, `reset(epoch)`, first sample) the plan's own Co-moving Fields table names.
Nothing in `law_update`/`law_apply_goal`/`law_outputs`/`write_outputs` reads `fc_est` — confirmed by
grep, not inferred from the comment. The `flight_profile.lua` move is a mechanical extraction: every
one of the 39 pre-existing toy-plant scenarios in `test_flight_control_law.py` still passes with the
same numeric assertions, which is the plan's own bit-identical bar, read correctly.

**Deviation 1 (law cadence stays per-frame, only the estimator moves to `LAW_HZ`) is the right
reading of LV-0's scope.** The plan's "Update rate, not every frame" prose under section A describes
the eventual architecture once the law actually consumes the estimator (LV-1+); LV-0's own
Implementation Plan bullet says only "Estimator (A) running every frame" and LV-0's own framing is
explicitly "no behaviour change" — moving `law_update`'s cadence would itself be a behaviour change.
Agrees with the main loop's own lean. No fix needed.

**Deviation 2 (`fc_est_lambda` hard-codes 25/50 km/h) is acceptable for LV-0.** The plan's own
amendment text (line 18) and `flight_profile.lua`'s header both say the regime-blend breakpoints are
deliberately not in the profile yet, first needed by LV-3. `lambda` is reported-but-unread, explicitly
commented as a placeholder. No fix needed.

**Estimator correctness**: the ring-buffer eviction fix (`oldest_idx = ((head - count) % CAP) + 1`)
is correct — verified against the regression test and worked the eviction math by hand for count=1
and count=2 cases. The Euler-rate transform matches the plan's own 60°-bank worked example and is
pinned by a test. Reset/priming on `dt > DT_CAP`/negative dt/first-sample is tested and matches the
plan's Co-moving Fields row exactly (`dt > DT_CAP`, mission stop, `reset(epoch)` — which calls
`on_stop` which calls `est_reset` — and first frame). All timing confirmed on `t` (DCS model time,
threaded from `Export.lua`'s `LuaExportBeforeNextFrame`), never wall clock.

**One real numerical-precision gap, not a behaviour risk at this stage**: see Required Fixes — the
"sums stay well-conditioned" comment overstates what the one-time `t0` rebase actually guarantees
over a long session.

**Per-frame cost**: `est_due` is checked before any `LoGet*` read (confirmed by reading the call
order in `run_flight_control`), so an off-due frame (the large majority at ~140 Hz DCS frames against
30 Hz `law_hz`) costs two comparisons. The unselected velocity source and logged-only channels
(`LoGetAccelerationUnits`, AoA/AoSS) are read only under the trace flag — confirmed by reading
`read_estimator_raw`. Both of `perf-plan-review.md`'s "NOW" findings are addressed in the code, not
just claimed.

**Card**: uses `$DCS_COLLECTOR_IP` from `run-scripts/petrobrain.env` correctly, states no new deploy
step, and puts SAU off in the setup line — but see Required Fixes for the branch name itself, which
is the one thing wrong with it.

### Required Fixes

- **The card names a branch that no longer exists.** `docs/acceptance/2026-11-23-bl16-lv0-card.md`
  line 3 says "Branch to fly: `impl/lv0`" with a conditional fallback to
  `feature/bl16-lift-vector-law` "if this has already been harvested." `impl/lv0` was the
  implementer's own worktree branch and has already been harvested and deleted (`git branch -a` shows
  no `impl/lv0`, local or remote; LV-0's three commits are already on `feature/bl16-lift-vector-law`,
  which is what this review read). `git checkout impl/lv0` in the user's root will fail. Per root
  `CLAUDE.md` ("Workflow") and `AGENTS.md` ("Naming the branch is the only way they learn what to
  test"), the card is the only channel that tells the user what to fly — it must name the branch that
  actually carries the work at the point the user reads it. Fix: update the card to say "Branch to
  fly: `feature/bl16-lift-vector-law`" and drop the conditional/stale-branch language. (This is a
  one-line card edit, not a code change — no re-test of the estimator logic needed.)

### Optional Refinements

- **The "sums stay well-conditioned" claim in `est_ring_push`'s comment is not quite true, and is
  worth tightening before LV-1 makes the estimator's output load-bearing.** `ring.t0` rebases once, to
  the ring's own first-ever sample, not per-window — so as DCS model time grows across a long
  session, `rt = t - ring.t0` grows unboundedly even though the comment says "the sums never see more
  than `window_s` seconds of absolute magnitude." Worked the cancellation out by hand: the
  least-squares denominator `n*Σt² - (Σt)²` is mathematically shift-invariant, but the two terms being
  subtracted both grow as `O((n·T)²)` while the true difference stays `O(n·window_s²)`, so the
  relative floating-point error in the slope grows roughly quadratically with session length (T). At
  realistic sortie lengths (this project's own `w_v_s`/`w_a_s` windows are ≤0.2 s, `T` in the low
  thousands of seconds) the error stays far below anything that would show up on a card — not a
  defect in LV-0's own shadow-only output. But the comment overclaims, and LV-1+ will read this value
  in closed loop. Worth either correcting the comment to say what the rebase actually buys (bounded
  *within-window* spread, not bounded absolute magnitude) or periodically re-basing `t0` when a ring
  fully re-primes, before a stage that trusts this number for control. Not blocking for LV-0 — shadow
  only, no behaviour change — but flag it now rather than let the comment mislead the next reader.
- **`flight_trace_log` never calls `:flush()`, unlike `core.lua`'s own `debug_log` (which flushes
  every write).** Both are append-mode per-frame diagnostic logs; the asymmetry is unexplained and
  risks losing buffered trace lines if DCS exits uncleanly mid-card (the card's own rows (a)/(c)/(e)/
  (f) depend on reading the log intact after landing). Cheap to match the existing pattern (`:flush()`
  after `:write()`), optional since the card is a short, deliberate flight and DCS exiting mid-card is
  an edge case, not the expected path.

### Verdict

APPROVED WITH MINOR FIXES

The one required fix is a card correction (stale branch name), not a code change — LV-0's own
behaviour-preservation claim, estimator correctness, reset coverage, and performance gating all check
out against the plan and against re-run checks, not just against the implementer's report. Fix the
card line before handing it to the user; no re-review needed for that fix alone (trivial,
non-functional edit) unless the branch name is also wrong elsewhere in the card.

### Review Confidence

Full read — plan LV-0 section + amendments, explore-notes, implementation.md, the full diff
(`aircraft-layer/dcs-export/Export.lua`, `flight_control.lua`, new `flight_profile.lua`, schema,
all four touched/added test files), and the card. All checks re-run directly in this worktree
(not trusted from the implementer's report): `ruff format --check`/`ruff check` (pass, 90 files),
`mypy src --strict` (pass, 29 files), `.claude/scripts/fast-tests.sh aircraft-layer` (987 passed),
`luac5.1 -p` on every `dcs-export`/`Petrobrain` Lua file (pass), and the `luac5.1 -l -p` GETGLOBAL
check on `flight_control.lua` and `flight_profile.lua` (clean — every global is stdlib, a genuine DCS
API, or a legitimate cross-module global; `flight_profile.lua` reads no global at all). Did not run
the full subproject suite with `--full` (DoD's own job per root `CLAUDE.md` "Verification") — the
targeted `fast-tests.sh` run covers every file this diff touches.
