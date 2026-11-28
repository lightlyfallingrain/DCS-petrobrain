# BL-16 M3 (terrain floor and look-ahead) — Security Deep Analysis

Mode 2, once for this batch. Diff reviewed: `ca0bcb50578ec9a9022d59b8dff0bc2de81dc75c..0347b8c79b691e465c6d3c2b4bd23e8120af5b02`
(HEAD fast-forwarded cleanly from `a29eff71` into this worktree; no conflicts, no archive fallback
needed).

Context, per this role's scope: single-user, LAN-only DCS World flight-sim add-on. Threat model is
(1) malicious code in a dependency and (2) an infected/misbehaving box on the same LAN probing
reachable ports — not a remote internet adversary. Findings below are scoped to that model only;
player-experience correctness is Reviewer's territory and is out of scope here (none spotted in
this diff worth a "Passed to Reviewer" line — `review-m3.md`'s own required fixes already cover the
law/test gaps, which are correctness, not security).

Inputs read in full: `plans/flight-lift-vector/plan.md` "M3 amendment (2026-11-28)" section E;
`implementation-m3.md`; `review-m3.md` (both the original review and the re-review/fix pass —
important: that review's own safety argument for the `terrain` relay field has a gap, see Finding 1).
Prior relevant memory: `project_dostring_in_numeric_splice_naN_clamp_gap.md`,
`project_expected_area_look_probe_points_deep_analysis.md`,
`project_bl16_flight_authority_nan_int_crash.md`, `project_bl16_lv3_pure_lua_internal_no_wire_surface.md`.

## Dependency Status

No dependency change. This batch touches only `aircraft-layer` (Python stdlib + Lua) and
`body-layer` (stdlib, `math`, `tuning`) — no new import anywhere in the diff.

## Surfaces checked

### 1. `terrain_points` Hook op — the task's named "most important surface" — CLEAN

`aircraft-layer/dcs-export/petrobrain-line-of-sight-hook.lua`'s new `_applyTerrainPoints` builds the
`net.dostring_in("scripting", ...)` snippet from `SET_TERRAIN_TEMPLATE`, a fixed-shape template with
exactly `2 + 2*32 = 66` `%d` conversions and no other format specifier — mechanically enforced by
`test_set_terrain_template_has_exactly_sixty_six_percent_d_and_nothing_else` (reads the literal out
of the file and asserts the directive list). Every value spliced into it (`seq`, `n`, every `x`/`z`
pair) passes through `_safeClampInt` first, which is the **total**, correct form (explicit
`value ~= value` NaN check, explicit `+math.huge`/`-math.huge` checks, before any min/max
comparison) — this is exactly the form `project_dostring_in_numeric_splice_naN_clamp_gap.md` says a
naive `math.max(math.min(...))` is not, and this code does it right. `%d` output can only ever be
`-`+digits, so there is no string-injection path regardless of input; the only question was clamp
totality, and it's total. Inbound JSON decode (`JSON:decode(data)`) is `pcall`-wrapped, so a
malformed datagram cannot crash the Hook. This reproduces the already-approved `probe_points`
pattern (`project_expected_area_look_probe_points_deep_analysis.md`) with no new gap.

### 2. `POST /command/terrain_points` (collector API) — CLEAN

`aircraft-layer/src/api/server.py`'s `_handle_command_terrain_points`: `seq` bounded to
`[0, 2**31-1]` with `bool` excluded from passing as `int`; `points` bounded to a list of at most
`MAX_TERRAIN_POINTS` (32) `[x, z]` integer pairs, each coordinate bounded to
`±_TERRAIN_POINTS_COORD_ABS_MAX` (2,000,000), `bool` excluded the same way. Matches the already-
reviewed `probe_points` handler's shape exactly. `CommandSendError` on send failure returns `500`,
never raises unhandled.

### 3. `schema.line_of_sight.TerrainAnswers.from_wire` — CLEAN

Correctly applies this project's standing non-finite-at-a-boundary rule: `math.isfinite(height)`
before accepting a value, bounded index (`0 <= index < MAX_TERRAIN_POINTS`), and the whole `terrain`
field is dropped (never guessed) on any parse error — the caller catches `LineOfSightParseError` and
sets `terrain = None`, leaving the rest of the snapshot untouched. This is the pattern the
`flight_authority.py` NaN-crash finding (`project_bl16_flight_authority_nan_int_crash.md`, fixed on
an earlier BL-16 batch) says every LAN-JSON boundary needs; this one has it from the start.

### 4. `body-layer/src/belief/terrain_ahead.py` — CLEAN

`build_terrain_relay` re-checks `isinstance`/`math.isfinite` on every height it reads back from
`GET /line_of_sight/latest`, even though the aircraft-layer side already checked it — correct
"don't trust the upstream check across an HTTP/JSON hop" posture, matching this project's own
standing rule.

### 5. `flight_control.lua`'s `parse_terrain_relay` and the `terrain` flight-lease field — two findings

This is the direction the first four items are not: `terrain` on `POST /command/flight_lease` is a
**plain string field on an unauthenticated collector endpoint**, validated server-side by a regex
(`_TERRAIN_RELAY_PATTERN`) and a length cap, then forwarded verbatim over UDP and parsed by
`parse_terrain_relay` in `flight_control.lua`. Nothing stops a LAN actor from calling this endpoint
directly with a hand-crafted `terrain` string that never went through `belief/terrain_ahead.py`'s
own composition at all.

**Finding 1 (Low probability / Low impact) — `x`/`z` world coordinates in the `terrain` relay carry
no magnitude bound, only `h` does; the existing review's safety argument doesn't cover the actual
overflow mechanism.**

- `aircraft-layer/src/api/server.py`'s `_TERRAIN_RELAY_PATTERN` (`^-?\d+\|(-?\d+(\.\d+)?,...)*$`)
  bounds total string length (4096 chars) but places **no digit-count limit on any individual
  number**. `flight_control.lua`'s `parse_terrain_relay` (lines ~494-529) checks every coordinate
  for NaN (`x == x`) but has **no magnitude check on `x`/`z`** — only `h` got one, added in the M3
  re-review (`review-m3.md`'s "2b", confirmed fixed: `math.abs(h) < 1e5`).
- `review-m3.md` dismisses this as low-risk because *"the lease `terrain` field's own regex
  (`_TERRAIN_RELAY_PATTERN`) cannot carry an 'inf'/'nan' token."* That's true for a **literal**
  `"inf"`/`"nan"` substring, but it is not the only way to produce a non-finite Lua number from this
  input: a sufficiently long all-digit string (e.g. ~310+ nines) is valid under the regex, and
  Lua's `tonumber` on it overflows IEEE-754 double parsing to `math.huge` — a legitimate decimal
  literal, not an injected token. Within the 4096-character cap there is room for such a string on
  `x` or `z` (an entry like `"0|999...9,0,0"` with ~4000 nines easily fits). The re-review's stated
  reasoning does not rule this mechanism out, because it never considered it.
- **Traced the consequence, not just the gap.** `±math.huge` for `x` (or `z`) propagates into
  `fc_terrain.points`, then into `run_active_frame`'s projection (`flight_control.lua` ~L3460-3464):
  `dx = point[1] - measured.pos_x` → `±inf`; `d = dx*nose_x + dz*nose_z`. `law_terrain_w_floor`
  (~L984-1006) then gates every point on `type(d) == "number" and d > 0.0` before using it — `d ==
  math.huge` passes that gate, but the resulting `w_i = (r - a_asl) / tau` where `tau = max(d/v_f -
  lead, tau_min)` evaluates to `tau = math.huge`, so `w_i = finite/huge ≈ 0.0` — a near-zero,
  harmless contribution to the `max()` the function takes over all points. `d == -math.huge` fails
  the `d > 0.0` gate outright and the point is simply skipped, same as any other out-of-range point.
  **So this is not exploitable today** — but the protection is an incidental interaction of two
  guards written for a different purpose (the NaN-safe ground-speed gate and the `d > 0.0` reach
  gate), not a declared bound on the input itself. A later change to `law_terrain_w_floor` or the
  projection (e.g. one that divides by `d` directly, or drops the `d > 0.0` gate for a "behind
  ownship" case) could silently regress this into a bad or garbage climb command, still driven by
  unauthenticated LAN input, with no test anywhere currently exercising it.
- **Recommended fix**: the same bound `h` already has, applied to `x`/`z` at both layers — e.g.
  `|x|, |z| < _TERRAIN_POINTS_COORD_ABS_MAX` (2,000,000, the bound the *other* direction of this
  same channel, `probe_points`/`terrain_points`'s own request validation, already uses) in both
  `_TERRAIN_RELAY_PATTERN`'s consuming code (`server.py`) and `parse_terrain_relay` (`flight_control.lua`).

**Finding 2 (Low probability / Low impact) — the `terrain` relay's point count is unbounded in
practice; the server comment's stated bound does not match what the code checks.**

- `aircraft-layer/src/api/server.py`'s comment on `_TERRAIN_RELAY_MAX_LEN`/`_TERRAIN_RELAY_PATTERN`
  states: *"Generous sanity bounds, same posture as every other wire clamp in this file —
  `_TERRAIN_POINTS_MAX_POINTS` points, each coordinate/height a finite number..."* — but the actual
  check is a regex plus a **4096-character total length cap**, with no check anywhere on the number
  of `;`-separated entries. `MAX_TERRAIN_POINTS`/`_TERRAIN_POINTS_MAX_POINTS` (32) is imported into
  this file and used by the *other* direction (`/command/terrain_points`'s own `points` list), but
  never referenced by the `terrain`-relay validation path at all.
- `flight_control.lua`'s `parse_terrain_relay` loop (`for entry in rest:gmatch("[^;]+") do ... end`)
  has no truncation, unlike the Hook's own `_applyTerrainPoints` (which explicitly clamps `n` to
  `MAX_TERRAIN_POINTS`). A minimal entry is `"0,0,0;"` (6 chars); within the 4096-char budget an
  unauthenticated `POST /command/flight_lease` can carry on the order of ~680 points — more than
  20x the documented/intended 32 — all appended unbounded into `fc_terrain.points` and iterated
  every `law_update` step (gated to `flight_profile.ACTIVE.law_hz`, not every frame).
- **Impact assessed as low**: no crash (Lua tables grow dynamically), no unbounded memory (the
  wire string itself is capped at 4096 bytes, so the blow-up factor is small in absolute terms —
  a few hundred extra `{x,z,h}` triples, a few hundred extra loop iterations in a ~1 Hz-gated step),
  and `law_terrain_w_floor` is a simple linear scan with no quadratic behavior. This is a
  documentation/validation-intent mismatch more than a resource-exhaustion risk at this scale, but
  it is still a wire boundary that does not enforce the bound its own comment claims, worth closing
  the same way `_applyTerrainPoints` already does for the sibling op (truncate, don't just cap
  total length).
- **Recommended fix**: either reject a `terrain` string whose entry count exceeds
  `_TERRAIN_POINTS_MAX_POINTS` at the `server.py` validation layer, or truncate in
  `parse_terrain_relay` the way `_applyTerrainPoints` truncates `n` in the Hook script.

### 6. `core.lua`'s new `extract_json_raw_string_field` — CLEAN

Pure `string.match` extraction (`"field_name"%s*:%s*"([^"]*)"`) over this codebase's own
self-generated JSON text, bounded by `max_len` before being treated as present at all. It is not a
code-execution path and never feeds a `dostring_in` splice — it only feeds `parse_terrain_relay`'s
own string parsing (Finding 1/2's subject, already covered above). No general-purpose unescape, no
new injection surface.

### 7. `AC-B11` reproduced again — informational, not a new finding

`_handle_command_terrain_points` reproduces the same unbounded-`Content-Length`-then-`rfile.read`
shape every POST handler in `aircraft-layer/src/api/server.py` already has (now 13 occurrences
counting this one). Already filed and repeatedly re-assessed low/low, not re-filed here — see
`aircraft-layer/ROADMAP/AC-B11.md`'s own correction log, which should get one more line noting the
count went from 12 to 13 with this handler (docs-only, left to a follow-up rather than edited by
this pass per the "no roadmap edits" scope of this dispatch).

## Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/src/api/server.py` (`_TERRAIN_RELAY_PATTERN`, ~L472-477) + `aircraft-layer/dcs-export/Petrobrain/flight_control.lua:498-528` (`parse_terrain_relay`) | No magnitude bound on relayed `x`/`z` (only `h` bounded) | Low/Low — currently neutralized incidentally by `d > 0.0` gate + `tau = d/v_f` division, not by a declared bound; not exploitable today but fragile | Recommended fix, not blocking (Finding 1) |
| `aircraft-layer/src/api/server.py` (~L472-477) + `flight_control.lua:507` (`gmatch("[^;]+")` loop) | Point-count unbounded in the relay field despite a comment claiming `MAX_TERRAIN_POINTS` bound | Low/Low — no crash, bounded blow-up (~680 vs. 32 points), but validation doesn't match its own stated intent | Recommended fix, not blocking (Finding 2) |
| `petrobrain-line-of-sight-hook.lua` `_applyTerrainPoints`/`SET_TERRAIN_TEMPLATE` | New `dostring_in` splice | Clean — total `_safeClampInt`, mechanically-asserted `%d`-only template, matches approved `probe_points` pattern | None |
| `server.py` `_handle_command_terrain_points` | New POST handler | Clean validation (seq/points/coords bounded, bool excluded); reproduces `AC-B11`'s pre-existing unbounded-`Content-Length` shape | None (cite `AC-B11`) |
| `schema/line_of_sight.py` `TerrainAnswers.from_wire` | LAN-JSON boundary | Clean — `math.isfinite`, bounded index, malformed → whole field dropped | None |
| `belief/terrain_ahead.py` `build_terrain_relay` | HTTP/JSON boundary re-check | Clean — re-validates `isfinite` independently of the upstream check | None |

## Verdict

**APPROVED, no blocking findings.**

Findings 1 and 2 are both Low probability (requires a LAN actor deliberately crafting a payload
that bypasses body-layer's own composer and calling an internal collector endpoint directly) / Low
impact (traced concretely: no crash, no RCE, no unbounded resource growth, and the one currently-
reachable consequence of Finding 1 is a near-zero, harmless term in a `max()` — not a floor bypass).
Neither rises to "confirmed exploitable" or "probable risk" under this role's blocking criteria.
Presented per the Risk Communication Format below rather than blocking DoD.

**Finding 1 — Risk:**
Unauthenticated `POST /command/flight_lease` can carry a `terrain` string whose `x`/`z` values
overflow to `±math.huge` in Lua, bypassing the existing review's "can't carry an inf/nan token"
reasoning via ordinary decimal-literal overflow rather than a literal token.
**Probability:** low — requires a LAN actor who already knows the internal wire format and
deliberately crafts a payload; the project's threat class 2 (infected box scanning ports) would
need to go further than scanning to exploit this.
**Impact:** low — traced to a currently-harmless outcome (near-zero `w_i` term or a skipped point),
not a demonstrated bad command; risk is in future code changing the incidental protection, not in
present behavior.
**Recommended action:** add `|x|, |z| < _TERRAIN_POINTS_COORD_ABS_MAX` checks alongside the
existing `h` bound, at both the `server.py` regex-consuming code and `parse_terrain_relay`.

Options: (A) Ignore — document acceptance / (B) Add to todo or backlog for later / (C) Fix now /
(D) Stop until resolved. Given low/low and a one-line fix shape, (B) seems proportionate, but this
is the user's call.

**Finding 2 — Risk:**
The `terrain` relay field's point count is not bounded to match its own documented intent
(`MAX_TERRAIN_POINTS`/32), allowing ~680 points from an unauthenticated request instead.
**Probability:** low — same actor/knowledge requirement as Finding 1.
**Impact:** low — no crash, bounded blow-up, no quadratic cost downstream.
**Recommended action:** truncate in `parse_terrain_relay` (mirroring `_applyTerrainPoints`) or
reject an over-count string in `server.py`.

Options: same four as above; (B) or (C) both proportionate.

## Findings ledger (closing step)

**Not filed, intentionally.** This dispatch's own scope (orchestrator's task) states "No code or
roadmap edits" for this security pass — minting new `AC-B<n>` backlog entries would violate that.
Findings 1 and 2 above are written up in full, with file:line, reproduction trace, and recommended
fix, specifically so the orchestrator/user can file them (or decide (A)/(B)/(C)/(D) directly)
without re-deriving the analysis. Finding 7 (`AC-B11` count bump) is cited under its existing ID,
not a new item — the one-line roadmap update it calls for is also left to a follow-up, same reason.

## Review Confidence

Full read of every file the task's "Surfaces worth attention" list named, plus `review-m3.md`
(both passes) and `implementation-m3.md` in full. Traced Finding 1's consequence by hand through
`run_active_frame`'s projection and `law_terrain_w_floor`'s gates line-by-line (not just asserted
"the regex blocks it," which is what the existing review did and which is where the gap was) rather
than running a live reproduction — no DCS/Lua runtime available in this worktree; the trace is
arithmetic (IEEE-754 double overflow and gate semantics), not behavior requiring execution to
confirm. Did not re-verify `review-m3.md`'s own still-open Required Fix (the `shortfall`-recovery
test gap) — that is Reviewer's/Implementer's loop, not this role's concern, and is already tracked
there.
