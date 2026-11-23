### Review Summary

Reviewed BL-16 lift-vector Stage **LV-1** ("forward-flight law, no hand-back") on
`feature/bl16-lift-vector-law`, diff `7d0c6ef4..9e9e62d0` (3 commits: `25a0697c` the law itself,
`cc868c1d` body-layer floor removal, `9e9e62d0` card/roadmap/docs), against `plans/flight-lift-
vector/plan.md` (full, including the amendment and U1–U8 answers), `explore-notes.md`,
`implementation.md`'s LV-1 section, `debug-2026-11-23.md`, `review-lv0.md`, the 2026-11-23 sortie
feedback, and the LV-1 card. Full read of the diff, re-ran every check myself (not trusted from the
implementer's report).

**The six binding items from the LV-0 sortie, checked against the code, not the description:**

1. **VELOCITY_SOURCE** — `flight_profile.lua` still reads `velocity_source = "position"`, with
   `"vector"` fully wired and selectable (confirmed in `flight_control.lua`'s `read_estimator_raw`/
   `est_sample`). **The dispatch's premise that this should now be `"vector"` does not match the
   written record** — I read the full LV-0 sortie feedback and the debug pass, and found no
   statement anywhere confirming `LoGetVectorVelocity` actually matches `dP/dt` on all three axes
   (the LV-0 card's row (e) is exactly the row that was supposed to settle this, and the sortie
   feedback's "E — Sideslip" section reports estimator outputs but never states the vec-vs-pos
   comparison's answer). `flight_profile.lua`'s own comment says `"position"` stays default "until
   a card confirms `LoGetVectorVelocity` matches `dP/dt` on all three axes" — which is exactly
   where things stand. **Not a code defect**: keeping `"position"` absent a recorded confirmation
   is the correct, conservative choice, and matches `aircraft-layer/CLAUDE.md`'s own current
   description. If the main loop or the user has a recollection of this being confirmed verbally
   and not written down, that needs capturing in the sortie-feedback file per this project's own
   "write it down first" rule — I cannot find it in the record I was given.
2. **Anti-windup, toy-plant test from bad initial attitudes** — met. `TestAntiWindupPreventsThe
   RetestDivergence::test_take_from_30deg_bank_10deg_nose_down_mid_turn_converges` takes from 30°
   bank, 10° nose down, mid-turn (`r_deg_s = 8.0`), runs 3000 steps, and asserts roll rate stays
   under 100°/s (the retest's own crash reached 536°/s) and bank/pitch never approach ±90°, settling
   to within 5° of level. Read section H in `flight_control.lua`: every integrator (`phi_i`,
   `theta_i`, `u_c_i`, `t_p`, `t_r`, `t_y`) has its own anti-windup guard (freeze on push-further-
   into-saturation, plus the trim loops' own attitude-not-following hold) — confirmed by reading
   each site, not just the comment.
3. **Bumpless take** — met. `TestTakeIsBumpless` proves the integrators seed from measured state,
   not zero; `TestBitExactAtTake` (pre-existing, re-verified still passing) proves the first written
   output equals the captured command exactly, including with nonzero body rates at capture.
4. **LAW_HZ interleaved law, axis write every frame** — **not built; this is a required fix** (see
   below).
5. **Law never acts on an un-primed estimator; `t0` rebasing numerical-drift note** — the
   un-primed-estimator guard is correctly built (`fc_est.primed`, checked in `run_flight_control`
   before `law_update` runs — confirmed by reading the call site, not the comment: an un-primed
   frame holds integrators and feeds `nil` sentinels, never a fabricated zero, into `law_outputs`'
   own documented fallback). **The `t0` numerical-drift note was not decided or fixed in LV-1, and
   the report does not mention it — confirmed, this is a required fix** (see below).
6. **Preserved behaviours** — confirmed by reading the diff, not assuming: zero-axis-writes-after-
   release (the LV-0 debug pass's problem-1 fix — `pending_release_says`/`flight_pending_release`
   ack-gating in `crew_console.py`/`body.py` — is untouched by this diff); AI-overlay-activation-
   as-handover-to-mode-2 (no diff touches `ai_pilot_wheel.py`/`.lua` or the park/unpark path); SAU
   H/K/T/B handover-to-player sequence (unrelated branch, already merged, untouched here); the
   epoch/ack resync fix (`_resolve_command_reset` in `body.py`) — the only change near it is a
   comment update, confirmed by diff; SAU stays off/unused in the law (grepped `flight_control.lua`
   for `SAU` — only a comment naming it as M4, not-yet-built).

### Required Fixes

- **The `LAW_HZ` scheduler/interleaving was not built for `law_update`, for the second stage in a
  row, and the user's own direction was explicit and specific — this needs the architect's or the
  user's sign-off before being accepted as LV-1's shape, not a unilateral implementer deferral.**
  The user's own words (plan.md, section A): *"many of the flight control calculations (including
  estimator) don't really need to run every frame... 30Hz would be plenty... interleave
  calculations so that not everything is calculated in a single frame"* — confirmed *"the axis
  write itself may have to stay every frame -> this is true"*, i.e. everything **except** the axis
  write was meant to move to the scheduled/interleaved cadence. LV-0's own review accepted deferring
  this once, explicitly on the grounds that LV-1 — "the first stage that actually changes what the
  law does" — was where it belonged. LV-1's implementation defers it again, with a structurally
  identical "flagged for the architect's own review" note but no evidence the architect was
  actually asked. The implementer's risk argument (splitting `law_update`'s bit-exact-take/anti-
  windup/take-seed state machine across interleaved phases is a materially larger, separately risky
  change) is real and worth weighing, but it argues for *care*, not for silently deferring a twice-
  stated, specific user instruction a second time. It also doesn't fully answer the user's own
  reasoning: *"estimator's `LoGet*` reads are already gated to `LAW_HZ`"* addresses the per-frame
  **I/O** cost the perf review flagged, but the user's complaint was about the flight-control
  **calculations** generally (trig-heavy lift-vector math, the priority chain, the integrators) —
  `law_update`'s own CPU cost at 140 Hz vs 30 Hz was never measured or compared anywhere in this
  pass. Recommend: take this back to the architect (or the user directly) as a named plan amendment
  — either get explicit sign-off to defer again to LV-2/LV-3 with a stated reason, or build it now.
  Do not let a third stage pass silently on the same deferral.
- **The `t0` rebasing numerical-drift note from `review-lv0.md` was not addressed, and LV-1 is
  exactly the stage that makes it matter.** `review-lv0.md`'s optional refinement said the "sums
  stay well-conditioned" claim overstated what the one-time `t0` rebase buys, and the LV-0 fix
  commit (`773e8b76`) only corrected the comment, explicitly adding *"re-check before LV-1 closes
  the loop on it."* LV-1 is that stage: `a_f`/`a_r`/`a_u` from the estimator are now read every
  frame by `law_update`'s own trim integrators (`phi_i`/`theta_i`/`u_c_i`) and by the bumpless-take
  seed (`law_init_at_take`) — closed-loop, exactly the condition the comment named. I grepped the
  LV-1 diff for `t0`/`rebase`/`well-conditioned` and found zero changes to `est_ring_push`/
  `est_ring_slope` or any new long-run test. `implementation.md`'s LV-1 section does not mention
  this at all — confirming the dispatch's observation. The error is small at realistic sortie
  lengths per the earlier hand-worked analysis, so this is unlikely to be a live-flight risk today,
  but it was explicitly named as something to decide and fix *now*, with a long-run test, not to
  carry forward silently a second time. Fix: either add the long-run test review-lv0 asked for
  (confirm the slope's relative error stays bounded over a multi-thousand-second `t0` run) and
  decide whether the current single-rebase is adequate, or re-base `t0` periodically as that
  comment's own alternative suggested — and say which, with evidence, before this is called closed.
- **`body-layer/ROADMAP/BL-16.md` has a duplicated, garbled sentence from the LV-1 doc commit.**
  Lines 701–703 read: "...regime) remain. The user's control / principles, verbatim, are in
  `plans/flight-desired-state/explore-notes.md` ("Mode 1 control / principles, verbatim, are in
  `plans/flight-desired-state/explore-notes.md` ("Mode 1 control..." — the sentence "principles,
  verbatim, are in `plans/flight-desired-state/explore-notes.md` ("Mode 1 control" is duplicated
  verbatim, clearly a bad edit that left the old line in place above the new one instead of
  replacing it. One-line fix, no re-test needed.

### Optional Refinements

- **Deviation 2 (single-`shortfall` priority chain) and deviation 3 (flat gains besides `G(V)`)
  are acceptable for LV-1** — both match the plan's own repeated "first cut, the cards tune" framing
  for every gain in this law, and deviation 2 preserves the user's own ordering (speed, then turn
  rate, then height, U3) even though the hand-off between the first two steps is approximated rather
  than measured. Worth a one-line note in the plan or a backlog item that the five flat gains
  (`K_L`/`K_c`/`K_phi_trim`/`K_theta_trim`/`K_ball_pedal`) are candidates for their own `(V)`
  schedules once a card shows a need, so this isn't silently forgotten — but not a blocker.
- **`fc_est_lambda`'s hard-coded 25/50 km/h placeholder (inherited from LV-0) is still unread by
  `law_update`** (LV-1 flies `λ = 1` throughout, as planned) — confirmed consistent, no action
  needed until LV-3.

### Verdict

NEEDS REVISION

Two required fixes are substantive (the `LAW_HZ` deferral needs the architect's or user's explicit
sign-off, not a second silent pass, and the `t0` drift note needs the long-run test or a periodic-
rebase fix review-lv0 asked for) and one is a trivial doc correction. Everything else checked out:
anti-windup, bumpless take, un-primed-estimator gating, every preserved behaviour from the LV-0
debug pass, the body-layer floor removal and its test rewrites (scoped to the removal, not
weakened elsewhere), the card, and all re-run checks (ruff format/check, mypy --strict, `fast-
tests.sh` for both touched subprojects, `luac5.1 -p`, the GETGLOBAL leak check on both touched Lua
files).

### Review Confidence

Full read — the whole plan (including U1–U8 and the amendment), explore-notes, implementation.md's
LV-1 section, debug-2026-11-23.md, review-lv0.md, the sortie feedback, the card, and the full diff
(`flight_control.lua`, `flight_profile.lua`, every touched test file in both subprojects, the
body-layer belief modules, the roadmap/CLAUDE.md docs). Ran `.claude/scripts/accepted-items-ledger.sh
plans/flight-lift-vector` and traced each flagged `U<n>` by hand against implementation.md's prose
(the script only checks for the literal string "U1" etc.; U2/U6 are correctly deferred to LV-3/LV-2
by name in the plan's own staging, not restated per-stage, and U1/U3/U4/U7 are substantively present
in the LV-1 prose without the literal tag). Re-ran every check directly in this worktree (symlinked
`.venv` from the main checkout for `aircraft-layer`/`body-layer`/`world-model`): `ruff format
--check`/`ruff check` clean for both subprojects, `mypy src` clean for both (29 and 93 files),
`.claude/scripts/fast-tests.sh aircraft-layer` (993 passed) and `fast-tests.sh body-layer` (2968
passed, 4 xfailed), `luac5.1 -p` on both touched Lua files, and the `luac5.1 -l -p` GETGLOBAL check
on `flight_control.lua`/`flight_profile.lua` (every global traced: Lua stdlib, genuine DCS APIs, or
`core.lua`'s own shared helpers — none is one of this file's own locals referenced before
declaration; `flight_profile.lua` reads no global at all).
