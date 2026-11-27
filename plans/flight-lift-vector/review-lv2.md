# Review — BL-16 LV-2 (breaks), commit d6c444d5

Reviewed on branch `lv2-review` (created at `d6c444d53b1276b1c3b326c3d940ffeab8851348`, this
worktree's starting point `c0d8af86` was not an ancestor of that tip, so per the dispatch
instructions a fresh branch was checked out from the same object store rather than a worktree
switch). Full read: `plan.md` "LV-2 amendment" section in full, `explore-notes.md`'s LV-2 section,
`alignment.md`'s LV-2 plan check, `implementation-lv2.md`, the acceptance card, and the full diff
(`flight_control.lua`, `flight_profile.lua`, the three new test classes). Checks run independently
(not taken on the implementer's word): `ruff format --check`, `ruff check`, `mypy --strict src`
and `tests`, full `pytest aircraft-layer/tests` (1198 passed locally — see note below), plus three
hand-run mutations (bank-cap `min()`, section-C `if` guard, floor swap) against the new test
classes, each confirmed red for the stated reason and the file restored clean afterward.

## Required Fixes

**1. The break does not fly "more aggressive[ly] than normal turn" the way the plan, the shipped
`flight_profile.lua` comment, and the acceptance card all claim — the real closed-loop law is
dominated by the pre-existing `omega_heading` (0.3) heading shaper, and this amendment's new
bank/rate cap is almost inert for the step sizes a break actually commands. Required: correct the
documentation (comment, plan text, card) to the real numbers below, and raise with the user/
Architect whether a break-specific shaper bandwidth is needed to deliver what was actually asked for.**

This is not a test-harness artifact — it is the deployed law. A break (`axes_break_turn` →
`FlightControlGoalRequest(heading_deg, turn_rate_deg_s)`) sets `heading_goal_deg` and
`rate_override_deg_s`, with `turn_mode = false` and `bank_hold_deg = nil` (`law_apply_goal`,
lines ~588–608) — which routes it into `law_update`'s `else` branch (line 898 on), the **same**
second-order shaper ordinary "fly to heading" mode uses:

```
a_ref = omega_heading^2 * err  −  2*zeta*omega_heading*r_ref
r_ref += clamp(a_ref, ±accel_limit) * dt,  clamped to ±rate_limit
```

`rate_limit`/`accel_limit` differ between break and ordinary mode (this amendment's own
`break_max_bank_deg`-derived ceiling vs the ordinary `max_turn_bank_deg=20°`-derived one), but the
`a_ref` formula itself is identical and is what actually governs `r_ref`'s approach to a 90° error.
For a critically-damped (`zeta=1`) step of `err=90°`, the natural peak rate is `err·omega·e⁻¹ ≈
9.93°/s`, reached at `t=1/omega≈3.3 s`, **independent of speed and independent of either ceiling**
once that ceiling exceeds ~10°/s (which `break_max_bank_deg=60°` does at all three card speeds — the
bank needed for a 60° cap to bind is ~67–79°, while the natural peak only ever asks for ~30–51° of
bank). I confirmed this numerically (discrete simulation at `dt=1/30`, matching `law_hz`) and by
mutation (removing the new `min()` and re-running `TestLV2BreakBankRateCap` fails as expected only
because the test *seeds* `r_ref` directly — it does not and cannot exercise this through the real
heading error, exactly as the implementer's own test docstring and `implementation-lv2.md`'s
"Notable Discoveries" already say). This matches `TestBreakTurnChannel`'s own pre-existing (already
merged, out of scope) docstring almost verbatim — so the finding itself is not new, but its
consequence for *this* amendment's claimed numbers was never re-checked before they were written
into three places:

| speed | plan/comment/card claim | real law (discrete sim, `err=90°`) |
|---|---|---|
| 120 km/h | steady ~32°/s, 90° in ~2.8 s | peak **~9.95°/s**, ~13.0 s to 90% of the turn |
| 180 km/h | steady ~21°/s, 90° in ~4.3 s | peak **~9.95°/s**, ~13.0 s to 90% of the turn |
| 250 km/h | steady ~15°/s, 90° in ~6.0 s | peak **~9.95°/s**, ~13.0 s to 90% of the turn |

