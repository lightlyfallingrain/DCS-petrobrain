## Security Deep Analysis: 9K113 sight edge-park (BL-B80 v3, Stage 6)

Branch `feature/9k113-sight-edge-park`, tip `e1d9f985b7361630b584c0acca57f1167e6e50e1`
(verified: HEAD was a strict ancestor of this sha on a clean tree; fast-forwarded, no cherry-pick
needed). Diff base `9dfc3d2f32b4f012672c95fbda7d02ddcb3a19de`. Scope per root `CLAUDE.md`:
single-user, LAN-only — realistic attackers are a malicious dependency and an infected LAN host
port-scanning. Player-experience correctness (slew limits, callout wording, belief state) is
Reviewer's remit, not restated here as a finding — `review-v3.md` already covers it and reports no
required fixes.

### Dependency Status

No dependency change. `extract-plan-deps`-equivalent check: `plan.md`'s v3 section adds no new
package on either the Python or Lua side — purely internal `Export.lua` math (two new pure
functions) and two new fields on an existing schema/wire message. No `pyproject.toml` touched.

### What this stage actually is, for the security questions it was scoped to

Confirmed by reading the diff rather than the plan's account of it:

- **No new HTTP endpoint, no new inbound command.** `grep` for `handle_<new>_command`,
  `json.decode`, `rfile`, `Content-Length` across the `Export.lua` diff: zero new matches. The
  only wire changes are (a) two new optional fields and one new boolean appended to the *existing*,
  already-reviewed `push_sight_servo_state` outbound status line (consumed read-only via
  `GET /sight_servo/latest`), and (b) three new fields appended to the existing `SLEW_DEBUG`-gated
  per-frame file log line. The inbound `sight_target` command path (`az_cmd`/`elev_cmd`/
  `goal_rate_*`/`t_sim`, reviewed in `security-review.md`'s v1/v2 sections) is untouched in this
  diff.
- **No code execution surface.** `grep -E 'eval|exec\(|loadstring|dostring|subprocess|os\.system|pickle|yaml\.load|__import__'`
  across the full diff: zero hits (same check `project_bl_b66_9k113_effectors_deep_analysis`
  memory used, re-run here rather than assumed clean by precedent).
- **No new file-system write path.** `push_slew_trace`'s destination file is the existing
  `SLEW_DEBUG`-gated log, unchanged path, append-only; the three new fields it writes
  (`mark_az_raw`, `mark_el_raw`, `mark_clipped`) are all numbers/booleans formatted through the
  file's own existing `fmt_num_or_null`/`tostring`, never string-concatenated from external text —
  no log-injection surface (nothing here takes an attacker-shaped string and writes it verbatim).
- **No change to anything a LAN port scanner reaches.** The collector's TCP listener (receiving
  Export.lua's push) and the HTTP API's bind/handler set are unchanged by this diff — confirmed by
  `git diff --stat`, which shows no `src/collector/server.py` or `src/api/server.py` hunk at all.
  `GET /sight_servo/latest` grows two more floats and a bool in its JSON body; it was already a
  read-only, unauthenticated-by-design LAN endpoint under this project's accepted threat model
  (consistent with every other `GET .../latest` endpoint), and nothing about this stage changes
  what that endpoint accepts or how it fails on hostile input — it still takes no request body.

### Schema validation on the new fields (`sight_servo.py`)

`field_target_azimuth_deg`/`field_target_elevation_deg` go through the same `optional_numbers`
loop every other optional float on this schema already uses (`mark_azimuth_deg`,
`error_azimuth_deg`, etc.): `None` passes through, a `bool` is explicitly rejected before the
`(int, float)` check (so `True`/`False` can't silently become `1.0`/`0.0`), anything else
non-numeric raises `SightServoParseError`. `mark_clipped` is a strict `isinstance(..., bool)`
check, same shape as the existing `stalled` field. Both match this module's established pattern
exactly — no weaker check was introduced for the new fields than for the old ones.

**One thing checked and found not applicable, by the same reasoning
`project_bl_b80_v2_t_sim_unbounded_in_stated_bounds` used for `t_sim`**: none of the three new
fields get an `isfinite` check, only the bool/numeric-type check above. For `t_sim` that mattered
because a non-finite inbound value fed a `clamp()` subtraction inside the Lua control loop — an
attacker-reachable input shaping a safety-relevant computation. Here the direction is reversed:
`field_target_*`/`mark_clipped` are *outbound* telemetry, computed in `Export.lua` by
`sight_clip_to_field_body_deg` from an already-gimbal-clamped setpoint (`math.max`/`math.min`
against ±60°/+20°/−15° immediately above, in the diff) and bounded by construction (`scale` is a
`math.min` chain starting at `1.0`, so `field_target` can only ever be the setpoint scaled down,
never expanded or driven non-finite by this function). Confirmed no body-layer code reads these two
fields back into any computation at all — `grep -rln "field_target\|mark_clipped" body-layer/src`
returns nothing; the only body-layer reference is a `CLAUDE.md` doc note that they land on the
existing per-run trace log as additional write-only columns. So there is no downstream arithmetic
on this project's own side for a non-finite value to corrupt, and nothing a LAN attacker could
inject here anyway, since this value only ever flows DCS → collector → HTTP `GET` response, never
back into a `POST`. A finite-check would be free defence-in-depth but isn't closing a reachable
path; not a required fix.

### Bounds on values sent to DCS commands (does any path command the sight beyond intended limits)

This is the one question with a genuine before/after to compare, since v3's whole point is
tightening exactly this bound. Confirmed by reading `run_sight_servo` and the final write clamp
(unchanged, line ~1791-1792: `write_az_cmd`/`write_el_cmd` clamped to `[-1.5, 1.5]` raw units
regardless of mode):

- **Before (the bug this stage fixes):** the `closed` branch's `u_az`/`u_el` had no saturation at
  all ahead of that final clamp, and the mark-validity gate checked the *setpoint* against the 60°
  gimbal envelope rather than the mark's own ~4.3° window — so a 20° simulated direction produced
  a ~47° command before the write clamp, i.e. the servo could be driven hard against its mechanical
  stop by a target the mark geometrically cannot represent. (This is the field-of-regard-shaped
  defect the plan documents as occurrence 5 of a recurring class — correctness, not itself a
  security finding, but relevant context for why "bounds on commands" is the right thing to check
  here.)
- **After:** `closed` mode's error term is now `field_target − mark`, and `field_target` is
  radially projected to sit *inside* the ASP-17's own ~3.8°-margined field by construction — so the
  achievable error, and hence `u`, is structurally bounded to a few degrees before the unchanged
  final clamp ever has to act. `homing` mode (the renamed/narrowed former open-loop branch) adds an
  explicit `±HOMING_SAT_DEG = 6.0` clamp on `u` that didn't exist for every path before. Net effect:
  this stage **strictly tightens** what can reach the write clamp in every mode; it does not open a
  new way to command the sight beyond its limits. No path in the diff bypasses the ±1.5 final
  clamp, and no new write op was added.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/src/schema/sight_servo.py:88-96` | new optional-float fields, no `isfinite` check | Outbound-only telemetry, bounded by construction at the Lua source, never read back into computation anywhere in this repo (confirmed by grep) — see reasoning above | None |
| `aircraft-layer/dcs-export/Export.lua` (`push_slew_trace`, `run_sight_servo`) | new fields appended to existing outbound status/log lines | Numeric/boolean only, formatted through existing safe helpers, no string injection, no new file path | None |
| `aircraft-layer/dcs-export/Export.lua` (`run_sight_servo`'s `closed`/`homing` split) | command bound on the real sight axis | Strictly tighter than the prior version; final ±1.5 write clamp unchanged and still the backstop in every mode | None |
| Collector TCP listener / HTTP API bind | what a LAN port scanner reaches | Unchanged by this diff (no hunk in `src/collector/server.py` or `src/api/server.py`) | None — pre-existing `AC-B11` (unbounded `Content-Length`) still open, not reopened or expanded here |

### Verdict

APPROVED

No required fixes. This stage adds no new dependency, no new network-reachable surface, no code
execution path, and no log-injection surface; the one behavioural change that touches "could this
command the sight beyond intended limits" tightens the existing bound rather than loosening it.

### Findings filed or explicitly not filed (closing step)

- No new backlog-worthy finding from this pass. The one pre-existing item this diff's area
  borders — `AC-B11` (unbounded `Content-Length` on every `TelemetryAPIServer` `POST` handler) —
  is untouched by this diff (no `POST` handler added or changed here) and stays filed as-is; not
  re-raised, per this role's own "don't flag pre-existing issues as blockers for the current
  feature" rule.
- The `field_target_*`/`mark_clipped` missing-`isfinite`-check observation above is **not filed,
  intentionally**: it is not a reachable path (outbound-only, never consumed downstream in this
  repo today), so there is nothing to schedule — filing it would create backlog noise with no
  action attached. If a future stage starts consuming these fields in body-layer computation, add
  the `isfinite` check at that time, the same way `t_sim`'s was added when it became load-bearing.

### Passed to Reviewer

(For completeness — correctness, not security, so no verdict given here.) `review-v3.md` already
flags two non-security loose ends on its own: Flight B's edge-park test card not yet written, and
`ASP17_FIELD_EL_HALF_DEG`/`ASP17_FIELD_MARGIN_DEG` being unmeasured placeholders. Nothing further
noted from this pass.
