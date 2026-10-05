## Security Deep Analysis: dcs-driven-los (X-B29), Stages 1-3

Reviewed `feature/dcs-driven-los`, tip **`a849f8d88dbd346121656e41c2b7c0f68978d94e`** (confirmed via
`git rev-parse feature/dcs-driven-los` before reading — this task's worktree landed on `main`'s tip
`01d84d0e622469e67a954136cc2e66bb9033b339`, as expected, so all reading below ran against an
isolated snapshot: `git archive feature/dcs-driven-los | tar -x -C <scratch>`). `plans/dcs-driven-
los/plan.md` exists on `main` (pre-dates the branch's §7-§17 revisions); `security-plan-review.md`,
`review.md`, and `implementation.md` — all read during this analysis — exist **only on the feature
branch**. This file (`security-deep-analysis.md`) is new and likewise branch-only until merged.

### Dependency Status

No dependency change. Confirmed by my own Mode 1 review and independently re-confirmed here: the
feature adds a Lua Hook listener (stdlib `LuaSocket`, already vendored/in use), a FastAPI-free
`BaseHTTPRequestHandler` endpoint pair on the existing collector stack, and schema/client code in
already-present packages. No `pip install`, no new Lua `require`.

### Coordinator follow-up: is `hour` (bearing) clamped as totally as `fov_half_deg`?

Yes, identically. Both call sites in `_applyLookDirection`
(`aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua:403-404`) go through the same
`_safeClampInt` function with no special-casing for `hour`:

```lua
local hour = _safeClampInt(hourRaw, HOUR_MIN, HOUR_MAX, HOUR_DEFAULT)
local fovHalfDeg = _safeClampInt(fovRaw, FOV_MIN_DEG, FOV_MAX_DEG, FOV_DEFAULT_DEG)
```

`_safeClampInt` (lines 368-388) checks `type ~= "number"` → NaN self-inequality → `±math.huge` →
ordinary min/max → round, in that order, for *every* call site. There is no `% 360` anywhere in this
file — `hour` is clamped directly into `[0, 11]`, never wrapped. That matters here because a modulo
is exactly the operation that looks natural for a "compass value" and that silently propagates NaN
(`0/0 % 360` is still NaN in Lua, since `%` is defined via `floor` division on the same IEEE values).
This codebase doesn't have that shape of bug: both substitutions reach `string.format`'s `%d` through
the identical total guard, not through a looser path that "looked bounded already." Confirmed, not
assumed — I read the clamp call sites directly rather than taking the symmetry on the plan's word.

**Boundary to re-review, not re-litigate now, per the coordinator's note:** the two current
substitutions are integers reached by a total clamp, which is what makes the splice safe. A future
`look_around(x_coord, y_coord, alt)` variant would change the substitution count *and* the value
class — floats/coordinates, not small bounded integers — which is a different safety argument
entirely (range clamping an unbounded float doesn't close the same gap a `%d`-only format string
closes automatically; `%f`/`%g` specifiers can emit different things than `%d` can, and "world
coordinate" has no natural `[min, max]` the way `hour`/`fov_half_deg` do). If that variant is ever
built, it needs a fresh plan-stage security review of its own — this analysis does not pre-clear it.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `petrobrain-line-of-sight-hook.lua:207` (`SET_LOOK_TEMPLATE`) | Two `%d` substitutions into `dostring_in` text | Both substitutions pass through the identical total `_safeClampInt` before formatting; `%d` can only emit `-`+digits regardless of input (Lua 5.1 `sprintf` wrapper). `LOS_CODE` itself (lines 229-335) is a fully fixed literal — traced every line, no runtime value enters it. The template is guarded by `test_set_look_template_has_exactly_two_percent_d_and_nothing_else`. | None — deviation from plan review's "exactly one %d" is sound as built. |
| `petrobrain-line-of-sight-hook.lua:425-443` (`pollLookDirection`/`_applyLookDirection`) | Bounded drain, single coalesced bridge call | Drains ≤20 datagrams/frame, applies only the last successfully-decoded one, one `dostring_in` call regardless of burst size. `pcall`-wrapped; failure leaves prior globals untouched (fail-to-stale-wedge, not fail-to-corrupt). | None. |
| `aircraft-layer/src/api/server.py:442-503` (`_handle_command_look_direction`) | Unbounded `Content-Length` read, same shape as 3 pre-existing sibling handlers | `int(self.headers.get("Content-Length","0") or "0")` is read with no upper-bound check before `rfile.read(length)`, identical to `_handle_text_push`/`_handle_command_petrovich_search`/`_handle_audio_play`. Not a new weakness this feature introduces — it's the established pattern on this LAN-only, single-user collector. `hour`/`fov_half_deg` validation itself is correct and tight: both explicitly exclude `bool` before the `isinstance(int)`/range check (defeats Python `bool`-is-`int` subtyping), mirroring `_VALID_SEARCH_MODES`'s pattern. | None required this feature; pre-existing posture (previously noted in the audio-adapter audit as RECOMMENDED, not required). |
| `aircraft-layer/src/collector/line_of_sight_receiver.py:107-146` (`_handle_datagram`) | Malformed/oversized/type-confused envelope handling | Bounded `recvfrom` buffer (65536), strict type checks on `payload`(str)/`bridge_call_ms`(int\|float, bool excluded) before any parse, `LineOfSightParseError` caught and the datagram dropped+logged — never raises into `serve_forever`'s loop. | None. |
| `aircraft-layer/src/schema/line_of_sight.py:107-153,180-200` (`from_wire`/`_parse_entry`) | String-split parsing of a Hook-sourced payload | Exact split-count checks (`len(parts) != 7`, `len(fields) != 3`) raise `LineOfSightParseError` rather than silently mis-indexing; `_parse_bool01` rejects anything but literal `"0"`/`"1"`. One documented, pre-existing-pattern limitation: a `unit_name` containing a literal `;` would misalign the top-level `entries_str.split(";")` and raise, dropping the *entire* poll's snapshot (not just that unit) — same accepted limitation `unit_velocity.py`'s parser already carries, and mission-editor-authored unit names are not attacker input in this project's single-player scope. | None — fails closed (whole datagram dropped), consistent with existing precedent. |
| `body-layer/src/perception/naked_eye_source.py:1066-1132` (`_resolve_los_by_unit_name`) | Join of untrusted collector payload onto belief-adjacent candidates | Every field re-type-checked at this boundary independent of the schema layer already having checked it (`isinstance(verdict, dict)`, `isinstance(building_clear, bool)`, duplicate-`unit_name` resolved to unresolved rather than last-wins-silently). Any failure mode (no snapshot, stale skew via `LOS_MAX_AGE_S`, malformed verdict) degrades uniformly to "absent from `resolved`" → gate 4 falls back to the offline primitive. `hour_used`/`fov_half_deg_used` are returned and recorded in the trace on every path, including failure paths, so a degraded join is visible in `detection_trace`, not silent. | None. |
| `body-layer/src/belief/contacts.py:1359-1389` (engagement term gate 4) | Fail-open rewrite replacing deleted `_threat_has_los` | Three-branch logic (out-of-envelope resets masking state; no-fresh-verdict fails open; fresh `False` only clears danger after `LOS_MASK_CONFIRM_S` continuous masking) matches plan §11a exactly. Grepped the whole of `body-layer/src/` for `_threat_has_los`/`LOS_UNCERTAINTY_SAMPLES`/`los_clear=` — only remaining hits are the new `live_los_clear=` keyword assignments; nothing of the deleted mechanism survives in a weakened form. | None. |
| `body-layer/src/detection_trace_writer.py` | No-omniscience boundary | Grepped for `los`/`LOS` — zero references. Confirmed independently (not re-trusted from plan/review text) that this module remains the single deliberately-dual-sighted, read-only module and the new LOS fields never reach it. | None. |

### No-omniscience adversarial trace

Traced every hop the single crossing boolean takes, end to end:

`world.getPlayer()`/`unit:getPoint()` (true position, Hook-side, never leaves the mission-scripting
state as coordinates) → `buildingClear`/`terrainClear` booleans → wire string `name:b01:t01` →
`LineOfSightVerdict(building_clear, terrain_clear)` (schema, aircraft-layer) → joined by `unit_name`
in `_resolve_los_by_unit_name` → `WorldObjectCandidate.live_los_clear` property
(`building_clear and terrain_clear`, line 1062-1063) → `visibility.check_visibility` gate 4 (reads
the bool, records `GateOutcome.TERRAIN_LOS` on `False`, never forwards the bool itself into any
belief-visible return) → `Observation.live_los_clear` → `Percept.live_los_clear` (pass-through) →
`Contact.live_los_clear` (overwritten in `record()`/`from_percept()`, never unioned/accumulated).

Nothing else crosses this boundary: no DCS object id, no raw position, no `hour_used`/
`fov_half_deg_used` (those stay in `detection_trace` only — and even if they did reach belief, they
describe the player's own commanded wedge, not ground truth about a target, so they wouldn't be an
omniscience leak regardless). `building_clear`/`terrain_clear` individually also never reach belief
— only the joined `live_los_clear` single bool does, exactly as the plan intends.

### Cost-as-safety

The cone filter (`delta <= fovHalfDeg` inside `LOS_CODE`, lines 274-277) is the intended cost bound;
`MAX_SIGHTLINES_PER_CALL = 128` is the independent backstop, applied after the wedge filter and the
nearest-first sort (`sightlinesComputed >= 128 then break`, line 322). If the wedge filter were
wrong in a way that admitted everything in the 10 km bubble, the 128 cap still holds — it does not
depend on the wedge filter being correct, it depends only on the candidate list being iterated in a
loop that checks the counter before each sightline pair, which it is. The duplication Reviewer
flagged (`local MAX_SIGHTLINES_PER_CALL = 128` vs. the hardcoded `128` literal inside `LOS_CODE`,
with no mechanical guard tying them) is a real maintenance gap but not an exploitable one in this
project's scope: drifting the two apart could only ever make the *outer* Lua value stop matching
documentation/logs, or make the inner cap silently diverge from the named constant — in neither
direction does a mismatch remove the backstop itself, since the inner literal is what actually bounds
the loop regardless of what the outer `local` says. Agree with Reviewer that this is optional, not a
required fix.

### The `None` fallback branch — can it be induced silently?

Traced every path that produces `candidate.live_los_clear is None` (no feed yet, Hook not running,
stale skew beyond `LOS_MAX_AGE_S`, malformed/missing `verdicts`, duplicate `unit_name`, wrong-typed
verdict fields, unit simply outside the wedge). Every one of these degrades uniformly to "absent," and
`hour_used`/`fov_half_deg_used` plus `units_in_bubble`/`units_in_wedge`/`sightlines_computed` are
recorded in the trace on every poll regardless of outcome — so a systematic failure (e.g. the Hook
script silently crashing, or every verdict being malformed) is visible as a sustained run of null/zero
observability fields in `detection_trace`, not hidden. There is no automated alerting on that signal
today, which is a correctness/observability gap rather than a vulnerability, and is proportionate to
flag rather than block:

**Finding:** no live monitoring or test asserts that `units_in_wedge`/`sightlines_computed` stay
non-trivially nonzero over a sortie when the look-direction channel is supposed to be active — a
silent full-session fallback to the 12 m-tolerance offline primitive (e.g. Hook script fails to load,
`autoexec.cfg` opt-in missing) would currently only be caught by a human reading `dcs.log` or running
`sortie-log-triage`.
**Location:** `body-layer/src/perception/naked_eye_source.py:1066-1132`, `detection_trace` fields.
**Probability:** low — this is the same "watch `dcs.log` for `PetrobrainLineOfSight` lines" caveat the
file's own header already states for the `dostring_in` opt-in generally, not a new gap this feature
introduces beyond that existing caveat.
**Impact:** low — correctness/coverage regression (reverts to the pre-existing, already-reviewed
12 m-tolerance primitive), never a correctness-in-the-dangerous-direction failure (fail-open posture
is unchanged either way), never an omniscience leak.
**Recommended action:** no action required now; worth a `sortie-log-triage` check added opportunistically
later (not blocking DoD).

Options:
  (A) Ignore — document acceptance of this risk
  (B) Add to todo.md — fix in a future session
  (C) Fix now — I'll address it before continuing
  (D) Stop — do not proceed until this is resolved

### Verdict

**APPROVED**

Both Security plan-review required fixes are correctly implemented and independently verified in the
built code (not re-trusted from the Reviewer's account): the NaN/Inf-guarded total clamp applies
identically to both substitution points, and the receive loop coalesces to one `dostring_in` call per
frame regardless of burst size. The declared one-vs-two-`%d` deviation is sound — confirmed by reading
the clamp call sites directly, including the coordinator's specific follow-up on the bearing/`hour`
path, which uses the identical guard with no weaker modulo-based path. No-omniscience holds under an
end-to-end adversarial trace: exactly one boolean crosses perception→belief, nothing else. The deleted
mechanism left no weakened remnant. The new LAN surface's validation is tight and bool-safe; its
`Content-Length` posture matches existing, already-accepted sibling handlers rather than introducing a
new gap. The one new item above (fallback-visibility observability) is low/low and offered per the
Risk Communication Format, not blocking.

### Required Fixes (if any)

None.
