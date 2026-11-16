## Security Deep Analysis: seat-change-triggers

Branch `feature/seat-change-triggers`, merged by fast-forward into this worktree at `e2ee3f98`
(`a55f7e97..e2ee3f98`). Scope: `git diff a55f7e97...e2ee3f98 -- body-layer` (body-layer only,
confirmed by `--stat`; the Lua/aircraft-layer side that already emits `apw_seat` is pre-existing
and untouched by this diff).

### Dependency Status

No dependency change.

### What changed

Two new `EffectorTrigger` values, `SEAT_PILOT`/`SEAT_COPILOT`, fired by `body.py`'s poll loop when
`belief.ai_pilot_wheel.seat_change(previous, current)` sees a change between two *known* seats in
`ParkedFlightState.player_seat`. `player_seat` is populated each poll from `apw_seat`, a field on
the aircraft-layer's LAN-facing `GET /ai_pilot_wheel/latest` feed, via a new `_as_seat` parser.
Firing either trigger runs a user-authored sequence file through the existing (pre-existing, not
part of this diff) effector engine, which writes cockpit switches.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/belief/ai_pilot_wheel.py:124-129` (`_as_seat`) | Untrusted-field parsing at a LAN boundary | **Strict allow-list, not a conversion.** `value == "pilot"` / `value == "operator"`, else `None`. No `int()`/`float()`/`isinstance(x, int \| float)` path exists for this field, so the recurring NaN/Infinity/int-conversion class this codebase has hit twice before (`BL-B104`, `.claude/agent-memory/security/project_nan_infinity_int_conversion_at_lan_boundary.md`) does not apply — there is nothing to convert. `==` against any JSON-decoded type (str/int/float/bool/None/list/dict) never raises. A hostile/malformed value of any shape — wrong type, oversized string, nested structure — degrades to `None` ("seat unknown"), never an exception, never a write. | None. |
| `body-layer/src/belief/ai_pilot_wheel.py:170-175` (`player_seat=` assignment) | Field presence vs. absence | `"apw_seat" in sample` guards an older `Export.lua` that sends no field at all (keeps prior state) separately from the field being present-but-garbage (routed through `_as_seat`, above). Correctly distinguishes "absent" from "invalid" — same posture as every other optional field in this parser. | None. |
| `body-layer/src/belief/ai_pilot_wheel.py:131-141` (`seat_change`) | Pure comparison, no I/O | `previous is None or current is None or previous == current -> None`. Both arguments are already constrained to `Literal["pilot","operator"] \| None` by `_as_seat`'s return type — nothing attacker-controlled reaches this function except through that allow-list first. | None. |
| `body-layer/src/body.py:4604-4619` | Trigger selection from parsed data | `EffectorTrigger.SEAT_PILOT if moved_to == "pilot" else EffectorTrigger.SEAT_COPILOT` — `moved_to` can only be `"pilot"`, `"operator"`, or `None` (guarded by the `if moved_to is not None` above it), so exactly one of two fixed enum members is ever selected. No dynamic lookup, no attacker-chosen trigger name, no attacker-chosen sequence file. | None. |
| `body-layer/src/belief/effector_sequences.py` (new enum members + `TRIGGER_INFO`) | Config/registry surface | Purely declarative; the actual write path (`effector_engine.advance`) is unchanged by this diff and was reviewed under `BL-B90`/`[[project_bl_b90_stage4_readback_by_need]]`. | None. |

**No `eval`/`exec`/dynamic code execution, no shell-out, no new file path built from network data,
no new unbounded read, no new listening socket.** `/security-grep`'s dynamic-code-execution and
unbounded-read categories were checked against the three touched source files directly; no hits.

### Threat-model analysis (LAN/dependency, per project scope)

1. **Can a malformed/hostile `apw_seat` value cause unintended writes?** No new unintended-write
   path. The value is validated to exactly two literals before it can influence anything; any other
   value is indistinguishable from "seat not reported." The only thing a hostile value can do is
   make `player_seat` read `None` (no trigger) or one of the two legitimate seats (a trigger that
   can fire regardless, any time the player actually moves seats).

2. **Rate/DoS via rapid forged seat-flapping.** A LAN actor able to forge aircraft-layer's response
   (or a compromised aircraft-layer process) could flap `apw_seat` between `"pilot"`/`"operator"`
   every poll. This is bounded by the pre-existing effector engine (`BL-B90`, D1): a trigger
   already running when re-fired is marked pending, not queued a second time, and at most one write
   per trigger per poll happens regardless of fire rate — the same bound every other `every_time`
   trigger (e.g. `weapons-safe`) already has. Not a new DoS class introduced by this feature.

3. **Trust boundary this reuses, not a new one.** `GET /ai_pilot_wheel/latest` is the same
   unauthenticated LAN HTTP seam `[[project_bl15_mission_start_plan_review]]` already assessed for
   the mission-start/belief-wipe trigger and accepted under this project's single-user/LAN-only
   scope ("same local-attacker standard already applied to every other loopback/LAN channel, not a
   new trust boundary"). This feature adds a second consumer of that same boundary (a cockpit
   switch write via a committed, fixed sequence file) rather than a new boundary. The blast radius
   is narrower than the mission-start case it's compared against: a forged value here can only
   select between two fixed, author-controlled sequence files, never wipe belief state or run
   arbitrary content.

   Presented per the standard format for completeness, since the project rule is never to carry an
   acceptance forward silently when its blast radius could have grown:

   **Finding:** A LAN actor who can forge/MITM the aircraft-layer→body-layer feed can cause
   `seat-pilot`/`seat-copilot` to fire at will, running their mapped sequence files.
   **Location:** `body-layer/src/belief/ai_pilot_wheel.py` (`_as_seat`), `body-layer/src/body.py`
   (seat-change trigger dispatch).
   **Probability:** low — requires a compromised or spoofing device already on the LAN, the same
   capability every other channel in this project already assumes away.
   **Impact:** low — bounded to running an existing, committed, two-row-scale sequence file
   (cockpit switch writes within DCS); no code execution, no filesystem access, no belief/mission-
   memory effect.
   **Recommended action:** accept, as an extension of the standing BL-15 LAN-trust acceptance
   rather than a new acceptance.

   Options:
     (A) Ignore — document acceptance of this risk (recommended; this is what I'd do)
     (B) Add to todo.md — fix in a future session
     (C) Fix now — I'll address it before continuing
     (D) Stop — do not proceed until this is resolved

   **Lapse condition, stated explicitly per project rule:** this acceptance, like the one it
   extends, lapses the moment root `CLAUDE.md`'s scope statement changes from single-player to
   multiplayer/shared-machine — that would put a second, less-trusted party on the same LAN the
   acceptance assumes is one user's own equipment.

### Passed to Reviewer (no verdict — player-experience domain)

- Whether a transient/ambiguous camera-position reading during the seat-transition animation
  itself could read as a spurious seat value and fire a sequence mid-transition is a correctness
  question about what `Export.lua`'s camera check actually reports frame-to-frame, not a security
  question — noting it so Reviewer can confirm `apw_seat`'s source behaves as the docstring assumes.

### Verdict

APPROVED

### Required Fixes

None.

### Findings ledger (closing-step rule)

One low-risk item above, presented with the standard risk-communication options. **Not filed as a
new backlog item, intentionally**: it is the same trust boundary and capability
`[[project_bl15_mission_start_plan_review]]` already accepted under this project's single-user/
LAN-only scope, with a narrower blast radius (two fixed sequence files vs. a full belief wipe) —
filing a second backlog entry for the same standing acceptance would fragment, not improve,
tracking of it. If the user chooses option (D) or wants it tracked separately, mint one then.
