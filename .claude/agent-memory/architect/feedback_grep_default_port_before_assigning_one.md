---
name: grep_default_port_before_assigning_one
description: Before picking a port for any new LAN-facing service, grep DEFAULT_PORT repo-wide -- there is no central port registry and collisions already exist.
type: feedback
---

Before assigning a port to a new LAN-facing service, run
`grep -rn "DEFAULT_PORT" --include="*.py" .` across the whole repo (not just the subproject being
planned) and pick an unused number, rather than guessing a "probably free" one.

**Why:** there is no central port registry. Each subproject declares its own `DEFAULT_PORT`
constants independently: aircraft-layer owns a contiguous family (7790 Export.lua listener, 7791
LAN API, 7793 command sender, 7795 unit-velocity receiver, 7796 line-of-sight receiver, 7797
look-direction, 7798 firing receiver, 7799 mission-start — 7794 was the retired F10 command
channel, not reused), world-model's API server is 7792, brain-layer's server is 7796 (same number
as aircraft-layer's line-of-sight receiver — not a bug, since the two are UDP vs TCP on
different roles, but a sign nobody is checking), and audio-adapter's server is 7795 (same number
as aircraft-layer's unit-velocity receiver). These collisions have shipped and nobody has had to
reconcile them, presumably because the colliding pairs don't run on the same machine — but that is
an assumption, not a guarantee, and it means "pick a number that looks free" is not a safe method.

**How to apply:** when a plan introduces a new network-facing service (raster-chart-viewer chose
7800, one past the aircraft-layer family, 2026-11-16), grep first, list every `DEFAULT_PORT` found,
and choose a number not already in that list. State the grep result in the plan so a reviewer can
verify the choice without re-running it. Do not propose retiring/renumbering an existing collision
as part of an unrelated feature plan — that is its own, separate piece of work.
