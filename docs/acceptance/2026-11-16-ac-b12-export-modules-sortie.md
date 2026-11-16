# AC-B12/AC-B13 Export.lua module split: deploy check (2026-11-16)

**Artifact (cockpit-readable card):** https://claude.ai/artifact/5Q1za4baC6VNYaRoScNuyc
**Card source:** `docs/acceptance/2026-11-16-ac-b12-export-modules-card.html`
**Branch to fly:** `main`, after this DoD pass's auto-merge.

**What changed.** `Export.lua` is now a short loader. The 3,200-line single file became nine files:
the loader plus eight modules under a new `aircraft-layer/dcs-export/Petrobrain/` folder
(`core`, `telemetry`, `petrovich`, `sight`, `ai_pilot_wheel`, `effectors`, `ptt_ics`, `commands`).
No feed's behaviour should be different. The one approved exception is AC-B13: a mission restart
while the AI-pilot-wheel is mid-correction-hold now releases the held cockpit button instead of
leaving it pressed.

**What is verified already, off-Windows, before you fly:**
- All 9 Lua files (`Export.lua` + 8 modules) parse clean under `luac5.1 -p`.
- `ruff format`/`ruff check`/`mypy --strict`/`pytest` all pass (795 tests, 0 skipped/failed).
- The version-handshake logic was run for real against the actual collector code on this machine
  (not DCS, just a loopback socket standing in for Export.lua): sending `{"export_version":
  "2026-11-16b"}` logs `Export.lua wire-format version 2026-11-16b (matches)`; sending the old
  `"2026-11-16"` logs the loud MISMATCH warning. Both sides of the deploy-staleness check work as
  designed.
- AC-B13's own fix has a passing Lua unit test extracting the real `on_stop` function: an open
  press is released and every takeover field clears; no open press means no spurious release but
  the fields still clear.

**What only a live DCS session can confirm** — this is the point of this card.

## Setup

1. Deploy, per `aircraft-layer/WORKFLOW.md`: copy `aircraft-layer/dcs-export/Export.lua` to
   `Saved Games\DCS\Scripts\Export.lua`, **and** copy the whole
   `aircraft-layer/dcs-export/Petrobrain\` folder to `Saved Games\DCS\Scripts\Petrobrain\`.
   Copying the loader alone leaves every feed silently absent — there is no error for a missing
   module folder, only silence on that one feed.
2. Start the collector (Windows box): `cd aircraft-layer/src && python -m collector`.
3. Air start, straight and level, per this project's own convention for effector probes.

## Checks

1. **Version match.** Watch the collector's first lines after DCS connects. Expect
   `Export.lua wire-format version 2026-11-16b (matches)`. A mismatch warning means a stale or
   partial deploy — stop and re-copy both the loader and the folder before continuing.
2. **Every feed still reports.** `GET /telemetry/latest` moves with the aircraft; pause the
   mission, confirm it keeps serving (stale, not crashed, not null). `GET /world_objects/latest`
   lists at least one other object. Trigger Petrovich's search
   (`POST /command/petrovich_search`), confirm `GET /petrovich_wheel/latest` reflects it. Turn
   OBSERV on, send a `sight_target` command, confirm the mark closes on the goal. Flip one cockpit
   switch via `POST /command/cockpit_switch`, confirm it moves in the cockpit. Install a
   `watch_args` set and a `read_args` one-shot, confirm both reply.
3. **`dcs.log` shows no Export Lua errors.** Any `nil` or unhandled-error line naming
   `Export.lua` or a `Petrobrain\` module means a load-order or deploy problem the pcall-guard
   design did not expect.
4. **AC-B13's own check — the one this plan cannot retire without you.** Park the stick (BL-16),
   induce a correction hold, then restart the mission mid-hold. Confirm no cockpit control is left
   pressed after the restart. The Lua unit test is the primary proof this fix exists; this is
   confirming it holds under the real DCS stop/restart path, not a Lua harness standing in for it.
5. **Repeat the paused-state check once more**, covering the full feed set — this subproject's own
   "always include a paused-state check" convention.

## The prize

Check 4. Everything else is "did the split change anything" (it should not have); check 4 is the
one behaviour change this plan makes on purpose.

## Bring back

- Did the collector log a match or a mismatch on connect?
- Did every feed answer, paused and moving?
- Anything in `dcs.log` naming `Export.lua` or a `Petrobrain\` file?
- After a restart mid-correction-hold, is any AI-wheel button still pressed?
- Anything that surprised you is worth more than anything on this list.
