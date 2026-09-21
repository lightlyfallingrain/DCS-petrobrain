# PB-1.5 live probe: is the ambient contact callout readable from Lua?

**Date:** 2026-09-09
**DCS version:** 2.9.29.27278
**Aircraft:** Mi-24P, pilot seat, Petrovich (CPG) AI
**Terrain:** flat desert, ~31°34'N 40°08'E, clear daylight
**Harness:** `aircraft-layer/dcs-export/Export.probe-pb15.lua` (probe build of `Export.lua`)
**Artifacts:** `Saved Games/DCS/Logs/pb15_probe.log` (1,187 lines), 12 screenshots in
`Saved Games/DCS/ScreenShots/` (`Screen_260909_1234*`–`1240*`)

### Question

Settles the question left open across Sessions 1–5: **during a pass where the sight is off, does
any exported Lua value change at the moment Petrovich's ambient `"…, H O'CLOCK"` contact report
appears?**

Protocol: A/B over the same targets — segment A with `OBSERV OFF` (ambient only), segment B with
`OBSERV ON` (sight active, the control). Scenario units, from the F10 map screenshot: `T-90A`,
`BMD1`, `BTR60`, `Ikarus` (civilian bus), and two infantry (`AK74`, `AK`), spread around the
ownship at roughly 1.5–4 km.

## Finding 1 — the ambient callout has **no companion in `list_indication(6)`**. Q2 is answered.

Two ambient reports were captured on screen during segment A:

| wall clock | radio pop-up text | `list_indication(6)` at that moment |
|---|---|---|
| 12:34:18 | `GROUND, 11 O'CLOCK` | **nothing — device returned no elements at all** |
| 12:36:45 | `GROUND, 12 O'CLOCK` | **nothing — device returned no elements at all** |

Across the whole segment A window (session start 12:34:04 → 12:38:34, ~4.5 minutes) the device-6
tree produced **zero change events**, and its last logged state was empty. The probe logs that
tree on *every* change, and it demonstrably does change later in the same flight — so this is a
clean negative, not a gap in instrumentation. — **evidence:** reproduced-locally (live probe).

**The HelperAI device tree is not even instantiated until the sight comes on.** The first device-6
event of the session is at 12:38:34, when a lone `crosshair` element appears — i.e. the tree
materialises with `OBSERV ON` and is absent before it. That, on its own, rules the HelperAI
indication tree out as a carrier for anything ambient.

## Finding 2 — the two channels are distinct on screen as well as in Lua

| channel | where it appears on screen | in `list_indication(6)` |
|---|---|---|
| ambient / naked-eye | radio-message pop-up, top right — `GROUND, 11 O'CLOCK` | nothing |
| target list (sight) | list widget, bottom left — `> Civilian bus`, with the AI wheel (`PREV TGT`/`SELECT TGT`/…) | `middle_list_text` |

Segment B produced three sight-driven detections, each matching the log exactly:

| wall clock | `middle_list_text` | on screen |
|---|---|---|
| 12:38:58 | `BTR-60` | — |
| 12:40:10 | `BMD-1` | — |
| 12:40:40 | `Civilian bus` | `> Civilian bus` in the list widget at 12:40:43 |

Each detection populates the list for ~5 s, then the tree drops back to `crosshair` only
(12:39:03, 12:40:19, 12:40:45). `T-90A` was never listed at all during the flight.

## Finding 3 — `list_cockpit_params()` is useless on the Mi-24P for state probing

The sweep returned only **112–116 `BASE_SENSOR_*` values** — flight-model quantities
(`BASE_SENSOR_RADALT`, `_PITCH`, `_IAS`, `_LEFT_ENGINE_RPM`, atmospherics, stick/pedal positions).
**No cockpit switch, device, or subsystem state appears in it at all.** Nearly all of it was
auto-retired as volatile within the first 2 s of flight; the only later changes in the entire
sortie were two FFB stick factors at 12:35:00.

Consequence: the pilot's in-band markers (ICS/radio switch for segment A, NVG toggle for segment B)
were **never captured**, and the callout moments had to be recovered from screenshot timestamps
instead. The marker scheme should be considered failed, not the correlation — the screenshots
carried it.

**Scope limit, stated plainly:** because the param sweep cannot see device state on this module,
Finding 1's negative is clean **for `list_indication`** but is *not* an exhaustive negative across
every export surface. What is established is that neither the HelperAI indication tree nor any
cockpit param reachable from `Export.lua` mirrors the ambient callout.

## Finding 4 — ambient callout format

`GROUND, <N> O'CLOCK` — no count fragment when the contact is single/ungrouped. This matches the
`HelperAI_lengths_ng.lua` enum composition (`OP_SEE_GROUND` + `OP_A<N>H`) with the count bucket
omitted, and is consistent with the earlier user screenshot's `9 CONTACTS, 1 O'CLOCK`, where a
group adds `OP_8TO10UNITS`. See the Session 5 Addendum in
`2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`.

## Finding 5 — Petrovich detects considerably later than the player can see (pilot observation)

The pilot reports seeing the units on screen **well before** any contact report appeared, on flat
open desert with nothing occluding them. Treated as a calibration signal rather than a measurement
(the F10 snapshot is a single moment and the aircraft was moving, so per-detection ranges were not
computed): the scenario units sat roughly 1.5–4 km out, and two of the three sight detections were
of units the map places beyond PB-1.5's current `NAKED_EYE_RANGE_CAP_M = 2500`.

> **Note 2026-09-21:** `NAKED_EYE_RANGE_CAP_M` is **10000.0** today, not 2500 — the follow-up this
> section asks for was carried out (2500 → 5000 → 10000, the last by the 2026-09-17 screenshot
> ladder). The pilot's design position recorded here — *"if the player can see a unit, Petrovich
> should be able to as well"* — is what drove it, and it is now the project's stated calibration
> target (`body-layer/research/2026-09-21-calibration-target-decided.md`). Quote the *finding*
> from this section, not the constant.

The pilot's design position: **if the player can see a unit, Petrovich should be able to as well.**
Flat desert is the easy case and would flatter any detection model — among trees or in broken
terrain the comparison would differ — but it does suggest PB-1.5's cap is, if anything, too tight
rather than too generous. That direction matches the concern already recorded in the plan's Risks
("the derivation's error direction is unknown, and the arithmetic suggests it is strict"), and
supports Decision 6's ×4 binocular multiplier as a floor rather than a ceiling.

## Verdict for PB-1.5

**Outcome 2 of the three anticipated in `WORKFLOW.md`:** the ambient channel is real and fires
independently of the sight, but has no exported companion. PB-1.5's synthetic
FOV + angular-radius + LOS filter therefore stands as the only available implementation, and
Decision 1's "revisit if a real signal turns up" branch is closed for the `list_indication`
surface. The design does not change; the uncertainty behind it does.

Two follow-ups worth carrying:
1. **Re-examine `NAKED_EYE_RANGE_CAP_M = 2500`** against Finding 5 before or during live acceptance
   testing. The cap currently binds for every ground vehicle, and this sortie suggests real
   detections happen further out.
2. **`T-90A` was never detected** across the whole sortie despite being in the scenario. Unexplained
   — worth a glance during acceptance testing, since our own `object_model.py` classifies it fine.
