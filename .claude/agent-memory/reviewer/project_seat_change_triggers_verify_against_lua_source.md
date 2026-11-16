---
name: seat-change-triggers-verify-against-lua-source
description: reviewing a body-layer feature whose correctness depends on an aircraft-layer Export.lua behaviour (a held-last-value seat read) -- verified by reading the Lua directly rather than trusting the commit message's account of it
metadata:
  type: project
---

`feature/seat-change-triggers` (BL-16's `ParkedFlightState.player_seat` + `seat_change`,
`body.py` wiring to new `SEAT_PILOT`/`SEAT_COPILOT` effector triggers) has a correctness property
that is invisible from the body-layer diff alone: `seat_change(previous, current)` only fires on a
move between two *known* seats, and silently swallows a move if `current` ever reads as an
"unknown" value in between two real seats (`previous -> None -> new_seat` loses the transition,
since `seat_change(None, new_seat)` is `None` by definition). The commit message asserts this is
safe because `Export.lua` never emits a transient "unknown" mid-transition. I did not take that on
faith -- I read `aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`'s
`ai_pilot_update_seat`/`ai_pilot_seat_from_camera` directly and confirmed: a `nil` camera reading
keeps the *previous* `ai_pilot_player_seat` rather than overwriting it, and the value is reset to
`nil` only on `LuaExportStop` (mission end), not transiently during a seat move. Both claims in the
body-layer commit message and `body-layer/CLAUDE.md` turned out correct, but this is exactly the
kind of cross-subproject behavioural assumption that a body-layer-only read (even a careful one)
cannot settle on its own -- the two subprojects are independently-tested, HTTP/feed-coupled, and
the actual guarantee lives in Lua, not Python.

**How to apply**: when a body-layer (or any subproject) feature's test coverage relies on a
property of *another* subproject's live behaviour that isn't itself exercised by any test in this
diff (an upstream "holds the last known value," "never emits X mid-transition," "resets only on Y"
claim), go read that other subproject's actual source before accepting it -- a commit message's
account of another layer's behaviour is a claim, same status as any other docstring "X, so Y"
claim this role is told to distrust. Grep for the relevant local/field name in the Lua (or other
subproject) source directly; don't stop at the Python-side comment that paraphrases it.

See also [[verify-the-rendered-artifact-not-the-source-comment]] (triggers.md generation) --
same genre of "read the real source, not the account of it," applied here to live behaviour
instead of a generated file.
