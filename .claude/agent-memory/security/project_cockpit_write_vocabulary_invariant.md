---
name: project_cockpit_write_vocabulary_invariant
description: aircraft-layer's write paths must stay a small fixed vocabulary, no generic device/cmd/value pass-through — flagged once on BL-B66's cockpit_switch op
metadata:
  type: project
---

`aircraft-layer/CLAUDE.md`'s "What this is" section states a standing invariant: every write path
into DCS carries only a small, fixed vocabulary (opaque display string, search mode enum, WAV
blob, one of three F10 tokens) — "no aircraft state, no free-form commands, no code, no
general-purpose remote-exec surface." Every existing write path honours it by an explicit enum/
allow-list check before the DCS call (`petrovich_search`'s mode checked against exactly
`{"forward","boresight"}`, F10 commands checked against `ALLOWED_COMMANDS`).

**Why this matters for review:** BL-B66's `plans/9k113-effectors/plan.md` (2026-10-21 revision)
specified a new, generic `cockpit_switch` op — `(device, cmd, value)` forwarded straight to
`GetDevice(device):performClickableAction(cmd, value)` — with only a type/shape ("malformed body")
check, no value allow-list. That is precisely the "general-purpose remote-exec surface" the
subproject's own doc rules out, and the plan didn't discuss departing from the invariant — it read
as an oversight. Flagged as the Mode 1 REJECT reason (`plans/9k113-effectors/
security-plan-review.md`), required fix: a fixed `(device, cmd)` allow-list + `value ∈ {0,1}`
enforced in `Export.lua`'s own dispatch (the unsandboxed-host layer), mirroring
`handle_petrovich_search_command`'s mode-enum check — not merely at the HTTP layer.

**How to apply:** any future plan that adds a new generic/parameterized write primitive to
aircraft-layer (a new op taking an arg number, a device id, a raw value, etc.) should be checked
against this exact invariant first. A write path that accepts anything beyond a closed enum/fixed
set is the recurring shape of the problem here — check for an allow-list at the Lua dispatch layer
specifically, not just a body-shape check at the HTTP boundary one layer up.


**Overridden by the user, 2026-10-21** — the BL-B66 allow-list fix was declined: *"Allow any cockpit switch. That gives us much more freedom later and even now with experimenting. This is LAN only and switch behaviour is limited to DCS."* `aircraft-layer/CLAUDE.md` now names `cockpit_switch` as the one deliberate exception. Do not re-raise the missing allow-list on that op as a required fix; a *new* free-form surface (code, arbitrary SetCommand on axes, file writes) is still a finding.
