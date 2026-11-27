# BL-16 security fix `dc60120f` — accepted without reviewer pass

**Status: ACCEPTED BY USER, NOT REVIEWED** (2026-11-27).

`dc60120f` answers Required Fix 1 of `security.md` (`flight_authority.py` `_as_optional_float`
accepts NaN/Infinity off the wire → `int()` crash downstream). The fix adds a `math.isfinite`
check so a non-finite value degrades to `None`, with tests that fail without it.

The reviewer pass required by `AGENTS.md` ("A change request from Security … re-enters the loop")
did not happen: three reviewer/implementer dispatches on this work across two sessions were
stopped by Anthropic's safety checks (`general_harms`), the latest
`req_011ChTzEesUYeyJ3v93fPvo1`. Offered the choice between retrying in a new session and
accepting the fix unreviewed, the user chose to accept it ("option 2").

**What was not checked**, so DoD and any later reader know: the downstream handling of `None`
on every path a value used to reach (`decide_carried_value_speech`,
`CrewConsole._axes_current_*` `round()`/`int()` paths). DoD's full test suite is the remaining
gate for that.

Pre-existing identical gaps in `belief/flight_control.py` and `belief/ai_pilot_wheel.py` are
filed on `[[BL-B135]]` (main, 2026-11-27).
