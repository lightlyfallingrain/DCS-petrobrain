## Security Deep Analysis: bl-b124-light-level

**Batch:** BL-B124 Stages 1–5, range `7a1c70b3..baba22f4` on `feature/bl-b124-light-level`.
**Scope (root `CLAUDE.md`'s scoping note):** computer/network security under a single-user,
LAN-only threat model — supply-chain-in-a-dependency and an infected LAN host are the realistic
attackers. Player-experience correctness (whether the light curve's numbers are *right*) is the
Reviewer's job, not this pass's.

### Dependency Status

No dependency change. No new package, no new import outside this subproject's own modules.

### Surfaces reviewed

1. **`aircraft-layer/dcs-export/petrobrain-firing-events-hook.lua`** — `EVENT_POLL_CODE`'s
   `net.dostring_in("scripting", ...)` snippet is a **fixed literal string**, same as before this
   amendment: no runtime value is spliced into the Lua source at all (unlike the LOS Hook's `%d`
   splice pattern, `.claude/agent-memory/security/project_dostring_in_numeric_splice_naN_clamp_gap.md`).
   It only reads `timer.getAbsTime()`/`env.mission.date`, both independently `pcall`-guarded so a
   failure there cannot drop the firing-event drain. No new arbitrary-code-execution surface.
2. **UDP envelope, Hook → collector** — `mission_clock` rides as a new, optional `\1`-separated
   sub-string inside the existing firing-events UDP payload, the same device the LOS Hook's
   `probes` key already established. `collector.firing_receiver.FiringEventsReceiver` binds
   **`127.0.0.1` by default** (`DEFAULT_HOST`, `collector/__main__.py`'s `--firing-host` default)
   — loopback-only, not reachable from the LAN. `_handle_datagram`'s existing bounded-recv
   (`_RECV_BUFFER_SIZE`), non-dict/non-str/malformed-JSON drops are unchanged and still apply to
   the new key (`mission_clock_raw = envelope.get("mission_clock"); if not isinstance(...str):
   None`).
3. **`GET /firing/latest`** (`aircraft-layer/src/api/server.py`) — LAN-facing (`0.0.0.0`) by
   design, but this change is a docstring update only; no new write path. The new `mission_clock`
   key is a plain reflection of whatever the (loopback-only) UDP channel last ingested — read-only
   from a LAN peer's perspective.
4. **`body-layer/src/aircraft_client.py`** — docstring only, no code change (`get_firing_latest`
   is a shallow pass-through).
5. **`body-layer/src/perception/light_level.py`, `body.py`'s `_resolve_sun_elevation_deg`/
   `_parse_mission_clock_dict`** — pure computation over the parsed `mission_clock` value. This is
   where the one real finding below lives.
6. **`optic_policy.py`/`attack_run.py`/`crew_console.py`/`naked_eye_source.py`/`emitters.py`/
   `percept.py`** — parameter threading (`light_factor`/`sun_elevation_deg`) and a new
   `EmitterKind.LAUNCH_FLASH`/`S_EVENT_SHOT` branch in the collector's state machine. No new
   external input, no new file path, no new process/network call. Reviewed for the "No LAN
   message... carries a raw flight-axis value" and no-omniscience invariants in `body-layer/
   CLAUDE.md` — neither is touched by this diff; out of this pass's scope anyway (player-experience
   correctness).

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/src/schema/firing.py` `MissionClockSample.from_wire` (`abs_time_s = float(abs_str)`) | NaN/Infinity-at-wire-boundary gap, third instance of the pattern `[[BL-B135]]` generalises | Confirmed, traced end-to-end (not speculative) — see Finding 1 below | Filed `[[BL-B137]]`, not blocking |
| `aircraft-layer/src/schema/firing.py` `year`/`month`/`day` (`int(...)`, no bounds) | An attacker-controlled huge digit-string overflows `_julian_day`'s float arithmetic (`OverflowError`) | Caught by `body.py`'s poll-cycle `except Exception`; one dropped poll, self-healing | Noted in `[[BL-B137]]`'s "optionally also range-check" line; not separately filed |
| `collector/firing_receiver.py` `_handle_datagram` | `mission_clock_raw` type-checked (`isinstance(..., str)`), malformed sub-wire dropped to `None` without failing the batch | Correct, matches the established `probes` precedent | None |
| `petrobrain-firing-events-hook.lua` `EVENT_POLL_CODE` | `net.dostring_in` on a fixed literal, two independently `pcall`-guarded reads | Safe — no splice, no new injection surface | None |
| `collector/firing_receiver.py` `FiringEventsReceiver` default bind | `127.0.0.1` (loopback), unchanged by this feature | Confirms the new field's actual UDP attack surface is local-only, not LAN | None (reachability note for Finding 1) |

### Finding 1 — `mission_clock` NaN/Infinity silently forces the one outcome the feature forbids

**Confirmed by direct calculation**, not speculation. `MissionClockSample.from_wire` parses
`abs_time_s` with `float(abs_str)`, which does not raise on the strings `"nan"`/`"inf"`/`"-inf"`
— unlike the sibling `year`/`month`/`day` fields' `int()` calls, which do. `body.py`'s
`_parse_mission_clock_dict` accepts the resulting NaN/Infinity through its `isinstance(x, (int,
float))` guard (the same shape `.claude/agent-memory/security/
project_nan_infinity_int_conversion_at_lan_boundary.md` and its two siblings already document at
other wire boundaries in this codebase).

Traced through `perception.light_level.sun_elevation_deg`'s formula: a NaN `abs_time_s`
propagates NaN through every intermediate, but the function's own final clamp —
`sin_altitude = max(-1.0, min(1.0, sin_altitude))` — does **not** stay NaN. `min(1.0, nan)`
returns `1.0` (a NaN comparison is always `False`, so Python's `min`/`max` keep their *first*
argument whenever the comparison that would replace it is NaN); `max(-1.0, 1.0)` then returns
`1.0`. `math.degrees(math.asin(1.0))` is exactly `90.0` — sun directly overhead.
`light_factor()`'s `sun_elevation_deg >= EYE_FULL_DAYLIGHT_SUN_ELEV_DEG` branch fires cleanly on
`90.0`, returning `(1.0, 1.0, 1.0)`: **full clear-day optic performance**, the one outcome
`_resolve_sun_elevation_deg`'s own docstring says this feature must never produce from a bad
reading (user Q6, `explore-notes.md`: *"mission should always have both readable. Error if
not."*).

**It is also silent.** The Stage 4-5 review's own Required Fix 1 added a "fresh only if it
**differs** from the stored sample" guard specifically to stop a frozen/dead feed being mistaken
for a live one every poll. A NaN-bearing tuple defeats that guard structurally: `nan != nan` is
`True` in Python, so an identical malformed sample compares as "different from itself" on every
poll — permanently taking the "fresh" branch, never reaching the staleness/error path that would
log the one `ERROR` the design promises (`light_level_error_logged`).

**Reachability, why this is filed rather than blocking**: the UDP channel carrying
`mission_clock` into the collector binds `127.0.0.1` by default — loopback-only. `GET
/firing/latest` is LAN-facing but read-only (no write path for a LAN peer to inject a crafted
sample over HTTP). Triggering this therefore needs code already running locally on the DCS/
aircraft-layer box itself (a bigger prior compromise than this project's stated secondary threat
model — "an infected computer scanning LAN ports" — which is a different machine), or a genuine
upstream Lua anomaly, not observed and not expected under normal `timer.getAbsTime()`/
`env.mission.date` operation.

**Probability:** low — no LAN-reachable write path; requires local code execution on the DCS box.
**Impact:** low-medium — Petrovich's simulated light-dependent perception silently defaults to
full daylight for as long as the bad sample keeps winning the race against genuine Hook polls;
self-heals the instant a genuinely different, finite sample arrives. No code execution, no data
exposure, no crash.

**Recommended fix:** add `math.isfinite(abs_time_s)` to `MissionClockSample.from_wire`'s success
condition (raise `FiringParseError` otherwise, same as the existing `ValueError` path) — the
`float()`-not-`int()` precedent `line_of_sight.py`'s `agl_m` parse already sets, extended with the
explicit finite check this feature's own design goal requires.

**Filed as `[[BL-B137]]`** (`body-layer/ROADMAP/BL-B137.md`), a third instance of the pattern
`[[BL-B135]]` generalises — **not blocking**, same disposition as `BL-B135` and the `rules/
engine.py` instance before it: small, mechanical fix, low-probability reach, self-healing.
Flagged prominently in that entry as the worst-consequence instance of the pattern found so far
(silent, zero-observability, inverts the feature's own explicitly-named-dangerous direction),
because the pattern itself is recurring and worth a future dedicated pass across every numeric
wire field in this codebase (`BL-B135`'s own "a scan... would be a reasonable scope" note still
stands).

### Passed to Reviewer

None beyond what the Reviewer has already passed on — this batch went through
`review-stages-1-3.md` and `review-stages-4-5.md` before reaching this pass, both APPROVED WITH
MINOR FIXES, both fixes already applied and verified by mutation (`implementation.md`'s own
account).

### Verdict

**APPROVED.**

### Required Fixes (if any)

None blocking. `[[BL-B137]]` filed as a backlog item (see Finding 1).