For comparison, an **ordinary** 90° heading change (unchanged by this amendment, `max_turn_bank_deg
=20°`) is itself ceiling-bound (not shaper-bound) at these speeds: peak rate ~6.1/4.1/2.9°/s, ~16.6/
22.1/29.1 s to 90%. So the break genuinely *is* faster than an ordinary turn — by ~22% at 120 km/h
widening to ~55% at 250 km/h — but almost entirely because the ordinary turn's low bank ceiling gets
worse at speed, not because the break is "aggressive": its own peak rate is flat at ~9.95°/s
regardless of speed, and the bank it actually flies to reach that (from `r_ref`, before any
`phi_i`-integrator margin — a pre-existing, separately-flagged, deliberately-unaddressed risk) is
only ~30°/41°/51° at 120/180/250 km/h, not the ~60° the cap allows and not the "momentary ~2 G" the
user asked for (`n=1/cos(bank)` at those banks is ~1.16/1.33/1.59 G, not ~2.0 G). The
`break_max_bank_deg=60°` cap this amendment built is correctly implemented and correctly tested in
isolation (seeded-`r_ref` tests, honestly documented as isolating the clamp from "this unrelated,
pre-existing shaper slowness") — but as shipped, nothing in the real flight ever drives `r_ref` far
enough to reach it for a plain 90°/180° break command, so section B delivers close to no behavioural
change over the pre-amendment 40°/s-uncapped-rate law for the speeds and headings this card tests.

**This also means `alignment.md`'s own LV-2 Finding 1 — the one that drove the 65°→60° correction —
rests on the same unverified premise** ("the cap binds at all three card speeds… the break flies at
the full cap… for 2.5–5.2 s"). The correction to 60° (exact 2 G) is harmless and matches the user's
figure, but neither 65° nor 60° is actually reached by `r_ref` in the real law at these speeds, so
the alignment's "E18 — contradicted in part" framing and its "met" verdicts for E5/E17/E18 should be
revisited once the real numbers are known, not left resting on the plan's own (now-shown-wrong)
"Effect, by speed" arithmetic.

**Why this must be fixed, not just noted**: the acceptance card (line 25–28) tells the user to
expect "steep bank reached promptly" at a "steady rate at the cap: ~32/21/15°/s, 90° in ~2.8/4.3/
6.0 s." Flying it against that expectation and getting ~10°/s/~13 s instead reads as a regression
or a broken cap, when it is actually the pre-existing `omega_heading` gain doing what it has always
done — a wasted flight cycle at best, a false "it's broken" report at worst. Minimum required fix:
correct the `flight_profile.lua` comment, the plan's "Effect, by speed" paragraph, and the card's
expectation line to the real numbers (or to a qualitative "faster than an ordinary turn at the same
speed, especially at higher speed, but not dramatically steep" framing) before this card is flown.
Recommend also raising with the user/Architect whether a break-specific heading-shaper gain (a
`break_omega_heading`, analogous to this amendment's own break-specific bank/rate cap) is needed to
actually deliver "faster turn rate, more aggressive manoeuvre… than normal turn," since as shipped
the cap this amendment built has (almost) nothing to cap.

## Everything else checked — no issues found

- **Section C (height-gives-first)**: acts only in break class (`state.rate_override_deg_s ~=
  nil and break_floor ~= nil`); both the 100 m loss budget and the 50 m AGL floor hold together via
  the unchanged `max()` shape; the fraction ramps continuously from 1→0 across `break_height_give_
  band_m`, so behaviour returns smoothly to the ordinary chain near the floor (no discontinuity) —
  confirmed by reading and by mutation (`if false and …` guard → both `TestLV2HeightGivesFirst`
  tests go red for the stated reason). Ordinary (non-break) flight is bit-for-bit unchanged by
  construction (`effective_shortfall` only ever diverges from `shortfall` inside the break-class
  `if`) and the full LV-1 regression suite (unmodified) still passes.
- **`break_floor_agl_m` is break-only (U11)**: `limits.floor_agl_m` (40.0) is untouched at every
  other read site, including the unpark seed clamp (`flight_control.lua:2670-2671`) — grepped for
  every occurrence, not just the one site named in the plan. Confirmed by mutation (reverting the
  break-floor clamp's constant to `limits.floor_agl_m` fails `TestLV2BreakFloorIsBreakOnly` exactly
  as the test's own comment predicts).
- **Non-positive-band guard / finite-float rule**: `break_height_give_band_m ≤ 0` degrades to
  `height_available_frac = 0.0` (no height-giving, the pre-amendment behaviour) rather than
  `shortfall / 0` (NaN/±Inf) — correctly guarded, matching `law_turn_rate_at_bank`'s own
  near-zero-input convention. The three new constants are hardcoded Lua table literals (never
  wire-received, confirmed by reading `FC_LIMIT_BOUNDS` and the wire-receive path in full, per the
  plan's own note), so the standing rule's literal `math.isfinite()`-at-parse form has no parse
  boundary to attach to here — the division-safety guard is the right-shaped substitute and is
  honestly described as such in the comment, not silently skipped.
- **Tests**: on shipped `flight_profile.lua` values via `dofile` (not retyped), as the project's
  own standing convention requires. I independently re-ran all three described counterfactuals
  (bank-cap `min()`, section-C `if` guard, floor constant swap) and got the same failures the
  implementer reports, for the same reasons — not tautological, each asserts a value against the
  shipped law's own derived constant (`law_turn_rate_at_bank`) or a cross-scenario comparison, not
  a hardcoded magic number restated from the implementation.
- **Scope**: diff touches only `flight_profile.lua`, `flight_control.lua` (sections B/C/D only —
  confirmed no other `law_*` function touched), the test file, the card, and
  `implementation-lv2.md` — matches the plan's stated scope exactly, no drift.
- **Checks**: `ruff format --check`, `ruff check`, `mypy --strict src` and the test file, all pass,
  independently re-run. `luac5.1` was not available in this environment to re-run the Lua syntax
  check; the implementer's own report states it passed and the Lua diff is small and mechanical
  (two `local`-scoped edits, no new top-level function), so this is a spot-check gap, not a finding.
- **Minor, non-blocking**: the full suite showed **1198 passed** here vs. the implementation
  note's **1190** — almost certainly an environment/collection difference (nothing failed or was
  skipped either run), not a discrepancy in the diff itself; worth a one-line sanity check at DoD if
  the gap recurs on other branches, but not a required fix.

## Optional Refinements

- The plan's own "Effect, by speed" paragraph and the card's numeric claims should probably also
  gain a one-line pointer to `TestBreakTurnChannel`'s pre-existing docstring (already in the repo)
  so the next amendment to this law does not have to re-derive the same finding a third time.
  (optional — the required fix above covers the correctness; this is about not losing the thread.)
- If a break-specific shaper bandwidth is built later, the new `break_max_bank_deg`/`break_height_
  give_band_m` constants and the diagnostic `dbg_shortfall`/`dbg_effective_shortfall` fields built
  this pass should still be reusable as-is — worth saying so explicitly in whichever plan does that
  work, so it doesn't look like a prerequisite for it. (optional)

## Verdict

**NEEDS REVISION** — required fix above (documentation of the realized break-turn behaviour, and a
design question for the user/Architect on whether a break-specific shaper gain is needed) must be
addressed before this card is flown; Section C/D and the floor/guard work are solid and need no
changes.

## Review Confidence

Full read of the diff, the plan, the alignment check, the implementation note and the card. Checks
and three mutations re-run independently (not taken on report). The one gap: `luac5.1` was not
available in this environment, so the Lua syntax check itself was not independently re-run (spot
reliance on the implementer's report for that one check only).

---

## Re-review — LV-2 fix pass, commit `15451bcd`

Base: `15451bcd7fdfb1870099856c37cd3c191702567d` on `fix/bl16-flight-epoch-bound` (branch `lv2-fix`
in the implementer's own account). This worktree's starting point (`f9864b45`, a different,
unrelated feature) was not an ancestor, and the branch the task named is checked out elsewhere
(`/Users/sg/Code/DCS-petrobrain-epochfix`, not touched); per the dispatch instructions a fresh
branch `lv2-rereview` was checked out from the same object store at the named sha. Full read:
`git show 15451bcd` in full (`flight_control.lua`, `flight_profile.lua`, the test file, the card,
`plan.md`'s new "LV-2 fix pass" section, `implementation-lv2.md`'s fix-pass addendum, the new
implementer agent-memory file). Checks run independently: `ruff format --check`, `ruff check`,
`mypy --strict src` and the touched test file, `luac5.1 -p` on every deployed `.lua` file
(available in this environment, unlike the prior pass — passes clean, closing that spot-check
gap), full `pytest aircraft-layer/tests` (1211 passed). One mutation re-run independently (not
taken on the implementer's word): commented out the `omega_heading = profile.break_omega_heading`
line in `flight_control.lua` (reverting to the pre-fix, always-ordinary-shaper behaviour) and
re-ran the touched test file — 12 of the targeted tests went red for the stated reason (every
`TestLV2BreakShaperBandwidth` test but the ordinary-case regression, plus the renamed
`TestLV2BreakBankRateCap` test), file restored and confirmed clean (`git diff` empty). Also
independently re-derived, from first principles, the two numeric claims the fix pass's reasoning
depends on: (1) a bare Python simulation of the idealized critically-damped shaper confirms the
peak-rate formula `err·ω/e` at both `ω=0.3` (~9.95°/s, matching the original review) and `ω=1.0`
(~33.1°/s, matching the fix pass's own figure); (2) `law_turn_rate_at_bank(60°, v)` at 120/180/250
km/h gives 29.21/19.47/14.02°/s, matching the plan's/comment's "~29.2/19.5/14.0" cap figures
exactly.

### (1) Break now faster than ordinary, cap binds — through the real heading error, not seeded

Confirmed. The fix adds exactly one mechanism (`break_omega_heading`, read only inside the
existing `state.rate_override_deg_s ~= nil` branch, `flight_control.lua:912-940`) and the new
`TestLV2BreakShaperBandwidth` class exercises it through the full closed-loop toy plant (bank lag
included), not a seeded `r_ref` — the exact gap the original required fix named. The mutation
above shows these tests are not decorative: removing the one line that reads `break_omega_heading`
turns 11 of 13 new-class tests red for the right reason (cap-binds, faster-than-ordinary, and both
no-sustained-oscillation checks all fail; the two that stay green — the pinned ordinary-case
regression and one 180°-break-away overshoot-bound at the far end — do so because a reverted
shaper still produces *some* overshoot-free, if far slower, motion, which is the right thing for
them to still pass on). The claimed cap-derived rates (29.2/19.5/14.0°/s) and the claimed natural
peak rate at the new bandwidth (~33.1°/s, which is why the cap now binds rather than being inert)
both check out independently, above. The documentation correction is real too, not just a comment
edit — `plan.md`'s "Effect, by speed" table, the `flight_profile.lua` comment and the card's
expectation line now all state the same measured numbers (peak bank ~56/63/64° and ~5.4/6.2/7.3 s
to 90% of the turn at 120/180/250 km/h), cross-checked consistent across all three documents.

### (2) Ordinary heading flight bit-identical

Confirmed. The `else` branch (ordinary, non-break heading) is untouched by the diff — the only
change inside `law_update`'s heading-rate step is the new `local omega_heading` selection, which
reads `profile.omega_heading` (unchanged value, 0.3) whenever `state.rate_override_deg_s == nil`.
`TestLV2BreakShaperBandwidth::test_ordinary_heading_change_is_bit_identical_to_before_this_fix_pass`
pins the exact closed-loop numbers for a 120 km/h ordinary 90° turn, and the full pre-existing
regression suite (1211 tests, unmodified elsewhere) stays green. No new global, no cross-frame
state — `omega_heading` is a fresh per-call `local`, not persisted on `state`.

### (3) The ~5–10° roll-out overshoot — plant-lag artefact, acceptable as a first cut

This is the one place a second reviewer could reasonably disagree, so stating the reasoning fully
rather than deferring to the implementer's framing. The claim is that the overshoot belongs to the
toy plant's first-order bank lag on `phi_d`, not to the shaper's own reference trajectory
(`r_ref`/`psi_ref`), which stays critically damped (`zeta=1`, unchanged) at any bandwidth. Checked
by reading `_LV2_CLOSED_LOOP_DRIVER`: the lag is modelled exactly where the implementer says it is
(`measured.bank_deg = measured.bank_deg + (state.phi_d - measured.bank_deg) * (dt/tau)`,
`tau = 1.0`, the same shape `_BREAK_PLANT_DRIVER`/`_HEADING_PLANT_DRIVER` already use elsewhere in
this file) — a real, physically-motivated artifact (the aircraft's own bank cannot reverse
instantly once the shaper starts decelerating toward the target), not a shortcut invented to excuse
a defect. The claim that the idealized shaper alone shows zero overshoot at any bandwidth is
consistent with standard 2nd-order critically-damped step response theory (no complex poles, so no
ringing by construction) and is independently plausible, not just asserted. The residual itself is
bounded (≤2 zero-crossings, asserted and mutation-tested) and single-shot, not growing or
divergent, and it is the SAME mechanism the original review's own table implicitly already carried
(any shaper fast enough to reach a bank cap will show some plant lag on roll-out) — this fix pass
is the first point that mechanism became visible because, before it, the break never flew fast
enough to expose it. **Judgment: acceptable to fly as a first cut with the card watching it, not a
required fix.** It is disclosed in three places (the `flight_profile.lua` comment, the plan's own
fix-pass section, and the card's watch line), bounded by a test, and named on the card's own
acceptance item as something the user should flag if it reads as *more* than one clean correction —
which is the right bar for a first-cut tunable (`break_omega_heading`) that the project's own
"behaviour-affecting constants are tunable" convention already treats as something to retune from
a live sortie, not something to perfect in the toy plant before ever flying it. If a future stage
wants to tighten it, the implementer's own memory file and plan section already name the fix
(a lookahead/anticipation term) rather than leaving it a mystery.

### (4) Pitch stays calm — height-gives-first still holds

Confirmed by inspection and by scope: this commit touches only `law_update`'s heading-rate step
(`flight_control.lua` section B's `if`/`else`, 20 changed lines) and `flight_profile.lua` comments
plus the one new constant. Section C (height-gives-first, `effective_shortfall`) is untouched —
confirmed by `git show --stat` (no other hunk in `flight_control.lua`) and by reading the
surrounding lines in the post-fix file, which show the pitch/altitude channel below the heading
step is reached only after `r_d` is computed, with no new read of `break_omega_heading` or the
local `omega_heading` anywhere in it. The faster roll-in does not feed back into the altitude
shaper by construction — they are separate channels (heading-rate vs. altitude/pitch), and nothing
in this diff couples them.

### (5) Tests mutation-sound

Confirmed, independently (not taken on the implementer's own counterfactual report) — see the
mutation above. The renamed `TestLV2BreakBankRateCap` assertion
(`test_cap_does_not_bind_below_88_kmh_leaving_the_rate_free_to_move`) was also checked for being a
real property rather than a restated magic number: its exact-value assertion
(`abs(r_after - 38.7) < 1e-6`) is derived from the unclamped `a_ref` formula at the new bandwidth
(`38 + (90 - 2*38) * 0.05`), not a number copied from a single run, and the comment shows the
derivation.

### (6) Card expectations match the numbers

Confirmed. The card's peak-bank/90%-time figures, the "~5–6°"/"~7–10°" overshoot ranges, and the
branch/deploy instructions (`lv2-impl`/`lv2-fix`/`fix/bl16-flight-epoch-bound`, harvested onto
`feature/bl16-lift-vector-law`) all cross-check against `plan.md`'s table and
`implementation-lv2.md`'s own numbers, with no drift between the three documents.

### Everything else checked — no new issues

- **Cross-key coupling** (`break_omega_heading` vs. `t_roll`/`break_max_bank_deg`): named and
  reasoned about in `implementation-lv2.md`, not guarded in code, consistent with the rest of this
  table's own (unguarded) convention — correctly disclosed rather than silently skipped.
- **Tuning mechanism**: `break_omega_heading` is a Lua-literal `flight_profile.lua` field, never
  wire-received, same posture the original review already accepted for its three LV-2 siblings —
  outside body-layer, this is the right-shaped substitute for the `tuning.py` mechanism, not a
  departure from it.
- **Scope**: diff touches only `flight_control.lua` (the one `if`/`else` branch), `flight_profile.
  lua` (one new field plus comments), the test file, the card, the plan, the implementation note,
  and one new agent-memory file — matches the required fix's scope exactly, no drift.
- **Checks**: `ruff format --check`, `ruff check`, `mypy --strict src` and the touched test file,
  `luac5.1 -p` on every deployed `.lua` file (now available, closing the prior pass's spot-check
  gap), full suite (1211 passed) — all independently re-run and clean. The two pre-existing
  `ruff`/`mypy` findings surfaced while running these checks (an unformatted/non-executable
  research script, several `test_flight_control_api.py`/`test_flight_control_lua.py` mypy errors)
  predate this commit by `git log -1`, are outside the diff, and are not this pass's to fix.

## Verdict

**APPROVED** — the required fix from the first pass is addressed: the cap now binds through the
real heading error at every card speed, documented and tested against the real (not idealized)
numbers, with the one known residual (plant-lag roll-out overshoot) disclosed in three places,
bounded by a test, and correctly judged acceptable to fly as a first cut rather than something that
needed fixing before this card is flown.

## Review Confidence

Full read of the diff, the plan's and implementation note's fix-pass sections, and the card.
Checks and one mutation re-run independently (not taken on report), plus two independent
first-principles numeric derivations (idealized-shaper peak rate, bank-cap-derived rate) that both
matched the documents exactly. `luac5.1` was available this pass and run clean, closing the one gap
the first pass flagged as a spot-check.
