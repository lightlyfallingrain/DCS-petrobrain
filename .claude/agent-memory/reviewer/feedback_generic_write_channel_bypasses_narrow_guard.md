---
name: generic-write-channel-bypasses-narrow-guard
description: When a change adds a narrow safety gate on one named write call site (e.g. SetCommand on a specific device/cmd), check whether this codebase's other, deliberately-unrestricted write channels (the aircraft-layer cockpit_switch op, BL-B66's "allow any switch") can reach the same device/cmd through a different DCS API and were left ungated.
metadata:
  type: feedback
---

Found reviewing `feature/9k113-hands-off-switch` (2026-10-30): the hands-off switch gated the one
`SetCommand(CMD_AI_AZ/CMD_AI_ELEV)` call site inside `sight_point_quiet`, verified by grepping for
`SetCommand` calls on that device/cmd pair. But `aircraft-layer`'s `handle_cockpit_switch_command`
(the `cockpit_switch` op, `BL-B66`, deliberately unrestricted by user direction 2026-10-21 — "allow
any cockpit switch... this is LAN only and switch behaviour is limited to DCS") writes via
`GetDevice(device):performClickableAction(cmd, value)` with no allow-list at all, and was not
gated by the new flag. A grep for the gated mechanism's own call site (`SetCommand`) correctly
found the narrow claim true, but missed that a *different* DCS write API
(`performClickableAction`) on the *same* device/cmd pair was never checked.

**Why it turned out to be low-risk this time, and how I confirmed that rather than assuming it**:
cross-checked `body-layer/config/sequences/<aircraft>/switch-reference.md` and the raw dump
`effectors-raw/<aircraft>.toml` — both are generated from the actual game's clickable-cockpit-data
declarations — and found no clickable element registered for the AI axis's command numbers on that
device. Combined with existing project research
(`aircraft-layer/research/2026-10-21-dcs-bios-mi24p-9k113-controls.md`) establishing the sibling
player-slew axis "has no clickable element... a raw `SetCommand` continuous axis," this made it
very likely (not proven) that `performClickableAction` on that device/cmd is a no-op in DCS. Still
flagged as a Required Fix rather than waved through, because the actual DCS-internals claim was
never verified live, the fix is three lines, and the failure mode (a corrupted calibration run) is
silent and undetectable after the fact — not a case to accept on inference alone when the
guarantee itself is "the whole point" of the feature.

**How to apply**: whenever a plan/implementation narrows what one write call site does by gating
it on a flag/condition, check this project's other write channels for the same device/target
before approving — specifically the `cockpit_switch` generic channel in aircraft-layer (and any
future analogous "allow anything, validated only for shape" channel elsewhere), not just the named
call site the change itself touched. `switch-reference.md`/`effectors-raw/*.toml` (generated from
the live game) is the fastest way to check whether a given device/cmd pair even has a reachable
clickable element, which is real, codebase-grounded evidence rather than an assumption about DCS
internals.
