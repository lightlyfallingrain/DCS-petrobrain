---
name: project_9k113_ai_axis_native_contention_hypothesis
description: Leading hypothesis for the 9K113 AI-slew-axis intermittent gate (BL-B80) — Petrovich's own native autonomous-OBSERV scanning, already decided as in-scope design, is a second writer to device 7 competing with our SetCommand
metadata:
  type: project
---

8 probe runs on 2026-10-22 (`docs/acceptance/2026-10-22-9k113-ai-latency-probe.md`) established the
9K113 AI axis (3060/3061, device 7) is a rate command that is obeyed in short windows (1-3 commands)
then ignored for 4-100+ s, all-or-nothing per step, uncorrelated with boresight proximity. No cockpit
arg tracks the gating state (962 LAUNCH PERMITTED and the stick-park toggle 3055 both correlate in
some runs and are flatly refuted in others — run 8: 42 toggles, zero effect).

**Cross-referencing against this project's own prior `/explore` decision surfaced the likely cause**,
found only by searching `docs/acceptance/` rather than re-deriving from the probe logs:
`docs/acceptance/2026-10-15-9k113-sight-direction.md` §6 — user direction, verbatim, decided a week
*before* any of these probes were flown: *"if OBSERV is ON, then Petrovich can use the 9K113
autonomously, like he uses binoculars."* Every probe run requires OBSERV ON as setup. ED's own public
newsletter independently corroborates the mechanism exists at all: *"Petrovich AI will move his Field
Of View (FOV) in different directions to scan for potential threats"* as documented idle/background
behaviour (`https://www.digitalcombatsimulator.com/en/news/newsletters/f8e32e08192f89a9c593861366a211b2/`,
fetched successfully).

**So the leading hypothesis: Petrovich's native AI and the external `SetCommand` write are two
independent writers to the same device, and whichever the engine applies last on a frame wins** —
explains all-or-nothing-per-step, no tracked gating arg (native state machine isn't exposed to Lua),
and no boresight correlation (an autonomous scan sweeps the whole FOV). Not yet tested directly.

**Cheapest untested check, for whoever picks this up next:** `list_indication(10)` (the AI command
wheel text channel) already exposes Petrovich's own state as `SEARCHING`/`TRACKING`/`WAITING`
(confirmed readable, `aircraft-layer/research/mi24p-command-surface.md` §5) and was never logged
alongside any of the 8 runs. Add it to the next probe's per-frame log and check whether `SEARCHING`
coincides with ignored windows.

Full writeup with all forum/GitHub searches (community has no published prior art for driving an
AI-operator-owned device from Lua — a genuine negative result, not a missed find) and ranked
approaches: `aircraft-layer/research/2026-10-22-9k113-ai-axis-obedience-prior-art.md`.

See also [[forum-dcs-world-fetch]] — three on-topic forum.dcs.world threads (274765 "auto-handoff",
368258 "observe on stutter", 347628 "Petro complaints") 403'd on WebFetch; ask the user to paste
them if this hypothesis needs more than the newsletter + design-decision corroboration it already has.
