---
name: dostring_in_optional_subwire_pattern
description: How to add a new optional field to a Hook script's single net.dostring_in return string without breaking the existing collector parse (the \1-separator pattern, used by the LOS hook's "probes" and BL-B124's "mission_clock")
metadata:
  type: reference
---

`net.dostring_in` returns exactly one value from the bridged Lua chunk, so a Hook script that
already has a fixed, pipe-delimited wire shape (e.g. `"<count>|<t>|<entries>"`) cannot just append
a new field with another `|` — that breaks every existing parser's fixed-field-count split.

The established pattern (`petrobrain-line-of-sight-hook.lua`'s `probes` addition, and
`petrobrain-firing-events-hook.lua`'s `mission_clock` addition, `BL-B124`):

1. Inside the bridged Lua chunk, build the original payload string exactly as before, then append
   `"\1" .. newFieldString` to it. `\1` is a control character that will never appear in the
   existing payload, so splitting on it is unambiguous.
2. In the outer Hook script (outside `dostring_in`), split the returned string on `\1` into the
   original payload and the new field's own sub-string, with a defensive fallback (`result:match`
   returning `nil` → treat the whole string as the old payload, new field empty).
3. Send the new field as its **own top-level JSON envelope key** (`envelope.newField = ...`), never
   folded into the existing `payload` string on the wire. The collector's envelope parser reads
   `envelope.get("payload")`/`get("bridge_call_ms")` and ignores unknown keys, so this is
   automatically forward/backward compatible: an old collector with a new Hook ignores the new key;
   a new collector with an old Hook (no key at all) gets `None`/absent and must treat that the same
   as "unavailable."
4. On the Python schema side, give the new field its own small dataclass with its own `from_wire`
   (e.g. `MissionClockSample`, mirroring `ProbeAnswers`) — a malformed new field drops to `None`
   without raising and without failing the rest of the batch, same posture
   `LineOfSightSnapshot.from_wire` already established for `probes`.

**How to apply:** any time a plan asks to add a new per-poll value to an existing `dostring_in`
poll channel, check whether the channel already has this pattern (grep `\\1` and `probes` in
`aircraft-layer/dcs-export/*.lua`) before inventing a new envelope/port — it generalizes directly.
