## Security Plan Review: 9k113-sight-pointing (BL-B80, v2)

Reviewing `plans/9k113-sight-pointing/plan.md` as of its "Re-plan, 2026-10-22" header (seen-aim
Stage 3b, the reshaped `sight_target` wire payload, the new `GET /sight_servo/latest` endpoint).
This supersedes the v1 review below — v1's code (Stages 1-3, `sight_target` with `az_cmd`/
`elev_cmd`) is already implemented, reviewed and DoD-passed, but **never flown**, and this plan
removes its position-model pieces.

### Dependencies Checked

No new dependency. `/extract-plan-deps`-equivalent check: the plan's own text contains no
dependency statement at all (one `grep` hit each for "wheel" in "do not reinvent the wheel" and a
backlog-ID cross-reference — neither is a package). Confirmed against both subprojects'
`pyproject.toml`: `aircraft-layer` is `dependencies = []`; `body-layer`'s only entries are the
pre-existing, already-justified `pyproj`/`numpy` transitive pulls from the world-model seam,
unrelated to this plan. Every new symbol the plan lists (`SightHead`, `select_sight_goal`,
`world_direction_from_body`, the reshaped Lua `sight_target` op, `run_sight_servo`) is stdlib
Python / hand-rolled Lua, matching the stdlib-only posture both subprojects' `CLAUDE.md` state.

### Design Findings

Threat model unchanged: single-user, LAN-only (root `CLAUDE.md` "Agents"); the realistic attackers
are a malicious dependency (ruled out above) and an infected LAN box reaching the aircraft-layer's
LAN-facing HTTP API (`DEFAULT_HOST = "0.0.0.0"`, `aircraft-layer/src/api/server.py:260`) or probing
its loopback-only command socket.

