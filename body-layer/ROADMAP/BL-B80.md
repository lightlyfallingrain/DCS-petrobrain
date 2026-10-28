# BL-B80 — The 9K113 pointing loop: pointing the sight on the AI axis

- [~] **BL-B80 — Drive the sight head to Petrovich's modelled aim by closing a loop on the AI axis
  (3060/3061), a position target that works only while DCS's own AI Petrovich is on and only while
  re-asserted every frame.** #status/in-progress Split out of `[[BL-B66]]` on
  2026-10-17 by user direction (*"OK to split BL-B66, do not start working on it yet"*), after the
  slew probe settled which channel exists. **The channel changed from the player axis (3025/3026)
  to the AI axis (3060/3061) after the 2026-10-21 probes — see the SUPERSEDED block immediately
  below.** This heading used to still say "player axis"; it did not, and the body text already
  carried the correction — fixed here by the 2026-10-22 DoD pass on Stages 1-3.

  **Re-planned 2026-10-22: `plans/9k113-sight-pointing/plan.md` (v2 — simulated sight is
  Petrovich's sight, DCS sight slaved to it). The "Status, 2026-10-22 — Stages 1-3" block that
  used to sit here described the v1 build (`plan-v1-position-model.md`), which this re-plan
  overturned wholesale (run 11, below); its Stage 4 sortie card is superseded and not to be flown.
  See `notes/the-9k113-sight-bl-b64.md`'s last bullet for why nothing in v1's own test suite could
  have caught this — only the live probe could.**

  **Elevation clip-edge probe merged 2026-10-27 (`d641ca3b`)**: `aircraft-layer/dcs-export/Export.probe-9k113-hud-elevation-limits.lua`,
  card `docs/acceptance/2026-10-27-9k113-hud-elevation-limits-probe.md`, ~1 min. Its `EDGE UP`/`EDGE DOWN`
  555 values set `ASP17_FIELD_EL_HALF_DEG` and the margin. `#needs-flight`

  **Elevation field measured in flight 2026-10-28, `fix/9k113-el-field-measured`, merged
  `23d436eb`.** *Superseded on merge: scale shipped as 1/0.037 (gimbal-derived), field ≈ +4.6°/−14.9°,
  and the down side is reachable — the 1/0.030 figures below were rejected in review
  (`plans/9k113-sight-pointing/review-el-field.md`).* Two sorties
  (`docs/acceptance/2026-10-28-sortie-feedback.md` §2-4) replaced the placeholder
  `MARK_BORESIGHT_EL`/`MARK_DEG_PER_UNIT_EL`/`ASP17_FIELD_EL_HALF_DEG` above with measured values:
  boresight 0.83, scale 1/0.030, and an **asymmetric** field (~+5.7°/−18.4° about boresight, not a
  half-angle) derived from the raw clip readings (top saturates at 1.0; bottom readback limit
  0.278, the user's own decision — *"readback limit... the important thing is that the Petrobrain
  simulated and DCS sight match"*). `sight_clip_to_field_body_deg`/`sight_mark_is_clipped` both
  gained a signature split (one elevation bound → up/down). Discovery: the measured down bound
  exceeds the sight's own gimbal down limit (−15°), so only the up side is ever reachable through
  the normal setpoint path — see `plans/9k113-sight-pointing/implementation.md`'s matching entry.
  `#needs-flight` still applies: this closes the elevation-calibration gap the previous entry
  flagged, but the edge-park behaviour itself (does the real mark visibly sit at the new bounds,
  does continuous tracking look right against them) is unconfirmed live.

  ## v3 Stage 6 DoD-passed 2026-10-26 (`f65f0ce0`, merged `d763ab20`) — `#needs-flight`

  `plans/9k113-sight-pointing/plan.md` v3 Stage 6 — the ASP-17 edge-park fix for the
  `docs/acceptance/2026-10-26-sortie-feedback.md` §2 symptom (real mark moving inside the HUD
  while the simulated sight pointed well off to the side) — is implemented, reviewed, and
  DoD-passed on `feature/9k113-sight-edge-park` (`plans/9k113-sight-pointing/dod-check.md`).
  Root cause: `run_sight_servo`'s field-validity gate compared the setpoint against the sight's
  **gimbal** limits (±60°/+20°/−15°), not the ASP-17's own much narrower readable window
  (measured ≈±4.3° azimuth) — occurrence 5 of this subsystem's recurring field-of-regard-
  enforcement defect (`.claude/agent-memory/dod/project_recurring_field_of_regard_enforcement_gap.md`),
  and per the plan's own words, the subsystem's *last* remaining field-of-regard-shaped check.
  Fix: `sight_mark_is_clipped` checked against the mark's own raw reading (566/555), and the real
  sight always closed-loop on `field_target_body_*_deg` — the setpoint radially projected onto the
  inset ASP-17 field, continuously tracked as the simulated sight moves (not a one-shot park).
  Open loop removed entirely, not kept as a fallback. Aircraft-layer-only; no body-layer source
  change (`body-layer/CLAUDE.md` gained a documentation clause only).

  Reviewer (`review-v3.md`), Performance (`performance-review-v3.md`, MONITOR — inherited
  baseline, not new), and Security (`security-review-v3.md`) all APPROVED with **no required
  fixes**. DoD mechanical checks: aircraft-layer `ruff format`/`ruff check`/`mypy --strict`/
  `pytest` (607 passed), `luac5.1 -p` and the `GETGLOBAL` undeclared-global scan on `Export.lua`,
  all clean; no debug output/TODO markers/error suppression in touched files; tree clean. No
  body-layer code-quality gate run — no body-layer source changed.

  **`#needs-flight`**: `ASP17_FIELD_EL_HALF_DEG`/`ASP17_FIELD_MARGIN_DEG` remain guesses per the
  user's own 2026-10-26 ANSWERED decision ("Elevation - measure in flight") — the build carries
  the per-frame raw-555/raw-566 trace (`push_slew_trace`, behind the `aircraft_layer_slew_debug.flag`
  touch-file) specifically so the next sortie can read the real elevation clip edges off it. Test
  card: see below. **Acceptance-boundary statement** (so a fixture pass is never mistaken for a
  flight pass): no automated test here touches a real 9K113 gimbal, a real ASP-17 optical mark, or
  DCS's own intermittent-obedience behaviour — whether the real field is actually ≈4.3°/the
  guessed elevation half-angle, whether the cross hair visibly parks at the HUD edge rather than
  drifting/pegging, and whether continuous edge-tracking looks smooth to a human eye are all
  outside this test suite's reach by construction.

  Card: `docs/acceptance/2026-10-26-bl-b80-v3-sight-edge-park.md`,
  published https://claude.ai/artifact/H4Q7cCrVqEh2G8sj75L6Su — branch to fly is `main`.

  This does not close the broader BL-B80 milestone (`[~]` stays correct) — Flight A/B below remain
  outstanding independent of this stage, and this stage's own flight (elevation measurement +
  edge-park visual confirmation) batches with them where practical.

  ## Merged 2026-10-23 (`a2ea382c`) before Flight A — still in progress, not flown

  `feature/9k113-sight-pointing` merged to `main` at user direction (*"merge BL-B80, I will test
  fly when I have a chance"*), ahead of the plan's own pre-merge condition (a cold start showing
  arg 960 lights as the READY lamp). **So the merged build carries that risk:** if 960 never lights
  on a cold start, OBSERV is refused for the whole sortie. Also unverified: elevation closed loop on
  555, mark scale and boresight calibration, the frame the AI rate acts in, and the 1.2 m aim
  offset. Flight A (`docs/acceptance/2026-10-22-bl-b80-v2-flight-a.md`, now on `main`) settles
  them; Flight B follows. Post-merge checks: both subprojects' mypy and pytest pass (body-layer
  2443 passed, 4 xfailed; aircraft-layer 533 passed); the only `ruff` findings are in
  pre-existing `research/` files outside the merge.

  **Fixed on `fix/guidance-ready-edge` (DoD pass 2026-10-23, tip `1390acfd`), merged to `main`
  2026-10-23 (`1e249dfb`).** The merged build's 960/READY callout did not match this plan's own Decision 2 ("only
  on change"): `CrewConsole.drain_guidance_unit_ready` held a one-shot latch that spoke
  "Guidance unit ready." on the first poll the lamp ever read lit — including a warm air start's
  very first sample, with no prior observation at all — and then never spoke again, so a real
  power cycle never re-announced. The fix replaces the latch with a true previous-observed
  edge (`guidance_unit_ready_prev_observed: bool | None`; `None` is not treated as `False`, so a
  warm air start stays silent and a power cycle re-announces). Reviewer and Security approved;
  Performance: MONITOR, not a blocker (one more per-poll `replace()` at ~1 Hz). This is the only
  change on that branch — no change to `sight_ready()`, OBSERV gating, or anything else BL-B80
  touches. **Does not change what Flight A/B should observe**: Flight A's own card runs no
  body-layer process at all (it is the aircraft-layer Lua probe plus a manual cockpit-lamp
  observation), so the pre-fix latch bug was never reachable from that card and the card needed
  no correction. Flight B (not yet written) should note that "Guidance unit ready." is expected
  once, on the observed lamp's off→on transition, not at mission start if the unit is already warm.

  **Planned, not yet built, 2026-10-26: `plans/9k113-sight-pointing/plan.md`, "v3 (2026-10-26) —
  the real sight never leaves the ASP-17 field (edge park)".**
  `docs/acceptance/2026-10-26-sortie-feedback.md` §2: the pilot flew the merged v2 build and saw
  the DCS mark moving inside the HUD while the debug view showed the simulated sight pointing well
  off to the side — a fifth occurrence of this subsystem's recurring field-of-regard-enforcement
  defect (`.claude/agent-memory/dod/project_recurring_field_of_regard_enforcement_gap.md`): the
  existing `run_sight_servo` field-validity gate compared the setpoint against the sight's
  **gimbal** limits (±60°/+20°/−15°), not the ASP-17's own much narrower readable window
  (measured ≈±4.3° azimuth), so the closed loop ran unsaturated against a mark reading that was
  physically clipped at the field edge. v3 (not yet implemented): the real sight is now always
  closed-loop, its commanded target the simulated direction radially projected onto the inset
  ASP-17 field when outside it, continuously tracking the moving intersection point as the
  simulated sight moves (pilot's same-day clarification) rather than parking once. Open loop is
  removed entirely. Aircraft-layer-only; no body-layer change. Awaiting user review of the plan
  before Implementer starts.

  **Fixed on `fix/observ-off-axis-zero` (DoD pass 2026-10-24, tip `8a46e30a`), merged to `main`
  2026-10-24 (`e1d16037`).** `docs/acceptance/2026-10-24-sortie-feedback.md` F1: the pilot saw the ASP-17 mark
  still moving with OBSERV off. `run_sight_servo`'s existing `if not observ_on then ... return end`
  path reset only its own software state, never the AI axis (`CMD_AI_AZ`/`CMD_AI_ELEV` via
  `SetCommand`) — and that axis latches at whatever was last commanded once nothing keeps writing
  it (a distinct mechanism from the dither finding two paragraphs above, which is about DCS
  *ignoring* an unchanging per-frame write; this is about the axis holding its value when writes
  *stop entirely* — see `notes/the-9k113-sight-bl-b64.md`). The fix adds a one-time zero write
  (`sight_point_quiet(0.0, 0.0)`) on the genuine OBSERV on→off edge, by whichever of Petrovich/DCS
  AI/the player caused it, and writes nothing on every other off frame; `LuaExportStop` resets the
  new edge-tracking state so a mission restart cannot replay a stale edge. Reviewer and Security
  both APPROVED, no required fixes. This is the only change on that branch — no change to
  `sight_ready()`, the servo's on-path proportional loop, or anything else this entry's v2 design
  touches. `#needs-flight` — fixture-verified only; whether `SetCommand(..., 0.0)` actually
  recentres the real gimbal, or merely halts it where it was, needs the live check in that sortie-
  feedback entry. Does not change what Flight A/B above should observe (neither flight's card
  exercises an OBSERV-off transition).

  ## Status, 2026-10-22 — v2 Stages 1-4 (with 3b) built and reviewed; Stage 0/4 flights outstanding

  `feature/9k113-sight-pointing` (tip `e009465eba841a1a320ac02740dbbd1133221b96`) implements the
  v2 design — Petrovich's simulated 9K113 sight (`belief/sight_head.py`: gyro world-stabilised,
  gimbal-limited, slew-rate-limited) drives perception directly, and the real DCS sight is a
  best-effort slave of it via a reshaped `sight_target` wire op and a proportional (Kp-only)
  `run_sight_servo` loop in `Export.lua`, with an always-on per-frame dither to keep the AI axis
  obeyed (run 11's finding). "Seen aim" (Stage 3b, `attack_run.seen_world_direction` /
  `select_sight_goal`) lets the sight aim at the resolved target's true direction while belief's
  world-location estimate stays exactly as imprecise as before — the pilot's own answer to
  Decision 1, a sanctioned second consumer of `Percept.relative_direction` alongside attack-run
  alignment, fenced by `test_sight_head.py` and an `F4` differential no-leak test.

  DoD (2026-10-22, this pass) re-ran every mechanical check fresh in an isolated worktree:
  `ruff format --check` / `ruff check` / `mypy --strict` clean on both aircraft-layer (27 files)
  and body-layer (71 files); `aircraft-layer` pytest 533 passed; `body-layer` pytest 2443 passed,
  4 xfailed (one order-dependent flake under randomized test order,
  `test_connection_reporter_announces_the_first_connection`, confirmed pre-existing — introduced
  by `a5def59e`, outside this branch's diff — and not reproducible with ordering disabled; not a
  blocker, worth a `caplog`-isolation fix sometime, not gating this entry); `luac5.1 -p` clean on
  `Export.lua` and the new calibration probe; the `GETGLOBAL` scan lists only genuine DCS/stdlib
  globals. Both Reviewer required-fix rounds (`review.md`, NEEDS REVISION → three fixes → APPROVED)
  and Security's plan review, deep analysis, and Performance review are all APPROVED (Performance:
  MONITOR on two already-accepted patterns, not a blocker). Full detail:
  `plans/9k113-sight-pointing/dod-check.md`.

  **Not yet merged to `main`.** Two live flights are outstanding, neither of which this DoD pass
  can perform:
  - **Flight A (Stage 0, the calibration probe)** — mark scale, boresight, 555's elevation clip
    edges, the world-frame azimuth-loop steady error, and the AI-rate frame in a turn. **Also
    carries the 960-cold-start READY-lamp check, which the plan itself states must happen "before
    any merge"** (`plan.md`, Risks: "960 on a cold start is unconfirmed... refuses OBSERV for the
    whole sortie") — if 960 never lights, Petrovich cannot use OBSERV at all, which is a
    correctness blocker on the whole feature, not an ordinary deferred acceptance item. Card
    (published): https://claude.ai/artifact/YAfTTDn8XbeinrPjUAyovf (source
    `docs/acceptance/2026-10-22-bl-b80-v2-flight-a.md`).
  - **Flight B (Stage 4)** — the simulated head holding a world direction through a turn, the mark
    settling on the servo, the seen-aim rows (mark sits on the real vehicle, belief stays off),
    and the acceptance-boundary items below. Card not yet written — follows Flight A's numbers
    (Stage 0's calibration constants feed Stage 4's servo).

  **Per root `CLAUDE.md`'s standing direction, live acceptance does not gate other work starting**
  — but per the plan's own words above, Flight A's cold-start half specifically gates *this merge*,
  which is a plan-stated condition, not this DoD pass inventing one. Not tagged `#needs-flight`:
  that tag is for a shipped, merged change awaiting its sortie (`docs/TAGS.md`); this entry has not
  merged, so `#status/in-progress` ([~]) stays correct. Add `#needs-flight` only if a future
  decision merges this ahead of Flight A/B (would need the 960 risk separately accepted).

  **What Stage 4/Flight B must still verify, not yet checked by anything automated** — this
  batch's own acceptance boundary, stated so a fixture pass is never read as a flight pass:
  - Whether the real DCS 9K113 actually holds the simulated world direction through a turn at the
    numbers Flight A/B predict, not just that the Python/Lua math agrees with itself.
  - Whether the seen-aim mark visibly sits on the real vehicle hull (not its base) at the ranges
    Flight B exercises — the vertical-offset risk the plan names.
  - Whether belief's position estimate genuinely stays unaffected by a held seen-aim look, in a
    real flight rather than the differential fixture test (F4) that proves the mechanism, not the
    live behaviour.
  - Whether a hard manoeuvre's real DCS auto-OBSERV-off is followed correctly by `home_phase` and
    the head going `off`, not only the commanded path.
  - Whether the intermittent-obedience risk (suppressed by dither in probe runs, not explained)
    ever resurfaces in ordinary flight outside the field, where nothing can see it.

  **This blocks `[[BL-B67]]` (the ATGM run)**, which needs a trustworthy pointing channel as its
  guidance-accuracy baseline — per the plan's own "Second-order effect" section, Flight A/B's
  numbers (and any correction they force) must land here before `BL-B67` is planned, not after.

  > **SUPERSEDED AGAIN 2026-10-22 — read this block first; both blocks below predate it.**
  > Probe runs 1–10 (`docs/acceptance/2026-10-22-9k113-ai-latency-probe.md`, merged to `main` as
  > `6d6c99a9`) overturned the 2026-10-21 channel model:
  > - The AI axis (3061/3060) is a **rate** command at the spec rates (20°/s az, 10°/s el per
  >   unit), not a position target, with the overlay on or off. 874/876 echo the demand; the only
  >   readback is the ASP-17 mark (565/566, 555/556), inside the HUD field (~±4.3°).
  > - DCS **obeys it intermittently** (ignored 3–100+ s, invisibly, position-independent). A small
  >   fast **dither** on the command (0.6° at 8 Hz) kept it obeyed in runs 9–10. Stick park toggle
  >   and the overlay are not the gate.
  > - **Л5, arg 898** lights when gyro alignment is done (T+10 s after OBSERV on, five runs); arg
  >   **960** is very likely the guidance-unit READY lamp ([[BL-B66]] concluded it unreadable).
  >
  > **Design direction (explore, 2026-10-22, `plans/9k113-sight-pointing/explore-notes.md` on
  > `feature/9k113-sight-pointing`):** Petrobrain's simulated sight is Petrovich's sight (*"what
  > Petrovich could plausibly see with a sight that works as it should"*), held to gimbal limits
  > and maximum slew rate; the DCS sight is a best-effort slave with tiny dither always on; inside
  > the HUD, any trick that gets it on the simulated direction is allowed, and for ATGM the mark
  > must sit within ~0.02° (BTR at 3–4 km). Gate on 960 and 898. **The branch
  > `feature/9k113-sight-pointing` was built on the position model and is to be re-planned.**
  > **Run 11 (merged `d6ed947f`):** DCS takes the axis only when its value **changes** (pilot's
  > hypothesis, confirmed: constant 3/10, per-frame flicker 18/18). Holding with 0.6° / 8 Hz dither:
  > 0.006–0.013° RMS, inside the ATGM budget.
  > Status: probe phase closed; v2 plan on `feature/9k113-sight-pointing`, Stages 0–4 being built.
  >
  > **SUPERSEDED 2026-10-21 — read this block first; the text below it predates the finding.**
  > Probes flown 2026-10-21 (`aircraft-layer/research/2026-10-21-9k113-slew-readback-probe-findings.md`,
  > "Pointing probe runs 2–3") settled the channel. It is **not** the player axis and **not** a
  > rate loop. It is the **AI axis (3061/3060), an exact position target**: readback matched every
  > target to 0.1°, and the pilot saw the ASP-17 crosshair follow. Two conditions:
  > **DCS AI Petrovich must be on**, and **the target must be re-sent every frame** while we hold
  > the sight. With him off, writes are inert and 874/876 read 0. When we stop re-sending, he takes
  > the sight back. **`[[BL-B63]]` is therefore not a dependency.** The readback is trustworthy
  > under those conditions, so it serves as the check.
  >
  > **User direction, 2026-10-21, verbatim:**
  > *"These findings mean one additional thing: DCS Petrovich AI overlay *must be on* when
  > Petrobrain uses 9K113. We must ensure that in code. Turn AI overlay ON when with OBSERV ON and
  > make sure it keeps ON, even if player closes it, open it again immediately. Turn overlay OFF
  > with OBSERV OFF. Note that DCS AI may turn OBSERV OFF at too hard manouvres (or player can
  > turn any switch at any time), so OBSERV state in code must come from OBSERV state in DCS."*
  >
  > So, in scope here:
  > - **AI overlay follows the observed OBSERV state** (arg 886 readback), never the commanded one.
  >   On when OBSERV reads on, re-opened at once if closed, off when OBSERV reads off.
  > - **Open before planning.** The only known control is `ShowMenu` (device 30, cmd 3001), and it
  >   is a **toggle**. Keeping the overlay on therefore needs a readable "is it open" signal, or a
  >   blind toggle could close it. Candidate: whether `list_indication(10)` (the wheel, already
  >   exported as `petrovich_wheel`) is empty while it is closed. Unverified. Also unverified:
  >   whether closing the overlay is the same thing as switching his AI off.
  > - **Update, same day:** the wheel can't be the signal. User: *"Since we have to keep overlay
  >   open, I'd rather hide the wheel, it's possible in DCS settings. We need some other way."*
  >   **Proposed:** detect his AI from the pointing readback itself. If 874/876 stay 0 for ~0.5 s
  >   while the target is non-zero, his AI is off: press `ShowMenu` once and recheck. Aim 0.5° off
  >   a centre target, because centre reads 0 either way. The user confirmed: with the wheel hidden,
  >   `ShowMenu` still toggles his AI (*"yes"*), and one press reliably flips it (*"yes"*). Still to
  >   measure: how fast the readback obeys after he comes back on. Probe planned for 2026-10-22.

  **Why it is its own entry rather than a stage of `[[BL-B66]]`.** The switch half of `BL-B66` is
  unblocked and buildable today — all five writes measured working. This half is blocked on
  `[[BL-B63]]`, needs a controller with an empirical deflection law, and needs one more probe run
  before any law can be fitted. Keeping them together would hold working code behind an unbuilt
  milestone, which is exactly the scope caution `plans/9k113-effectors/plan.md` raised against
  itself.

  ## What the probe settled, 2026-10-17

  `aircraft-layer/research/2026-10-17-9k113-effector-and-slew-probe-findings.md`:

  - **The AI axis (3060/3061) is inert.** Five bearings and twelve staircase steps per axis, two
    runs, one with the aircraft correctly set up and `OBSERV` confirmed on — args 874/876 never
    left `0.00000`. Every call returned `ok=true`, so the return value distinguishes nothing.
  - **The player axis moves the head**: ~45° of azimuth in one ~3 s hold at 0.5 deflection
    (13–16°/s), elevation the same shape and sign-inverted, in the same run and through the same
    `SetCommand` path seconds after the AI axis did nothing.
  - **The user prefers this channel on its own merits**, not only by elimination — *"I much prefer
    the player axis approach"* (`docs/acceptance/2026-10-17-9k113-procedures-direction.md`). So
    the `BL-B63` dependency is a cost accepted knowingly, not one imposed by a negative result.

  ## Hard dependencies

  - **`[[BL-B63]]` — the fast lane.** A rate-commanded loop cannot close at 1 Hz. This is the
    dependency `BL-B66`'s entry carried under direction §12, which `plans/9k113-effectors/plan.md`
    §0 argued away on the strength of the 2026-09-11 AI-axis measurement; the probe restored it.
  - **One more probe run before a deflection law is fitted.** The slew probe sampled four times per
    hold and saw two plateaus rather than a ramp, so nothing separates *"the readback is quantised
    or lagged"* from *"the motion is stepped"*. The fix is per-frame logging of args 874/876 — a
    one-line change to `Export.probe-9k113-slew.lua`, not a new script.

  **The extra probe run may come free, 2026-10-21.** `BL-B66` Stage 4b adds per-frame logging of
  args 874/876 and a slot for the 3025/3026 command (user: *"Put logging in so that the slew loop
  can be adjusted based on data from logs. Actual vs desired angles especially, slew command
  values, etc."*), and the `BL-B66` sortie includes ~2 minutes of hand-slewing. If that log
  separates quantised / lagged / stepped readback, the probe above is done. **This entry must fill
  the command slot and add its loop internals** (deflection chosen, error, deadband in/out,
  converged) to the body-layer sight trace, so the loop is tuned from logs, not guessed.

  ## What it is not

  **Not the slew *time* model.** §8's requirement — the sight takes time to move, so Petrovich
  cannot expect instant alignment — is satisfied inside `advance_sight_aim` by rate-limiting
  `actual` toward `desired` at the device spec's 20°/s azimuth and 10°/s elevation. That is
  body-layer only, needs no cockpit write, and belongs with `[[BL-B64]]`/`[[BL-B66]]`.
  **Superseded 2026-10-21 (user direction, *"yes"*): the slew-time model moves *into* this
  entry** — `BL-B66` keeps `advance_sight_aim` a pass-through, and the model lands here beside the
  loop whose readback replaces it (`plans/9k113-effectors/explore-notes.md`, point 3). This entry
  only makes the **real head follow** a pointing direction that is already correctly paced.

  ## Field-of-regard limits: DCS enforces them once this lands

  **User direction, 2026-10-21**, on DoD's finding that `9k113-narrow-search` was the fourth time
  the simulated ±60°/+20°/−15° regard check shipped wrong (`notes/the-9k113-sight-bl-b64.md`):

  > *"DCS will enforce it. I'd rather rely on the real limits than simulation of them. Simulation
  > is just a temporary phase while the effectors are not build. Of course the logic behind where
  > we want to point the sight must behave correctly."*

  So the body-layer regard check in `belief/optic_policy.py` is a **stand-in** for the mechanical
  limits, needed only while no real head moves. Once this loop drives the head, the head stops
  where DCS stops it. What stays Petrovich's job is the **pointing intent** — choosing a sensible
  direction to look. Do not invest in hardening the simulated enforcement further.

  **What becomes of the simulated check when the loop lands — decided, user, 2026-10-21:** keep
  only enough of it that the intent never asks for a direction the head cannot reach (otherwise the
  loop chases a target it can never hit). In his words:

  > *"keep enough of it that Petrovich never asks for a direction the head can't physically reach
  > -> this. The +-60 azimuth limit especially. Might leave the vertical limit out, since that's
  > difficult for a real operator to judge."*

  So: **±60° azimuth stays as an intent constraint** — an operator knows where the head's side
  stops are. **The +20°/−15° elevation limits are likely dropped** from intent, because a real
  operator would not judge them reliably; DCS's own stop handles them. "Might" — the elevation
  half is his leaning, to be confirmed when this entry is planned, not a settled removal.

  Related: `[[BL-B66]]` (the switch half, unblocked), `[[BL-B63]]` (hard dependency),
  `[[BL-B64]]` (perception, lands first), `[[BL-B67]]` (the ATGM run, which is built out of this
  loop and cannot exist without it).
