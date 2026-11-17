---
name: project_bl17_stage4_wire_validator_drift_speed_target
description: BL-17 Stage 4 widened SlotValue to int|str|dict on the audio-adapter side (command_matcher.py) and documented body.py's mirror validator as fixed too, but body.py's _poll_transcripts isinstance(value, (int, str)) check was never actually touched -- confirmed by diff and empirically -- so the real "speed max"/"speed <number>" voice command is silently dropped at the HTTP wire boundary.
metadata:
  type: project
---

`[[BL-17]]` Stage 4 (`plans/speech-rules/plan.md`) ported `set_speed` with a union `speed_target`
slot (`{"kind": "max"}` / `{"kind": "number", "value": N}`) -- the first shipped rule to carry a
non-scalar slot value through the real dispatch path. `command_matcher.SlotValue` was correctly
widened to `int | str | dict[str, object]` and `_match_rules`'s own filter updated to
`isinstance(value, (int, str, dict))` (`audio-adapter/src/command_matcher.py:566-570`) --
confirmed correct, both by reading the diff and by the code's own comment citing the exact defect
it fixes.

**`body.py`'s own mirror validator, `_poll_transcripts` (body-layer, the other side of the same
wire), was never actually widened**, despite `plans/speech-rules/implementation.md:1474-1479`
explicitly claiming it was ("widening `body.py`'s own validator's `isinstance` check"). The real
code at `body-layer/src/body.py:3984-3987` (confirmed unchanged across the whole
`c309092b..1e5ddd5e` diff -- zero lines touched) still reads:

```python
if not isinstance(slots_raw, dict) or not all(
    isinstance(value, (int, str)) and not isinstance(value, bool)
    for value in slots_raw.values()
):
    continue
```

No `dict` in that tuple. Confirmed **empirically** (not just by reading): a standalone probe
feeding `_poll_transcripts` a `{"slots": {"speed_target": {"kind": "number", "value": 200}}}`
item -- the exact shape a real "speed two hundred" utterance produces -- shows `console.calls ==
[]`: the whole transcript item is silently dropped (`continue`), never reaching
`handle_transcript`. None of the 13 existing `test_poll_transcripts_*` tests exercise a
dict-valued slot (the one "malformed value" test uses `bool`, which is a different, deliberately
rejected case) -- a leaf-tested-but-wiring-untested gap, same shape as
`project_terrain_callout_stage5_wiring_gap.md`, except here the "wiring" is a second process's own
copy of the same validation contract that was fixed on one side and not the other.

**Consequence**: saying "speed max" or "speed <number>" over the real audio-adapter<->body-layer
wire does nothing and says nothing -- the exact "recognised, did nothing, indistinguishable from
unheard" failure `[[BL-17]]` exists to avoid. No crash, no security exposure (the opposite: the
stale filter is *too* strict, so nothing malformed from a dict-shaped slot value can ever reach
the Lua sandbox via this path) -- a correctness/wire-contract defect, not a vulnerability. Filed
as a Required Fix in `plans/speech-rules/security-stage3-4.md` rather than deferred, because it
sits exactly on the wire-boundary-validator surface this role is dispatched to check, and the
written implementation notes describing it as already fixed are themselves the trap: this
project's own "verify state, not the account of it" failure mode, caught only by reading the
actual current source and reproducing the drop, not by trusting the stage's own writeup.

**General lesson for this codebase's future Lua/HTTP slot-type widenings**: when a slot/wire type
is widened (`SlotValue` growing a new variant), grep for *every* site that type crosses a process
boundary and has its own independent `isinstance` allowlist -- there were two in this case
(`command_matcher.py`'s `_match_rules` filter on the sending side, `body.py`'s `_poll_transcripts`
filter on the receiving side), and fixing one does not imply the other was touched. A written
implementation note claiming "both filters widened" is not evidence either was -- read the actual
current source at the site, and where the two sides must agree on a shape, prefer a differential/
round-trip test (encode on one side, decode on the other, assert the value survives) over trusting
prose.
