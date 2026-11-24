# Review: BL-16 LV-1 pitch-sign revert (commit `2ff15f05`)

Reviewed in isolation against `plans/flight-lift-vector/debug-2026-11-24d.md`,
`plans/flight-lift-vector/debug-2026-11-24c.md` (superseded section), and
`docs/acceptance/2026-11-24-sortie-feedback.md` ("Third re-fly"). Branch
`feature/bl16-lift-vector-law`, commit `2ff15f054b8d8757b071669e185a15f6030e1e40`
(parent `0cc98d89`).

### Review Summary

The revert itself (`LAW_DIR.pitch` back to `1.0`) is well-supported by independent evidence that
is *not* the thing the commit message leans on: pitch-acceleration correlation with `a1100` across
multiple hand-flown sessions (+0.25..+0.64, consistent sign throughout) and a steady-trim argument
(higher cruise speed → lower `a1100`) agree with each other and point the same way. The mechanical
counterfactual is real — I reverted `LAW_DIR.pitch` to `-1.0` on a scratch copy of
`flight_control.lua` and `TestPitchLawDirection::test_pitch_below_theta_d_raises_the_written_command`
failed for exactly the stated reason (`-0.37225 ≯ -0.001 + 0.001`), then restored the file and
confirmed a clean tree. The rate-damping term (`u_pitch = t_p + k_theta*(theta_d - pitch) -
k_q*theta_rate`, `law_outputs`) is untouched by this commit and its sign is still correct against
`aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`'s own finding (`LoGetAngularVelocity`
z correlates +0.79..+0.97 with d(pitch)/dt, i.e. positive rate = nose rising; subtracting
`k_q*theta_rate` is negative feedback on rate regardless of `LAW_DIR`, since it operates purely in
the law/measured domain before the `LAW_DIR` mapping). `law_init_at_take`, `law_domain`, and the
trace-format comment are all consistent with "positive = nose up" post-revert; no code or comment
anywhere else in the Lua still asserts the old convention as live truth — the only remaining
"positive is stick forward/nose down" occurrences are in already-superseded sections of
`debug-2026-11-24c.md`, `review-pitch-1124.md`, `review-debug-1124c.md`, and the (now-corrected)
research doc's SUPERSEDED bullet, all explicitly history by the project's dated-correction
convention, none asserted as current.

Checks run clean: `ruff format --check`, `ruff check`, `mypy --strict src` (29 files), full
`pytest tests -q -m "not slow"` (1155 passed, matches the debug report's count), `luac5.1 -p` on
every `dcs-export/*.lua` and `Petrobrain/*.lua`.

One real problem, not in the code but in the evidentiary claim the fix rests its narrative on.

### Required Fixes

- **"User confirmed the nose went down" overstates what the cited acceptance-doc section says —
  correct it everywhere it appears** (commit message; `debug-2026-11-24d.md` lines 10-11;
  `debug-2026-11-24c.md`'s SUPERSEDED addendum, "a nose-down push-over, confirmed by the user").
  `docs/acceptance/2026-11-24-sortie-feedback.md`, "Third re-fly", quotes the user directly on this
  exact question ("did the stick go back or forward?"):

  > I think the pitch angle axis is flipped in our code.
  > On take Petrovich pulled the cyclic full back -> significant nose up.

  That is the *opposite* of nose-down — the user's own account is full aft stick, nose up. The
  "nose went down" conclusion is the **main loop's** telemetry read (ADI pitch, load factor,
  vertical speed, ground speed all read as a push-over), explicitly argued *against* the user's
  stated impression, not confirmed by it. The section's own last paragraph calls this **"Open"**
  and names two decisive, cheap checks that were not yet run: "the track replay in external view,
  and a ground check of which way `a1100` moves when the player pushes the stick forward." Neither
  check appears in `debug-2026-11-24d.md`'s evidence or verification sections — the revert instead
  rests entirely on cross-session correlation and a trim argument, which is reasonable supporting
  evidence but is not the same thing as resolving the acceptance doc's own named open question, and
  is not something the user confirmed. Only the loss-of-control event itself was confirmed by the
  user ("Fail on the cyclic logic - complete loss of control," same section) — not its direction.
  Fix: reword the three occurrences to attribute the nose-down reading to telemetry/correlation
  analysis, not the user, and state plainly that the acceptance doc's own decisive checks are still
  outstanding. This is a documentation-accuracy fix, not a code change, and does not by itself cast
  doubt on the correlation evidence — but shipping a flight-control sign reversal (on an axis that
  already caused one in-sim tumble) under a provenance claim stronger than what was actually
  established is exactly the kind of thing this project's dated-evidence discipline exists to catch.
  **Flag this explicitly in the next test card**: the pilot should watch stick/nose direction on
  take and say which way it goes, so the open question gets its decisive answer from the flight
  itself rather than from a correlation argument alone.

### Optional Refinements

- None beyond the above — the code change, test change, and dated-supersession handling in the
  research doc and `debug-2026-11-24c.md` are all correctly done (supersession marked, not
  deleted; comment pruning in `flight_control.lua` replaces stale text with corrected text rather
  than losing the citation trail).

### Verdict

APPROVED WITH MINOR FIXES — the code/test change is sound and independently verified by mutation;
the required fix is a documentation-accuracy correction (and a note for the next test card), not a
rework of the sign logic itself.

### Review Confidence

Full read of the diff, both debug reports, the cited acceptance-doc section in full, and the
research doc's relevant bullets. Ran the full aircraft-layer check suite (ruff format/check, mypy
--strict, full pytest, luac5.1) myself rather than trusting the debug report's own numbers, and
independently reproduced the counterfactual test failure by mutation.
