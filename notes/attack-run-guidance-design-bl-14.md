# Attack-run guidance design (BL-14)

- **A spoken number earns its place only when it names a reference the pilot already reads.**
  O'clock and kilometres survive because they point at something he can independently check out the
  window; "4 degrees right" does not, because it is a measurement he would have to convert first.
  This retroactively explains why the degree-based register (both azimuth-down and the periodic
  range countdown) was struck from `BL-14`'s guidance despite being the cheaper thing to compute —
  computability and usefulness are different properties (`docs/acceptance/
  2026-10-14-attack-run-guidance-direction.md` §§1, 9).
- **"Where is it on the map" and "where is it relative to me right now" are two different
  questions with two different error models, and conflating them injects an error nobody meant to
  model.** `BEARING_SIGMA_DEG` models the cost of *stating* a bearing in words, not anything DCS
  reports — its own docstring says so — and is the right model for an o'clock-and-km report, the
  wrong one for live alignment guidance while looking straight at the target (where most of the
  error is ownship's own, which cancels in a relative observation). `BL-14` had to introduce a
  second perception datum (`RelativeDirection`, `RELATIVE_DIRECTION_SIGMA_DEG`) rather than reuse
  the existing world-anchored belief, specifically because the reused model would have put a
  stating-precision error into a channel that needed none.
- **A stated invariant turns a defect into a violation, and the code should read that way.** "One
  thing only can be the target of an attack run" — because one azimuth/elevation solution cannot
  point at two places — is why a stale `attack_target` task silently surviving a re-selection
  mattered: the system briefly had two targets, which the invariant says cannot exist. The fix
  (cancel every active task, then promote) is the invariant's enforcement point, not just a bug
  patch, and is documented as such in `attack_target_task`'s own docstring.
- **Check a review brief's own premise, not only the mechanism it asks about.** A review brief
  stated `Percept` carries `derived_world_position` and now also `relative_direction`, implying a
  widened truth-adjacent surface. It doesn't: that field exists only on `Observation`, and `Percept`
  is deliberately stripped of every truth field. The premise came from the orchestrator's framing,
  not from the code, and would have gone unchecked if the reviewer had answered the question as
  asked instead of verifying what `Percept` actually carries first.
- **Look for an existing general mechanism before scoping a new constant for a request that sounds
  feature-specific.** A user request for "a 1s delay after the readback, before guidance speaks"
  turned out to be a 0.25s calibration delta on `callouts.py`'s pre-existing `INTER_UTTERANCE_GAP_S`
  (0.75s), which already gated every reply's trailing silence, attack-run or not. Treating it as a
  new attack-run-local constant would have duplicated ~80% of an existing mechanism and fragmented
  one scheduling concern across two modules.
- **An occupancy gate sitting between a public method and its pure decision core is exactly the
  place a staleness bug hides**, because calling the public method at the wrong simulated time can
  silently swallow the symptom. `drain_attack_run`'s "spoken state committed even when the channel
  was busy and nothing printed" bug was invisible when reproduced through `CrewConsole.
  drain_attack_run` at one particular `now_sim` (the busy-gate happened to suppress the print on
  that exact tick) and only surfaced when `belief.attack_run.decide` was called directly,
  bypassing the wrapper. When a wrapper and its pure core disagree about state, call the pure core
  directly to decide which one is lying.
- **A number cited from an earlier measurement needs checking against the current codebase, not
  just against the earlier report's own arithmetic.** A performance review's budget context reused
  `BL-11`'s `group_salient_ids`/worst-tick figures; the median had since improved 26× while the
  *maximum* (1,579 ms → 1,615 ms) had not moved at all — citing only the improved median would have
  misrepresented the actual tail risk a new per-press cost (`step`'s uncached `describe_contact`
  enrichment) was being measured against.
- **Verify the rendered artifact, not the source comment, whenever a generation step sits between
  an edit and the file a human actually reads.** A diff against source prose reviews intent, not
  effect. `X-T26`'s `config/defaults.toml` generator was wrong three separate times across three
  review passes — a second sentence that `_first_sentence()` never rendered, figures ~4x too high,
  and a backtick span eaten across a line wrap — and every one of the three was caught only by
  regenerating the file and reading its actual output, never by re-reading the `#:` source comment
  the fix had changed. This generalises past this one generator: any fix whose claimed effect is
  "this now appears in `<generated file>`" needs that file opened after the fix, not inferred from
  a correct-looking source diff.

- **A disjunctive suppression check can re-fire from its secondary clause even once a stricter
  primary clause already covers every real case — the secondary clause only needs to be
  satisfied, not to change the output.** `BL-B70`'s `_should_emit` compared rendered-text equality
  *or* an angular-delta threshold; the text comparison alone already caught every case worth
  catching, but the angular clause's own 3° threshold was finer than the vocabulary's own
  quantisation (10°/30°/7.5° word gates), so it kept firing on changes too small to change the
  words and re-spoke identical text 38% of the time in one sortie's own log. When a suppression
  rule is a disjunction, check whether every clause actually widens what gets through, or whether
  one of them is just a narrower false-positive generator layered on top of a sufficient check.
- **A fail-closed admission gate discards its own verdict, not just the rejected candidate.**
  `BL-B70`'s cause taxonomy wanted to distinguish "masked," "obstructed," and "too far" for an
  already-known contact, and the obvious place to read that from — the contact's own stored
  `live_los_clear` field — turns out structurally unable to ever hold `False`, because the gate
  that field feeds only lets a candidate survive admission when its look succeeded; a blocked look
  simply never updates the contact, so `False` is never written anywhere belief can read it later
  (filed as `BL-B76`). The gate itself is correct — it is not inventing sightings that didn't
  happen — but the per-tick reason for rejection is computed and then thrown away, leaving nothing
  for a later feature that wants to explain *why* the last update didn't arrive. Any fail-closed
  gate that drops a candidate silently is also dropping the one explanation a downstream feature
  might later need, and that gap only shows up when something tries to read it, not when the gate
  itself is reviewed.
- **Keying a state transition on resolvability, not on the proximate interruption, prevents a
  spurious re-announcement from an orthogonal interruption.** `BL-B70`'s losing-sight/regaining-
  sight register is deliberately keyed on `cause == "too_far"` rather than on tier or on having
  been masked, per direction: "the important question is whether Petrovich sees the target... not
  whether a break masked him in the meantime." A target that goes too-far → masked → too-far
  without ever resolving must not narrate a loss-and-regain pair at the masked step, because
  nothing about resolvability changed there. The general shape: when a register narrates a
  transition, name the condition as the thing that actually matters to the listener, not as
  whatever happened to be true on the tick before.

  **Correction, 2026-10-24 (`BL-B97`): `cause == "too_far"` was the wrong resolvability signal, not
  an instance of the general shape above.** A stale `"obstructed"` verdict ages out to `"unknown"`
  after `ATTACK_TARGET_LOS_MAX_AGE_S` (1.5s); `"unknown"` is not `"too_far"`, so the old register
  read that as "regained sight" and spoke "Eyes on" with no fresh look at all — exactly the sortie-
  reported bug. The register is now keyed on `tier != 1` (a genuine fresh naked-eye look) instead.
  The general principle still holds — key a transition on what the listener actually cares about —
  the earlier bullet simply misidentified which field *was* that condition. `cause` answers "why is
  there no look right now," `tier` answers "is there a look right now"; the register needs the
  second question, and conflating "resolvability" with "not currently too-far" is what let the bug
  through three review passes.
- **A transition's rendered text differing from the steady-state text for the same cause makes a
  text-equality suppression veto fire once more than it looks like it should.** `_should_emit`
  suppresses a repeat only when the new text equals the last spoken text; a losing/regaining-sight
  transition line (`"Behind the ridge, ..."` / `"Eyes on, ..."`) is deliberately worded differently
  from the ordinary steady-state qualified phrase for the same cause (`"..., obstructed."`), so the
  tick immediately after a transition still speaks once more before the suppression actually takes
  hold — not a bug, just a consequence of the veto being text-equality rather than cause-equality.
  Already present for the pre-existing `"too_far"` transition; worth knowing before reading a
  sortie's speech log and wondering why a transition produces two lines close together.
- **A docstring's "X and Y together is not reachable in practice, because Z" is a claim pinned to
  whatever makes Z true today, and a feature that changes Z can make the claim false the moment it
  ships — silently, because "unreachable" is exactly why nobody wrote a test for the combination.**
  `BL-B71`'s `attack_run.decide` asserted `tier == 1` with `cause == "too_far"` was unreachable
  because a fresh relative percept implies the naked eye already admitted it within its own
  presence range — true only while the admitting optic was fixed at `UNAIDED_OPTIC`. `BL-B71` is
  precisely the feature that stops that optic being fixed, and the function's own cause taxonomy
  kept testing range against the old fixed value, producing a "last I saw…" callout about a target
  being actively tracked through the granted optic. When a changed function's docstring (or one it
  reads from) asserts two states cannot co-occur, re-derive the claim against the diff rather than
  trusting it, especially when the diff touches a value the claim's "because" clause depends on.
