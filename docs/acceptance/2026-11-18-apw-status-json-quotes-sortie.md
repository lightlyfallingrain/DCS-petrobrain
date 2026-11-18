# apw-status-json-quotes: acceptance sortie (2026-11-18)

**Artifact (cockpit-readable card):** https://claude.ai/artifact/8i4iurqBcLZTPzd6Jp6pHV
**Card source:** `docs/acceptance/2026-11-18-apw-status-json-quotes-card.html`
**Branch to fly:** `main`, after this DoD pass's auto-merge (`git checkout main && git pull`).

**What is under test:** `plans/apw-status-json-quotes/debug.md` — a double-quoting bug in
`ai_pilot_wheel.lua`'s `push_ai_pilot_wheel_state` made the AI-overlay status line invalid JSON
from (in practice) the first poll after AI mode engaged. `aircraft-layer/src/collector/server.py`
dropped the whole line, so `GET /ai_pilot_wheel/latest` froze at its last validly-parsed sample —
this is exactly what `docs/acceptance/2026-11-16-bl16-batch-a-feedback.md` shows: `apw_mode_text`
etc. all `null` while the pilot could see the AI overlay actively showing text and flying. The fix
removes the redundant outer quote wrap; a new regression test
(`TestPushAiPilotWheelStateJson`, 4 cases) confirmed broken pre-fix, fixed post-fix.

**This may also explain apparent failures on two still-open flight cards since 2026-11-16**, both
of which drive the AI pilot wheel's status/goal channel and would have been reading this frozen
line the whole time:

- `docs/acceptance/2026-11-17-bl16-p2-voice-goals-sortie.md` (BL-16 Stage P2a/P2b — voice goals,
  HVRT translate)
- `docs/acceptance/2026-11-17-bl17-flight-commands-sortie.md` (BL-17 flight-commands)

Neither is re-flown by this card. If either showed a goal/readback that "didn't seem to update,"
it is worth re-checking now that the status line itself is fixed, rather than assuming it was a
goal-logic bug in those features.

## Check 1 — `GET /ai_pilot_wheel/latest` keeps advancing

**Prerequisite:** AI pilot wheel engaged (stick parked, AI flying) at some point during the sortie.

From the Mac or any LAN machine, with `OMEN` set to the Windows box's LAN address (as already used
in `docs/acceptance/2026-11-16-bl16-batch-a-feedback.md`):

```
OMEN=192.168.0.85; curl http://$OMEN:7791/ai_pilot_wheel/latest
```

Run it two or three times, a few seconds apart, while the AI overlay is visibly showing
mode/course/altitude/speed text and the AI is actively flying.

**Expect:** `apw_mode_text`, `apw_course_text`, `apw_alt_text`, `apw_speed_text` are non-`null` and
change between polls (course/alt/speed digits updating, or `t`/`received_wall_clock_s` advancing
each call) — not frozen at the same values every poll, and not all-`null` while the overlay is
visibly populated.

**Record:** did the fields update between polls, or freeze?

## Check 2 — an AI-overlay voice command is accepted, not refused

Speak a goal while mode 2 is active and the player is in the operator seat — e.g. "heading 090" (or
whatever this build's actual spoken phrasing is; see `body-layer/ROADMAP/BL-16.md` Stage P2 for the
exact vocabulary if "heading 090" isn't recognized verbatim).

**Expect:** the command is acted on (readback, or the AI-wheel status line's goal/course fields
move toward the new target) — not "say again" (not understood) or "unable" (rejected as
unavailable). `[[BL-16]]`'s own P2 card has the fuller goal-command test matrix if this needs more
than a smoke check.

**Record:** accepted and acted on, or refused — and if refused, "say again" or "unable"
(`notes/` distinguishes these as two different failures).

## UNVERIFIED — not run by this DoD pass

Both checks above need a live DCS session (Windows, AI pilot wheel engaged, a spoken command) that
this role cannot perform from here. Marked `#needs-flight` on `body-layer/ROADMAP/BL-16.md` rather
than held open as a merge blocker — testing debt is accepted in batches per 2026-10-26/2026-11-15
user direction.

## Bring back

- Did the status line advance continuously, or still freeze at some point?
- Was the spoken command accepted?
- Anything that surprises you is worth more than anything on this list.