- **`sight_target`'s payload is reshaped but stays a fixed-device/cmd op, not a new free-form
  surface.** v1's `{az_cmd, elev_cmd}` → device 7 / cmd 3060/3061 becomes `{goal_az, goal_el,
  goal_rate_az, goal_rate_el, t_sim}` on the same fixed device/cmd pair, still riding
  `CommandSender`'s existing loopback-only socket (no new listener). This re-confirms this project's
  own prior finding on this exact op
  (`[[project_bl_b80_sight_target_op_narrower_than_cockpit_switch]]`): it remains narrower than the
  already-accepted `cockpit_switch` exception (arbitrary `(device, cmd, value)`), which an infected
  LAN box reaching this API already has unrestricted use of. Adding two more floats to one fixed op
  does not change that category of exposure.

- **The plan states explicit bounds for three of the five new fields, and should state them for
  all five — required addition, not a rejection.** Design detail section: *"Bounds: az ∈ [−360,
  360], el ∈ [−90, 90], |rate| ≤ 30 °/s, all finite; enforced in the API and in Lua (v1's two-sided
  pattern)"* (plan.md line 194). `t_sim` is used two lines later directly in an arithmetic
  expression Lua evaluates every frame: `goal(t) = goal + rate·clamp(t − t_sim, 0, cap)`
  (line 207) — but `t_sim` is not named in the bounds sentence. The arithmetic is structurally safe
  **given a finite `t_sim`**: `clamp(·, 0, cap)` bounds the extrapolation term regardless of how
  stale or how far in the future `t_sim` claims to be. It is **not** safe given a non-finite one —
  `t − t_sim` with `t_sim = NaN` yields `NaN`, and `NaN` comparisons in Lua's `clamp` (via `<`) are
  all false, so the result depends on `clamp`'s exact implementation rather than being guaranteed
  caught; a `NaN` or `Inf` `goal(t)` would then feed the rate-limited setpoint step, which this
  project's own gimbal-clamp is the last line of defense against, not the first.
  **This is exactly the shape of this project's own most recent, corrected finding on this file**
  (`[[project_export_lua_json_extractor_cannot_yield_nonfinite]]`: *"this input channel's own
  parser can't produce X, so a downstream guard against X is dead code" is a claim about the
  parser's full accepted grammar, not about the subset of inputs anyone had tried feeding it* —
  here the analogous unchecked assumption would be "`t_sim` is only ever a sane model-time float
  because that's what a correct sender sends," which is not a property the wire format enforces.
  **Required addition**, both layers, mirroring the existing missing-field rejection
  (`handle_sight_target_command`'s *"ignoring malformed sight_target command (missing az_cmd/
  elev_cmd)"*) and the API's existing per-field `isfinite`-and-bound checks: reject the whole
  command if `t_sim` is absent or not finite, the same way `goal_rate_az`/`goal_rate_el` must be.
  Since `extract_json_number_field` already guarantees "absent/non-numeric/non-finite → `nil`"
  (the corrected memory above), this is a one-line presence check on the Lua side plus the
  matching API-side `isfinite` check — small, but it must be written into the Implementation Plan
  explicitly rather than left to "all finite" reading as covering a field the sentence does not
  name. Not a rejection: the mitigation pattern already exists in this codebase for the sibling
  fields, this is applying it to the one field the sentence omitted.

- **`GET /sight_servo/latest` is a new read endpoint, not a new write surface.** Same shape as the
  existing `/cockpit_switch/latest`/`/telemetry/latest` family: no request body, no query
  parameters, publishes servo mode/setpoint/mark/error/stall state that is no more sensitive than
  the kinematic and world-object state this API already exposes LAN-wide. Consistent with the "a
  departure, stated" note in the plan's own Affected Files section (a second feed because the
  servo status changes every frame while `cockpit_switch`'s feed is change-gated) — a rate-class
  split, not a new exposure category. No finding.

- **Removal of v1's `ShowMenu` press reduces attack/failure surface, net.** v2 deletes
  `run_sight_pointing`'s overlay-detector `ShowMenu` presses entirely (*"the overlay is not needed
  ... and pressing ShowMenu would switch ED's AI on — a likely second writer to device 7"*). This
  removes a self-inflicted path to a second writer on the same device the new servo now owns every
  frame; nothing in v2 replaces it with an externally-triggerable press. Net improvement over v1,
  not a new risk.

- **Unbounded `Content-Length` read**: unchanged from v1's review, still tracked under `AC-B11`
  (low/low on this project's threat model). `sight_target`'s reshaped POST handler reproduces the
  same pre-existing shape; `GET /sight_servo/latest` reads no body at all, so it does not add to
  `AC-B11`'s count. `AC-B11.md`'s text still says "five... eventually six" though `sight_target`
  (v1) already made it six — the same cosmetic staleness v1's own review flagged and did not get
  fixed; not re-filed, still housekeeping, still not blocking.

- **No LLM/prompt-injection surface.** This plan touches no text any model reads — perception
  geometry, a simulated head, and a per-frame control loop. Not applicable.

- **No secrets/credentials introduced.**

### No-omniscience fences (integrity property, in scope per this role's remit)

Decision 1's answer lets the sight aim at the target's *actual* direction while it is resolved in
the glass — a genuine new truth-channel consumer, which is exactly the kind of change this role is
asked to scrutinize structurally, not just for code-execution/access risk.

- **Reused, not reinvented, channel.** `seen_world_direction` is built as a second consumer of
  `Percept.relative_direction` — a datum this project already sanctioned and fenced for
  `attack_run.py` (`plans/attack-run/plan.md` Decision 16; `RELATIVE_DIRECTION_SIGMA_DEG = 0.0`,
  "exact while looking"). `belief/position_belief.py`/`Contact` never read it; that separation is
  unchanged by this plan. This matches this project's own prior lesson
  (`[[feedback_reuse_relative_direction_channel]]`: *"before designing any 'Petrovich sees it, so
  aim/guide exactly' truth channel, reuse `Percept.relative_direction` via `attack_run` — it
  already exists, is exact, and is grep-fenced"*) rather than opening a second truth-reading path.
- **F2/F3 are the right shape of fence**: F2 confines `seen_world_direction` to
  `belief/attack_run.py` and `belief/sight_head.py` only; F3 confines `sight_head` imports to
  `logger.py`/`sight_trace_writer.py` and explicitly excludes `belief/`, `mission_memory/`,
  `tools.py`, `tool_api.py`, `crew_console.py`, `speech.py` by name. Naming the speech/tool-facing
  modules explicitly is the part that matters most here — it is precisely the set of modules that
  could otherwise leak an exact direction into something the pilot hears or a tool call returns.
- **F4's differential no-leak test is the strongest fence in the set** — a behavioral proof
  (`ContactStore`, `MissionMemory`, every utterance, every `TOOL_SET` result identical with
  `seen_world_direction` monkeypatched to `None`) rather than only a static grep. This is the right
  instrument for the claim being made ("this channel cannot change what he says or remembers"); a
  grep alone would only prove nobody *imports* the function, not that its value cannot influence
  behavior through some other path.
- **Write-only sinks are stated, not just assumed.** The plan is explicit that the wire goal and
  the slew-trace `aim_source`/`|seen − belief|` columns are never read back ("Nothing reads (b) or
  (c) back") — consistent with every other trace file in this codebase
  (`detection_trace_writer.py` precedent). Worth a Mode 2 check that the implementation does not add
  a reader of `sight_trace_writer`'s output anywhere under `belief/`, since that would reopen
  exactly the path F3 closes.
- **One scope boundary stated correctly**: the plan's own Invariants addition says this is "the
  same perception datum given a second consumer, not a second exception... a third consumer is a
  user decision" — the right place to put the brake, rather than leaving the door open for a future
  plan to add a third reader without re-asking.

No finding here beyond confirming Mode 2 should re-run F2/F3/F4 against the actual diff (the
fences are specified well; whether the implementation matches the specification is the next gate).

### Passed to Reviewer

Player-facing correctness, not security — noted per this role's scope, no verdict given:

- **Field-of-regard / gimbal-clamp enforcement on the new simulated head.** This exact subsystem
  (9K113 sight, BL-B64/B80) has this project's own measured recurring defect: four prior
  occurrences of a field-of-regard or gimbal-limit enforcement gap, the fourth "checked, but in the
  wrong reference frame" (`[[project_bl_b64_field_of_regard_unenforced]]`,
  `[[project_recurring_field_of_regard_enforcement_gap]]`). `SightHead`'s world-hold-then-clamp
  step and the Lua setpoint's own gimbal clamp are the two places this plan's fifth occurrence
  would hide if it recurs — Reviewer should check both against the stated ±60° az / +20/−15° el
  limits in the frame they are actually clamped in, not just that a clamp call exists.
- Elevation closed-loop feasibility (555's clip edges, never closed-loop-tested) — Flight A
  decides; a correctness/measurement question, not a security one.
- Aim-point-on-the-hull vs. object reference point, and merged-cluster centroid aiming — both
  stated as open, both player-experience quality questions.
- The `still`/dither-vs-flicker per-frame mechanism selection (Stage 5, probe-gated) — a tuning/
  behavior question once a probe answers it.

### Verdict

**APPROVE WITH REQUIRED CHANGES**

Required change (one, narrow): add `t_sim` explicitly to the "Bounds... all finite" sentence and
the per-field validation the Implementation Plan describes for `sight_target`, at both the API
layer (`isfinite` check, reject the command on failure) and the Lua layer (reject on missing/
non-finite, the same posture `az_cmd`/`elev_cmd` already have) — closing the one field the current
bounds sentence does not name, in a wire message whose arithmetic depends on it being finite.

Everything else: no new dependency, no expansion of the write surface beyond the already-accepted
`cockpit_switch` precedent, the new read endpoint is a rate-class split of an already-exposed
telemetry category, the pre-existing `Content-Length` pattern stays tracked under `AC-B11`, and
the seen-aim no-omniscience design reuses an existing fenced channel with a materially strengthened
fence set (F2-F4, including a behavioral differential test). Proceed to Implementer with the one
required change folded into Stage 4's `sight_target` work.

---

## v1 (superseded)

## Security Plan Review: 9k113-sight-pointing (BL-B80)

### Dependencies Checked

No new dependency. Confirmed against the plan's "Affected Modules/Files" list and both subprojects'
stdlib-only posture (`aircraft-layer/CLAUDE.md`, `body-layer/CLAUDE.md` "Tech stack"): every new
symbol (`CommandSender.send_sight_target`, the `sight_target` Export.lua op,
`AircraftLayerClient.write_sight_target`, the `sight_effector` conversion functions) is stdlib
Python / hand-rolled Lua, same as every existing op on this channel.

### Design Findings

Threat model is single-user, LAN-only (root `CLAUDE.md` "Agents" / this role's own scoping
section). The realistic attackers are a malicious dependency (ruled out above — no new one) and an
infected LAN box reaching the aircraft-layer's HTTP API or its loopback sockets.

- **New surface is `POST /command/sight_target` (az_cmd, elev_cmd) → a third, narrow UDP op on
  `Export.lua`'s loopback command listener → fixed device 7 / cmd 3060/3061.** This is *narrower*
  than the `cockpit_switch` op this codebase already ships, which accepts **any**
  `(device, cmd, value)` triple with no allow-list — a deliberate exception on record (user
  direction 2026-10-21, `aircraft-layer/CLAUDE.md` "What this is": *"Allow any cockpit switch...
  This is LAN only and switch behaviour is limited to DCS"*). An infected LAN box reaching this API
  already has unrestricted cockpit-write capability through `cockpit_switch`, including the ability
  to press `ShowMenu` (device 30) directly. `sight_target` adds no new category of exposure — low
  risk, consistent with an already-accepted precedent. — **not filed, intentionally**: this is an
  observation that the new surface is subsumed by an already-reviewed, already-accepted broader
  one, not a new finding to track.
- **Validation posture matches the plan's own stated intent** ("same validation/shape posture as
  `/command/cockpit_switch`" — plan, Stage 2): finite-float checks on `az_cmd`/`elev_cmd`, no
  allow-list needed since there is nothing to allow-list (one fixed device/cmd pair). This is the
  right reuse — "do not reinvent the wheel" — of the pattern `_handle_command_cockpit_switch`
  already established (`aircraft-layer/src/api/server.py:607-665`): reject non-numeric/bool/NaN/Inf
  before forwarding. No numeric *bound* (e.g. clamping to the ±60°/+20°/−15° physical range) is
  specified at the API layer, but this is mitigated structurally by the design itself, not
  incidentally: Export.lua never writes the target directly — it rate-limits the commanded value
  toward it by at most `rate × dt` per frame (Stage 2), so an out-of-range or extreme target can
  only ever be *approached*, never jumped to, and DCS's own mechanical stops are what actually
  bound the head's real position (per the explore notes' own direction — "DCS will enforce it").
  An attacker sending `az_cmd=1e30` gets smooth, bounded, physically-limited motion toward a target
  it will never reach — a behavioral oddity at worst, not a safety or stability issue. **Low risk,
  not blocking.** Recommended, non-blocking improvement for the Implementer: clamp `az_cmd`/
  `elev_cmd` to a generous sane range (e.g. ±90° equivalent in raw units) alongside the finite
  check, purely to keep `ai_off_since`'s "commanded is non-trivial" comparison in Export.lua from
  ever reasoning about an absurd magnitude — cosmetic, not a blocker.
- **Loopback-only channel preserved.** The new `sight_target` op rides the existing
  `CommandSender`/`DEFAULT_PORT=7793` loopback UDP socket (`aircraft-layer/src/collector/
  command_sender.py`), not a new listener — consistent with every other op on this channel and with
  the "no new listening socket" posture a LAN port scanner would otherwise need flagging for.
- **Automatic `ShowMenu` press (the AI-on/off detector) is internally triggered, not
  externally commanded** — it fires from Export.lua's own per-frame comparison of the readback
  against the commanded value, not from a value an external caller supplies directly. Nothing in
  the wire protocol lets a LAN caller force a `ShowMenu` press through this new op beyond what
  `cockpit_switch` already permits directly. The self-correction property the coordinator
  amendments require (a false press corrects itself next interval, never latches) is a
  **correctness** property of the detector's behavior in the cockpit, not a security control —
  noted, not reviewed here (see "Passed to Reviewer" below).
- **Unbounded `Content-Length` read.** The new `_handle_command_sight_target` handler will
  reproduce the same `int(Content-Length) → rfile.read(length)` shape every existing POST handler
  on this server already has, with no upper bound. **Already filed and tracked**: `AC-B11`
  (`aircraft-layer/ROADMAP/AC-B11.md`), rated low/low on this project's threat model, not blocking
  any individual feature's merge — this plan would be the sixth endpoint sharing the shape (the
  file's text already anticipated a sixth before `BL-B67`). No new finding needed; worth a one-line
  update to `AC-B11.md`'s endpoint count when this ships, but that is housekeeping, not a security
  gate.
- **No LLM/prompt-injection surface.** This plan touches no text the brain layer or any model
  reads — it is a pure control-loop/effector addition (aim command → rate-limited cockpit write →
  position readback). Not applicable.
- **No secrets/credentials introduced.**

### Passed to Reviewer

The following are player-facing correctness concerns, not security findings — noted per this
role's scope, no verdict given:
- The derived (not independently measured) elevation degree↔raw conversion formula, to be verified
  live at the two mechanical stops (plan's own Risks section, Stage 4).
- The placeholder AI-off-detection timeout/re-press interval values, pending the 2026-10-22 latency
  probe (plan's own Risks section).
- The gyro-alignment window's effect on perception (no sight-tier optic during the ~10 s window)
  and the `home_phase` derivation moving from command-driven to observed-arg-886-driven — both are
  belief/perception-correctness properties for Reviewer to check against the plan's Co-moving
  Fields table.

### Verdict

APPROVED

No dependency change, no expansion of attack surface beyond an already-accepted precedent
(`cockpit_switch`), the one pre-existing pattern this plan reproduces (unbounded `Content-Length`)
is already filed and tracked under `AC-B11`, and the one place a numeric bound could be added is a
non-blocking, cosmetic recommendation given the rate-limiter's structural mitigation. Proceed to
Implementer.
