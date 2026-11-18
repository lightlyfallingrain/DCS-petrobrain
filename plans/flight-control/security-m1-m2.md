## Security Deep Analysis: BL-16 mode 1 Stages M1+M2 (raw-axis flight control)

Diff `0c206b37..6aa511c2` (merge-base with `main` → the task's tip). Reviewer verdict: APPROVED,
both stages and both fix rounds (`review-m1.md` NEEDS REVISION → `review-m1b.md` APPROVED,
`review-m2.md` NEEDS REVISION → `review-m2b.md` APPROVED). Scope per root `CLAUDE.md`/this role's
own scoping note: internet/LAN security only (code execution, cockpit-write surface, LAN
reachability, prompt injection, dependency/supply-chain, secrets, and this feature's own named
concern — can the player always get the controls back). Player-experience correctness (whether the
control law flies the goal the pilot expects, the `review-m2.md` co-moving-state gap, etc.) is the
Reviewer's territory and is not re-litigated here.

**Worktree note**: this agent's worktree started at `59192cfa`, not an ancestor of the task's tip
`6aa511c2` (`git merge-base --is-ancestor` returned false). Tree was clean, so per the task's own
fallback instruction: `git branch sec-m12 6aa511c2 && git checkout sec-m12`. Confirmed
`HEAD == 6aa511c2` before reading anything.

### Dependency Status

No dependency change. `git diff --stat 0c206b37 6aa511c2` touches only `*.py`, `*.lua`, `*.md`,
`*.toml` (the generated `config/defaults.toml`) and agent-memory files — no `pyproject.toml`/lock
file anywhere in the diff. `aircraft-layer` stays stdlib-only (`math`/`json`/`http.server`), no new
import in `body-layer`'s touched files beyond modules already in the codebase.

### What a LAN port scanner reaches — new surface

Two new endpoints on `TelemetryAPIServer` (binds `0.0.0.0` by design, pre-existing posture):
`GET /flight_control/latest` (read-only, no params, `cache.latest()` or JSON `null` — same shape as
every sibling `/latest` endpoint) and `POST /command/flight_control`. The POST handler is the
feature's real new attack surface and got the most attention below.

**Shape validation at the HTTP boundary is clean against the recurring bug class this project
tracks**: `seq` is checked `isinstance(..., int)` directly (bool excluded, range `[0, 2**31-1]`),
never passed through a raising `int()` conversion. Every `limits`/`goal` numeric field is checked
with `isinstance(x, (int, float))` (bool excluded) **and `math.isfinite(x)`** before being accepted
— this is exactly `[[project_nan_infinity_int_conversion_at_lan_boundary]]`'s known-good shape, not
the known-bad one. `goal.turn`/`goal.level_off`/`goal.alt_ref` are closed-vocabulary/type checks,
no conversion. Confirmed clean by reading `_handle_command_flight_control`, not assumed from the
pattern's name.

**Unbounded `Content-Length`** (`length = int(self.headers.get("Content-Length", "0") or "0")`,
`aircraft-layer/src/api/server.py`'s new handler) reproduces the already-tracked `[[AC-B11]]`
pattern again, by the same structural copy as every other POST handler on this server. Not a new
finding — `AC-B11`'s own 2026-11-17 correction already generalized "every POST handler on this
server", and this is one more instance of the same pre-existing, low/low, not-blocking shape. Not
re-filed.

### Arbitrary code execution / Lua eval

No `eval`/`loadstring`/`dostring`/`dostring_in` of untrusted data anywhere in this diff. The
inbound wire is parsed by `core.lua`'s existing hand-rolled pattern-match extractors
(`extract_json_number_field`/`extract_json_string_field`/`extract_json_bool_field`, the latter new
in this diff but same `string.match` shape as its siblings) — string pattern matching, not a
general parser, not an interpreter. The four effector functions
(`LoSetCommand(CMD[axis], value)`) write only to `CMD = {pitch=2001, roll=2002, pedals=2003,
collective=2087}`, a fixed four-entry table never indexed by anything wire-derived — `axis` in
`write_outputs`'s loop comes from `pairs(FC_AXES_ENABLED)`, a module-local fixed table, never from
parsed JSON. No generalization of the cockpit-write surface beyond what `[[project_cockpit_write_
vocabulary_invariant]]` already accepts for this project (`cockpit_switch` is still the one
deliberate any-device exception; this feature does not touch it or widen it).

### LLM prompt injection

No new text reaches a model prompt in this diff. The wire carries only numbers, a closed four-value
`cmd` enum, a closed two-value `alt_ref` enum, and a closed three-value `turn` int — never free text
read by Petrovich. `fc_release_reason`/`fc_refuse_cause`/`fc_takeover_mode` are closed-vocabulary
status strings Lua itself chooses from a fixed set (`"stop"`/`"refused"`/`"envelope"`/`"dead"`/
`"nan"`/`"too_slow"`/`"on_ground"`/`"lease"`/`"disabled"`/`"heading"`/`"turn"` — grepped every
assignment site, confirmed closed), never echoed from anything a LAN peer supplies. Not applicable
to this feature.

### The handover channel itself — this is the part the task was dispatched to check

Traced every path that can change `fc_mode`, start/stop `write_outputs()`, or change whether a
future `release`/`take`/`arm`/`goal` message is honored. Two real findings, both centered on the
same mechanism: `handle_flight_control_command` treats **every** accepted message — regardless of
`cmd` — as advancing one shared staleness counter (`fc_last_cmd_seq`) and one shared mutable
`limits` table (`fc_limits`), with no notion of *who* sent it. This project's API has no
authentication anywhere (accepted baseline for a single-user LAN project — `cockpit_switch` already
allows arbitrary writes), so this is not a new departure from that baseline, but it interacts badly
with the one safety property this feature is explicitly built around (U2/U10: "no watchdog... the
park-then-unpark lease is the escape if Petrovich dies mid-flight").

**Finding A — a single accepted message can permanently desync the staleness counter for the rest
of the DCS session, silently dropping every subsequent legitimate `take`/`release`/`goal`/`arm`.**

`handle_flight_control_command` (`flight_control.lua`):
```lua
if seq <= fc_last_cmd_seq then return end
-- [limits bound-check loop, can reject-and-return before the next line]
fc_last_cmd_seq = seq        -- bumped for ANY accepted cmd, not just the one the caller intended
```
`seq`'s own HTTP-layer bound is `[0, 2**31-1]` — a single minimal, fully-valid message such as
`{"seq": 2147483647, "cmd": "goal"}` (no `limits`, no `goal` body required — both are optional and
`None` passes every check) is accepted end to end and sets `fc_last_cmd_seq` to the maximum value.
`on_stop()` **deliberately does not reset `fc_last_cmd_seq`** ("a stale, pre-restart command
replayed after a reconnect must still be seen as stale") — so this is not cleared by a mission
restart either, only by `Export.lua` itself reloading (a full DCS restart). From that point,
body-layer's own `wire_seq` (`body-layer/src/belief/flight_control.py`, `wire_seq: int = 0`,
bumped by exactly 1 per send in `body._apply_flight_control`, held only in the in-memory
`CrewConsole` dataclass, never persisted) can never again produce a `seq` greater than
`2**31-1` — every future `take`/`release`/`goal`/`arm` from body-layer is silently dropped by the
`seq <= fc_last_cmd_seq` check for the rest of the DCS session. Confirmed no reconciliation exists:
grepped `belief/flight_control.py`/`body.py` for any read of Lua's own echoed `fc_goal_seq`/
`fc_take_seq` feeding back into `wire_seq` — none; `wire_seq` is purely local and one-directional.

**This is also self-inflicted, with no attacker at all, by the much more mundane case of a
body-layer process restart while mode 1 is anywhere but `off`.** `wire_seq` resets to 0 on every
body-layer restart (plain dataclass default, no persistence); `fc_last_cmd_seq` in the long-lived
Lua VM does not. A routine dev restart mid-flight (this project is in active development, restarted
many times a day per session-start protocol) while mode 1 is `active`/`armed` reproduces the exact
same silent-drop state with no malicious input required — the LAN-reachable version above is a
faster, deliberate way to reach a state that ordinary operation can already reach by itself.

**Finding B — any accepted message can widen `limits.arm_lease_s` up to its HTTP bound (60 s),
directly weakening the one safety margin U10 was built to provide.** `arm_lease_s`'s bound is
`(0.0, 60.0)` at both the HTTP layer and `FC_LIMIT_BOUNDS` in Lua — both accept the full range, no
tighter ceiling anywhere. The user's own design intent (`plan.md`, U10, "ANSWERED 2026-11-18:
approved"): *"a Petrobrain crash while he flies leaves no way to get the stick back short of a
mission restart [without the lease]"* — the lease is deliberately short (3 s default) so that if
body-layer dies, a park-then-wait-then-unpark reliably finds the lease stale and gives the player
the stick back. `handle_flight_control_command`'s `limits` loop applies `arm_lease_s` from **any**
accepted message exactly the same as every other limits field — there is nothing that scopes
"who may widen the escape-hatch window" differently from "who may set the heading goal". A single
message, `{"seq": <valid>, "cmd": "goal", "limits": {"arm_lease_s": 60.0}}`, is fully within both
layers' stated bounds and raises the window from 3 s to 60 s: after this, a player who parks to
recover from a dead/unresponsive body-layer must now wait up to a full minute (not 3 s) before an
unpark is treated as stale rather than re-arming Lua's own last-captured-and-frozen state. This
does not defeat the escape hatch outright (the park gesture itself is not seq-gated — see below —
and an unpark after the lease genuinely expires still refuses), but it meaningfully degrades the
one margin this feature's design explicitly reasons about by name.

**Why this does not reach "Petrovich holds the controls with literally no way back"**:
`run_flight_control`'s self-arm-on-park transition (`is_parked == true and fc_mode in
{"active","taking"}` → `fc_mode = "armed"`, stops calling `run_active_frame` from that point) is
driven directly by `ai_pilot_wheel.is_parked()`, a read of cockpit arg 852 (the AI-pilot-wheel's
own physical stow lever) — **not gated by `fc_last_cmd_seq`, not reachable or blockable through the
command channel at all.** Confirmed this is a genuinely separate physical control from the four
overridden flight axes (1100-1103/1110-1113): grepped every reference to arg 852 and to
`SEAT_ARGS`/`CMD` — disjoint sets. So the physical park-the-AI-wheel gesture remains available to
the player regardless of either finding above; it is exactly the mechanism U2/U10 already name as
the accepted answer to "Petrobrain has died while flying", and both findings above only widen or
degrade the *timing* of that same already-accepted escape, never remove it. This is also why
neither finding escalates to cockpit-write-vocabulary territory (`cockpit_switch`'s already-accepted
any-device exception remains strictly more powerful than anything reachable here).

**Framing**: the project's threat model (root `CLAUDE.md`, user direction 2026-10-21) names "an
infected computer scanning/probing reachable ports" as the realistic LAN actor. Finding A is
reachable with one crafted-but-fully-valid probe of exactly that shape, and degrades the feature's
designed voice/goal channel for the rest of the DCS session (recoverable only by the player's own
physical park gesture, or a full DCS restart) — squarely inside what this role was asked to check.
Finding B needs a similarly trivial single message and specifically undermines a margin the user
reasoned about by name, which is why it is reported with a verdict rather than waived as "no auth on
this API is already accepted."

### Output saturation / NaN handling / rate limiting on the law itself — verified safe

Checked directly, not inferred from the plan's narrative: `law_outputs` clamps every one of the
four axes to `[-1, 1]`; `write_outputs` re-clamps after adding the always-on wobble and before
calling `LoSetCommand`, so nothing outside `[-1, 1]` ever reaches the write. A hostile/huge
`goal.ias_kmh` (HTTP bound `(0, 2_000_000)` — a sanity bound only, far wider than any real IAS) does
**not** produce an output jump: `law_update`'s speed channel clamps the *acceleration* applied
toward the goal (`SPEED_ACCEL_CAP_MPS2`, then `limits.max_accel_mps2`) before integrating it into
`v_ref`, so the commanded rate of change is bounded regardless of how far away the target is —
confirmed by reading the integrator, not assumed. `read_measured` fails every sensor read soft to
`0.0`/a safe default (never `nil` propagating into arithmetic), and `check_envelope`/
`check_unpark_preconditions`/`capture_from_seat` all use the Lua NaN self-inequality idiom (`v ~= v`)
correctly to fail toward refuse/release rather than writing a NaN-derived command. The pause/
huge-frame-time path (`DT_CAP`) re-issues the last command verbatim with `dt=nil` (no rate-limit
division by a near-zero/negative `dt`), matching the plan's own pause row. `release` and the
envelope self-release both stop calling `write_outputs()` from that frame on, with no "re-issue one
last value" path that could outlive the mode change. The unpark-take capture path (`fc_last_stowed_
pilot_capture`) refuses rather than writes a stale/nil capture, confirmed above. None of this is a
finding — recorded because it was the task's explicit focus and is now verified rather than assumed.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/dcs-export/Petrobrain/flight_control.lua:1050-1075` (`fc_last_cmd_seq`) | Any accepted message of any `cmd` bumps the one shared staleness counter, never reset across a mission restart | Finding A — LAN-reachable single message, or an ordinary body-layer restart, silently and permanently (until DCS itself restarts) breaks every future `take`/`release`/`goal`/`arm` from the real sender | Fix recommended, not blocking (see Verdict) |
| `aircraft-layer/dcs-export/Petrobrain/flight_control.lua:1059-1073` (`new_limits`/`arm_lease_s`) | `limits.arm_lease_s` applied from any accepted message, bound only by the generous `[0, 60]` sanity range shared with every other limit | Finding B — widens the window U10 designed to be short, from any LAN sender | Fix recommended, not blocking (see Verdict) |
| `aircraft-layer/dcs-export/Petrobrain/flight_control.lua` (self-arm-on-park, `run_flight_control`) | Physical park gesture, bypasses the command channel entirely | Verified as the real, structurally-independent escape hatch both findings above degrade the timing of but do not remove | None |
| `aircraft-layer/src/api/server.py`, `_handle_command_flight_control` | `math.isfinite`/`isinstance` shape validation on every numeric field, `seq` never passed through `int()` | Matches the established safe pattern | None |
| `aircraft-layer/src/api/server.py`, `_handle_command_flight_control`'s `Content-Length` read | Unbounded body size | Pre-existing `[[AC-B11]]` pattern, ninth-or-later instance, already tracked, low/low | None — not re-filed |
| `flight_control.lua`'s four `LoSetCommand`/`write_outputs` | Cockpit-write surface | Axis table is fixed, never wire-indexed; no eval/loadstring anywhere in the diff | None |
| Output clamps, NaN handling, pause/rate-limit paths (see section above) | — | Verified safe by direct reading | None |
| All new Lua/Python in this diff | secrets/credentials grep | None found | None |

### Verdict

**APPROVED**, with two findings surfaced for the user's own decision rather than blocked — neither
expands this project's already-accepted no-auth-on-LAN baseline or its cockpit-write-vocabulary
invariant, and both degrade (rather than remove) an escape hatch the physical park gesture still
provides independently, confirmed structurally.

**Finding:** A single fully-valid `POST /command/flight_control` message can permanently (for the
rest of the DCS session) desync `fc_last_cmd_seq`, silently dropping every real future command on
this channel — reachable by a LAN probe matching this project's own stated threat actor, and also
reachable by an ordinary body-layer process restart with no attacker involved at all.
**Location:** `aircraft-layer/dcs-export/Petrobrain/flight_control.lua:1050,1075` (the seq-staleness
check applied across every `cmd`); root cause on the body-layer side is `wire_seq`'s lack of
persistence/reconciliation (`body-layer/src/belief/flight_control.py:307`).
**Probability:** low for deliberate LAN exploitation (single-user LAN, no current scanning tool
targets this); low-to-medium for the self-inflicted variant (restarting body-layer mid-flight is
routine during this project's active development, though mode 1 is pre-flight-test as of this pass).
**Impact:** medium — the feature's own designed voice/goal channel goes dead for the rest of the DCS
session; the player is not left with literally no recourse (the physical park gesture is
independent and unaffected), but loses the primary mechanism without necessarily knowing why, and
without any error surfaced anywhere (the drop is silent by design, matching the stale-datagram
posture this channel already wants for ordinary UDP reordering).
**Recommended action:** either (a) have `Export.lua` bound how far a single message may advance
`fc_last_cmd_seq` relative to its current value (reject an implausible jump as malformed rather than
applying it), or (b) have body-layer reconcile `wire_seq` against Lua's own echoed `fc_goal_seq`/
`fc_take_seq` on startup/reconnect (`wire_seq = max(local, remote) + 1`) so a restart cannot regress
behind whatever Lua last accepted — (b) also fixes the self-inflicted variant, which is likely the
more probable trigger in practice.

Options:
  (A) Ignore — document acceptance of this risk for now (LAN-only, single user, pre-flight-test
      feature; mode 1 has not yet passed U7/M0-D).
  (B) Add to todo.md/the aircraft-layer backlog — fix in a future session, before mode 1's first
      live flight test.
  (C) Fix now — one of the two recommended approaches above.
  (D) Stop — do not proceed until resolved.

**Finding:** `limits.arm_lease_s` can be widened to its full `[0, 60]` bound by any accepted
message from any sender on this channel, directly lengthening the window U10 designed to be short
(3 s default) as the margin for "body-layer has died mid-flight".
**Location:** `aircraft-layer/dcs-export/Petrobrain/flight_control.lua:1059-1073`
(`FC_LIMIT_BOUNDS.arm_lease_s`), `aircraft-layer/src/api/server.py`'s
`_FLIGHT_CONTROL_LIMITS_BOUNDS["arm_lease_s"]`.
**Probability:** low — same LAN-only/single-user reasoning as Finding A; this one has no
self-inflicted variant (body-layer itself only ever sends its own tuned default via
`flight_control_limits()`, never 60).
**Impact:** low-to-medium — does not remove the escape hatch (the physical park gesture is
independent, confirmed above), but can make the recovery wait up to 20x longer than the user's own
chosen margin, with nothing telling the player why an unpark "took" again sooner than they expected.
**Recommended action:** scope `arm_lease_s`'s own Lua-side ceiling tighter than the shared
sanity-bound pattern used for the other limits (e.g. a dedicated, smaller hard ceiling in
`FC_LIMIT_BOUNDS`, independent of whatever body-layer's own `tuning.py` range for this constant
ends up being), since this is the one limit whose value is itself a safety margin rather than a
flight-behaviour tuning knob.

Options: same four as above.

### Not filed (intentionally)

Per this task's own dispatch instructions ("backlog-worthy low items listed with suggested IDs left
for the main loop to mint" — overriding this role's usual self-mint step for this pass), both
findings above are left for the main loop to mint as `aircraft-layer/ROADMAP/AC-B<n>` entries
(next two free numbers per `.claude/scripts/mint-id.sh AC-B --list`) rather than minted here. Neither
is filed yet; both need an ID before this pass's closing step is satisfied.

The pre-existing `[[AC-B11]]` unbounded-`Content-Length` instance on this feature's new handler is
not re-filed — it is already covered by that entry's own 2026-11-17 correction, which generalized
to "every POST handler on this server."

### Passed to Reviewer

- Nothing new — `review-m2.md`'s own co-moving-state gap (goal commanded during the one-frame
  "taking" window, `fc_goal_heading` reporting a value the law never actually received) is a
  correctness finding already surfaced and fixed in that review round; not re-examined here since
  it carries no security content (closed wire vocabulary throughout, confirmed above).
