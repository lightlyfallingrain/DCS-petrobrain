# SPU-8 intercom read/write probe

<!-- doc-provenance:start -->
**Flight for:** [[AA-3]]
<!-- doc-provenance:end -->

**Branch: none yet** — this is reconnaissance for Audio-adapter Slice 2
(`audio-adapter/ROADMAP.md`), not a feature branch. There is nothing to check out; this probe runs
against your current DCS install directly, no code changes deployed. Findings:
`aircraft-layer/research/2026-10-05-spu8-intercom-write-path-recon.md`.

**Batches with the Afghanistan projection check** — `docs/acceptance/2026-10-05-afghanistan-
projection-check.md` on branch `feature/multi-theatre-afghanistan` — same session at the DCS box,
different question. Do that one too while you're there.

## Why this card exists

Slice 2 wants Petrovich's audio gated by the real intercom switches: pilot's own Radio/ICS switch
(arg 456) and the co-pilot/operator's intercom power switch (arg 664) — the second one sits on the
**operator's** panel, which you can't reach by clicking from the pilot's seat. Static file reading
confirms the command mechanism exists and is already shipping (BL-6's AI-wheel trigger uses the
same `GetDevice():performClickableAction()` call), but nothing has ever tested whether a write to
an **operator-panel** control succeeds while you're sitting in the **pilot's** seat. That's a
one-flight test, and it decides whether Slice 2 can set arg 664 automatically or has to ask you to
flip it by hand.

## Setup

No hand-editing: the probe is a ready-made script,
`aircraft-layer/dcs-export/Export.probe-spu8.lua` on branch `investigate/spu8-intercom-write-path`.
It runs on its own; the collector does not need to be running.

1. Copy `aircraft-layer/dcs-export/Export.probe-spu8.lua` to `Saved Games\DCS\Scripts\Export.lua`
   (replacing the deployed one for this flight).
2. Delete any old `Saved Games\DCS\Logs\aircraft_layer_probe_spu8.log`.
3. Fly any Mi-24P mission, **pilot seat**, on the ground is fine.

## What to do — about one minute, the script keeps time

| time from mission start | you | the script |
|---|---|---|
| 0–30 s | Click the **pilot's Radio/ICS switch (456)** both ways, and turn the **SPU-8 volume knob (457)** end to end and back. Optionally flip the two network switches (376/377). | Logs every value change. |
| 30 s | **Hands off the intercom panel.** | Flips the **operator's intercom power (664)** to the opposite of where it is. |
| 50 s | Hands off. | Flips 664 back. |
| 60 s | Exit whenever (log says `PROBE DONE`). | — |

Optional, if the mission lets you change seats: after 30 s, jump to the operator seat and look at
the intercom switch on his panel. Seeing it move confirms the write in the cockpit, not just in the
number.

Afterwards **re-copy the production `aircraft-layer/dcs-export/Export.lua` from the repository**
to `Scripts\Export.lua`. Do not restore a backup (see `aircraft-layer/WORKFLOW.md`).

The script's logic was run in this session under a stubbed DCS harness (Lua 5.1, fake devices):
the timeline, change logging and both writes behave as described. Whether DCS honours the write is
exactly what this flight measures.

## Pass criteria

There's no pass/fail here — it's a measurement, either answer is useful. What decides Slice 2's
design is simply: did 664 change value after the write attempt, and did it hold (not get reset by
some other system)?

## Bring back

The file `Saved Games\DCS\Logs\aircraft_layer_probe_spu8.log`. That alone answers everything:
the read values across each control's travel, and lines `WRITE 1` / `CHECK after write 1 +1s` /
`+5s` (and the same for write 2) showing whether 664 moved and held. If you looked from the
operator seat, add a sentence on what you saw.
