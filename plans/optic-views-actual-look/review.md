### Review Summary

Bug fix on `fix/optic-views-actual-look` (tip `1b0d5de5f0b7d6290122fe814d29492b96871675`,
base `3de03e6db95197c0af92043b1360b52daa1fbcab`). Fixes the defect reported in
`docs/acceptance/2026-10-26-sortie-feedback.md`: `--eyesight-view` and `--pov-view` disagreed on
where Petrovich was actually looking, because `--eyesight-view` (and `--pov-view`'s non-sight
branch) read `runner.scan_plan` directly — the *commanded* plan — which `_apply_active_gaze`
never writes a fixed look (sight aim, or a binocular glass phase) back onto.

The fix introduces one shared `_resolve_active_gaze(runner) -> Gaze` in `body-layer/src/body.py`,
read by both `_render_eyesight_frame` and `_render_pov_frame`, with three cases: sight tier reads
`SightHead.world_az_true_deg`/`world_el_deg` directly (converted to heading-relative azimuth); a
fixed look on any other optic (binoculars) reads `OpticState.actual_aim_azimuth_deg`/
`actual_aim_elevation_deg`; otherwise (free-scanning) it falls back to `gaze_at(runner.scan_plan)`,
unchanged from before.

**Verified by mutation, not just by reading the diff:**

- Replayed the base (`3de03e6d`) source with the tip's test file via `git archive` into a scratch
  tree (the worktree held the branch I couldn't check out directly, per the dispatch note) — all
  six new tests fail at collection against base (`ImportError: cannot import name
  '_resolve_active_gaze'` / `_render_eyesight_frame` not previously module-level-exported for
  import), confirming debug.md's "fails on base" claim rather than trusting the stated claim.
  Against the tip, all six pass in isolation and as part of the full suite.
- Traced every `OpticDecision(optic=BINOCULAR_OPTIC, ...)` construction site in
  `belief/optic_policy.py` (5 sites) by hand: all five always pair `BINOCULAR_OPTIC` with
  `look_azimuth_deg`/`look_elevation_deg` set, which is what makes `_apply_active_gaze`'s
  `actual_aim_*` assignment — and therefore `_resolve_active_gaze`'s binoculars branch — reliable;
  there is no binoculars-with-`actual_aim_*`-still-`None` gap.
- Confirmed the sight-tier `assert`s in `_resolve_active_gaze` inherit the same guarantee the old
  `_render_pov_frame` relied on (`run_once`'s own cap: `optic_decision.optic in (SIGHT_WIDE_OPTIC,
  SIGHT_NARROW_OPTIC) and not head_will_be_free` forces a fallback *before* `runner.optic` is ever
  set to a sight optic without `sight_head.mode == "free"`) — both debug-view calls read the same
  `runner` object, populated by the same poll's `run_once`, so the invariant that protected
  `_render_pov_frame` alone now protects the shared function identically for `_render_eyesight_frame`
  too.
- Confirmed `look <o'clock>`/`look <compass>` (`BoundedSightLook`) is exclusively a sight-tier
  mechanism (`_advance_bounded_look` only ever drives `search_pattern_steps` under
  `OpticPhase.SIGHTING`/`SIGHT_WIDE_OPTIC`) — there is no naked-eye-tier bounded look that would
  fall through a gap between the sight branch and the free-scan fallback.
- Confirmed the attack-run path reaches the sight tier through the ordinary `requested_optic`/
  guidance-request route (`body.py` ~L797-837), not a parallel mechanism that could set `runner.optic`
  to a sight optic outside the cap above.
- Grepped `body.py` for any change to `_speech_log_sink` — none; the stated out-of-scope item
  (same latent `runner.scan_plan` read, left for later) is genuinely untouched.

**The debugger's design call — not writing the resolved plan back onto `runner.scan_plan`, and
instead giving both views a shared resolver function — holds up.** Writing back would have fixed
the binoculars case but corrupted the sight case: `_apply_active_gaze`'s sight-tier override uses
the sight head's *body*-relative direction (pitch/bank included), which is the wrong frame for
these canvases (`plans/pov-view/plan.md`'s Design section requires heading-relative azimuth,
horizon-relative elevation, so a ground target stays visually still as the airframe pitches/rolls).
A shared function reading the same per-optic inputs `_apply_active_gaze` itself reads — rather than
its single, frame-mismatched output field — is the correct fix, not an overbuild: it is exactly as
much abstraction as removing the duplicate per-optic table from `_render_pov_frame` and folding it
into one place needs.

**Comment pruning:** `_render_pov_frame`'s old "Boresight resolution is per-optic" docstring
paragraph (the per-optic table and the `run_once`-cap reasoning) was deleted and is not duplicated
verbatim — but checked against the pruning rule's actual test (durable line / `#:` block / boundary
case moved to a test, in that order): it is ordinary design-rationale prose, not a dated line, user
quote, or measurement, and the substance is re-stated (not lost) in `_resolve_active_gaze`'s own
new docstring, which is the function that now owns that logic. Legitimate "the code says it itself
now" pruning, not a loss.

### Required Fixes

None.

### Optional Refinements

- `_resolve_active_gaze`'s free-scan fallback branch (`actual_aim_* is None`) is reached whenever
  `runner.optic` is `UNAIDED_OPTIC` *and* whenever a non-sight, non-fixed-look optic exists in the
  future with no `actual_aim_*` convention — today that set is exactly `{UNAIDED_OPTIC}` by
  construction (every `BINOCULAR_OPTIC` decision site sets `look_azimuth_deg`, verified above), but
  that is an invariant enforced only by convention across five call sites in `optic_policy.py`, not
  by a type or an assertion in `_resolve_active_gaze` itself. Not a defect — nothing in this diff
  weakens it — but worth a one-line comment or a narrow assertion the next time `optic_policy.py` is
  touched, so a sixth `BINOCULAR_OPTIC` construction that forgets `look_azimuth_deg` fails loudly in
  `_resolve_active_gaze` (wrong gaze width, label still correct) rather than silently falling back to
  the naked-eye scan cone's `half_width_deg` for a binocular view. (Optional — this is the same class
  of coupling the tuning-pattern checklist calls out for cross-key invariants, applied here to a
  cross-call-site one.)

### Verdict
APPROVED

### Review Confidence
Full read — diff is small (one new function, two call-site swaps, one deleted per-optic table, six
new tests), and every optic case named in the dispatch (naked-eye scan, bounded `look <o'clock>`,
binoculars, sight_wide/sight_narrow, and the attack-run path to the sight) was traced to a specific
code path and either a passing test or a hand-checked invariant, not just read for plausibility.
