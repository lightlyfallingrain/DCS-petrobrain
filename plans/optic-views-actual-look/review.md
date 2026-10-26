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

---

## Follow-on review: `fix/optic-views-actual-look` delta `9031125e..8091730e`

Tip `8091730e024a6ef076dec43d7ac1ac536a12ede3`. Reviews the one commit "Fix: `_speech_log_sink`
also reads the resolved gaze, not stale `scan_plan`" — the `_speech_log_sink` closure in
`body-layer/src/body.py` (`sink`, called from `CrewConsole.speech_log_sink`) still computed
`gaze = gaze_at(now_sim, runner.scan_plan)` for the belief-truth log's `kind: "speech"` rows
(`gaze_label`/`gaze_center_deg`) after the earlier fix above (`1b0d5de5`) switched the two debug
views to the shared `_resolve_active_gaze(runner)` resolver — this closes the one remaining
reporting site left out of that fix's stated scope (noted explicitly in the prior commit's debug
notes and confirmed untouched by this review's own grep above).

### Verified by mutation, not just by reading the diff

- Reverted `src/body.py`'s one changed line (`gaze = _resolve_active_gaze(runner)` →
  `gaze = gaze_at(now_sim, runner.scan_plan)`) in place and re-ran the two new tests
  (`test_speech_log_sink_sight_tier_uses_sight_head_not_stale_scan_plan`,
  `test_speech_log_sink_binocular_fixed_look_uses_actual_aim_not_stale_scan_plan`): both fail
  against the reverted line — `AssertionError: assert '1_oclock' == 'sight_wide'` and the
  binocular case fails the same way (`'1_oclock' == 'binocular'`) — confirming debug.md's "both
  confirmed to fail against the pre-fix line" claim rather than trusting the stated claim.
  Restored the file byte-for-byte (`git status --porcelain` clean after) and reran: both pass.
- **Checked whether a second `_speech_log_sink` or any other reporting reader of
  `runner.scan_plan`/`gaze_at(` survived the fix.** The commit message and debug.md addendum both
  claim this was the only remaining reporting site, grepped against `src`. Re-ran that grep myself
  (`grep -n "gaze_at(\|\.scan_plan\b" src/body.py src/perception/*.py`) and read every hit in
  context: `body.py:683` (`gaze_for_look_direction = gaze_at(...)`) drives the Lua look-direction
  push (`post_look_direction`), never reports to a person; `_resolve_active_gaze`'s own fallback
  line (`body.py:1814`) is the resolver itself, not a second caller; `naked_eye_source.py:776` is
  internal to the naked-eye source's own perception gating. No second `_speech_log_sink` exists —
  the knowledge graph's node for one at `logger.py:1301` is stale (that module was since renamed/
  merged into `body.py`; confirmed `logger.py` does not exist in this tree and `grep -rn
  "_speech_log_sink" src/` finds exactly one definition, in `body.py`). The claim holds.
- **Checked every reader of `gaze_label`/`gaze_center_deg` for an assumption about label format or
  a numeric range** (o'clock-shaped string, heading-relative bearing bucket): grepped the whole
  repo (`grep -rn "gaze_label\|gaze_center_deg"`, `.venv` excluded). `belief_truth_log.py` treats
  both as opaque `str | None`/`float | None` with the existing absent-not-null convention — no
  format assumption. `tests/test_belief_truth_log.py` only exercises the field's pass-through, not
  its value shape. `body-layer/tools/join_voice_latency.py` and every file under
  `.claude/skills/sortie-log-triage/` have zero hits on either name — neither reads the field at
  all, so neither can be broken by `gaze_label` now reading an optic name (`"sight_wide"`,
  `"binocular"`) instead of an o'clock label while on a fixed look. The only places that quote an
  o'clock-shaped `gaze_label` value are historical diagnosis/debug prose
  (`plans/sortie-2026-09-26-fixes/diagnosis.md`, `plans/log-attitude-with-speech/
  implementation.md`, two debugger agent-memory files) describing *past* log samples, not code
  that branches on the shape — the debug.md claim ("no reader... branches on that value") is
  correct as stated.
- **Checked the comment this commit stands next to.** `_speech_log_sink`'s docstring gained one
  new paragraph pointing at `_resolve_active_gaze` and the sortie-feedback quote (durable —
  dated, verbatim user quote, correctly attributed) and nothing was deleted from the existing
  docstring; `debug.md`'s prior "No change to ... the speech-log sink ... out of this fix's stated
  scope, left as-is" sentence was edited in place to read "(at the time) the speech-log sink ...
  **had** the same latent defect" — supersession marked in the text itself, not silently deleted,
  matching `docs/PROCESS.md`'s convention. No `#:` tuning block touched (no new constants), no
  boundary case silently dropped from a comment with no replacement test — the opposite: two new
  regression tests mirror the two existing debug-view ones.
- Confirmed no new behaviour-affecting constant was introduced (none — this is a pure call-site
  swap) and no new voice vocabulary (none).

### Scope

Matches the delta's own stated scope exactly: one call-site swap in `_speech_log_sink`, a
docstring addition, two tests, one debug.md addendum. No drift, no unrelated changes.

### Required Fixes

None.

### Optional Refinements

None beyond the one already on record above (the `optic_policy.py` five-construction-site
convention) — unaffected by this delta, which adds a third *reader* of the existing
`_resolve_active_gaze` resolver rather than a new write path into `OpticState`/`runner.optic`.

### Verdict
APPROVED

### Review Confidence
Full read, with mutation. Reverted the one-line fix in place, confirmed both new tests go red,
restored byte-for-byte and confirmed green; re-ran the "only remaining reporting site" and
"no reader assumes label format" claims as independent greps rather than trusting the commit
message and debug.md's stated conclusions. `ruff format --check`, `ruff check`, `mypy --strict`,
and the full `pytest` suite (2694 passed, 4 xfailed) all clean from `body-layer/` using the main
checkout's `.venv`.