- **A review's required fix can name a correct-sounding but narrower target than the defect it
  describes, and a fix that faithfully implements the named target can still miss the point.**
  `BL-B71`'s review named `OpticState.guidance_optic` (the ladder's own standing grant) as the fix
  for "the range gate must use the optic actually resolving the look." The two agree in the common
  case — hence passing the new tests — and diverge exactly where they matter: `guidance_optic` is
  `None` through ordinary glassing with no guidance grant standing, so the first fix round
  reintroduced the original bug in miniature for that case. Asked directly, the user's ruling was
  broader than the review's wording: "actual behavior must measure by used optic," which meant
  `runner.optic` — the value that actually admitted the tick's percept — not any one named field
  that usually tracks it. When a review names a specific field as *the* fix, treat the name as the
  reviewer's best guess at the requirement, not the requirement itself, and check whether the
  defect's own English description is broader than the named target.
- **A two-sided window's lower bound exists for a specific reason, and copying its shape into a
  new context that lacks that reason silently over-excludes.** `improvement_window_m`'s lower
  bound excludes a close target because the *naked eye* resolves the same tier "for free" on its
  next dwell, making a binocular look at it wasted — a competing-instrument argument.
  `9k113-narrow-search` needed the equivalent gate for an active sight look (`sight_can_still_
  improve`) and the natural-looking shape was to mirror that window, using `SIGHT_WIDE_OPTIC`'s
  own threshold as the new lower bound. That would have been wrong: while `SIGHTING`, nothing
  dwells in parallel to resolve a close contact for free — the sight *is* the active instrument —
  so there is no competing instrument to defer to, and the mirrored lower bound would have
  incorrectly excluded close, genuinely-worth-a-look targets. Caught by the review asking *why*
  the existing window's lower bound exists before reusing its shape, not by checking whether the
  new predicate "looked like" the old one.
- **`atgm_run.decide`'s own Stage 3-7 state machine (range calls, launch/impact speech, the
  "Shturm, N seconds." line) is not wired into `body.py`'s poll loop at all** — only Stage 1
  (constructing/tearing down `AtgmRunState` at engage/disengage) is live. The bearing-line
  depression search and "Tracking." callout (`fix/atgm-run-sight-tracking`, 2026-10-30) therefore
  could not reuse that module's `(state, speech, actions)` return shape and were implemented
  directly in the poll loop instead, via `CrewConsole.drain_sight_lock_tracking`. Not a conflict
  today, but a seam for whoever wires Stage 7: two independently-driven speech sources will then
  sit over the same run.
- **The generator's "first sentence" for a tunable's `defaults.toml` comment is actually the
  *last* `#:` paragraph before the assignment, not the first one in the block** —
  `generate_defaults.py`'s `_comment_block_above` walks upward and stops at a blank `#:` line. A
  comment written as two paragraphs separated by a blank line renders only the second one; the
  fix is one continuous paragraph with no blank-line break, not a wording change. A fourth
  instance of the standing "verify the rendered file, not the source comment" trap above, with its
  own distinct mechanism.
