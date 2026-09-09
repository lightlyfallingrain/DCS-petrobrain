---
name: project_pb15_worldobjects_ambient_recon
description: LoGetWorldObjects has no radius/coalition filter arg; no confirmed DCS-sourced ambient (non-scope) target-detection signal exists for Mi-24P/Petrovich
metadata:
  type: project
---

`LoGetWorldObjects(arg)` (Lua Export API) only accepts a **category** string arg — `"units"`
(default) / `"ballistic"` / `"airdromes"` — confirmed in
`win-mac-sync/from-windows/Export.lua.reference-file-from-DCS-installation.lua` lines 624-629
(primary source). No radius-around-point or coalition/IFF filter argument exists. Community
sources (Tacview wiki, asherao/DCS-ExportScripts) agree; nobody pre-filters server-side, everyone
filters client-side after the unfiltered call. Per-call cost is real but unquantified at realistic
object counts (~50-200 units) — only qualitative "can be inefficient, ED partially optimized it"
claims exist, no hard numbers, and the two most on-topic ED forum threads (133284, 302542) are
403-blocked to WebFetch.

Second finding, higher-stakes: across the existing PB-1 live spike (4000 samples/4 flights,
`aircraft-layer/research/2026-09-08-pb1-live-spike-results.md`) **every tested HelperAI
`list_indication(6)` leaf and the crosshair az/el/hdg text stayed empty until a target was
actively selected via ASP-17 scope** — no ambient/naked-eye ("spotted but not slewed to") signal
was ever observed. `HelperAI_page_common.lua` also defines two untested sibling leaves
(`upper_list_text`, `upper_upper_list_text`) sharing the same `show_list` gate as the three tested
ones — structurally almost certainly the same gate, not directly observed unselected. Forum
snippets (unread, 403-blocked — topics 388039, 366508) are directionally consistent: list
population is tied to weapon/ATGM-selection mode, and one report describes Petrovich's voice
callout firing while the list stays empty — suggesting the audio callout may have **no
Lua-readable companion signal at all**. This is the single most architecturally important open
question for any future "naked-eye channel" design — see
`aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md` for the
minimal live-probe that would settle it (log the full HelperAI recursive dump at the exact
voice-callout timestamp during a naked-eye-only pass, no scope slew).

**Session 2 update (2026-09-08, same day):** user-supplied screenshot shows the Mi-24P's native
on-screen radio-message/subtitle panel firing `"9 CONTACTS, 1 O'CLOCK"` from naked-eye spotting
(not scope-selection) — a real ambient signal richer than anything in `list_indication(6)`
(carries contact count + clock bearing). This is DCS's generic `SUBTITLE`-option caption system,
not a Lua UI element already examined; Hoggit's `DCS_server_gameGUI` page (read in full) has no
hook that exposes displayed subtitle text. New lead: `devices.PKV` (registration position 1 in
`indicators_list-grepped.lua`, same position-equals-device-ID method that correctly predicted
ASP17=2 and HelperAI=6) is untested and never fetched from Windows — plausible home for
`OBSERV`/`CAN'T MOVE SIGHT YET`/the contact-count text. **This reopens the "confirmed absent"
conclusion above — do not treat it as settled** until `PKV/Indicator/PKV_init.lua` is read and/or
`list_indication(1)` is live-probed.

**Session 3 correction (same day):** the three ED-forum threads cited only as WebSearch snippets
in Session 2 were read in full after the user pasted their content. Two corrections: (1) the
"~10-second calibration delay" claim (topic 278063) had no basis in the actual thread text —
WebSearch-summary artifact, retracted; (2) topic 366508 ("Petrovich Not Spotting Targets"), cited
as evidence that the voice/audio channel and `list_indication` text channel are independent, was
actually about an unrelated ED-confirmed fog-rendering bug (`fog=Auto` blinded Petrovich outright)
— **not** evidence of channel separation. That citation is retracted; the audio-vs-text-channel
question now has **zero** supporting forum evidence either way, not weak support. Net effect:
forum research is exhausted for this question — only the PKV file fetch or a live probe can
resolve it now. See Session 2 + Session 3 addenda in
`aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`.

**Session 4 (2026-09-09):** `PKV_init.lua` fetched and read — it's a page/mode registration shell
only (page IDs, master modes SIGHT_OFF/SIGHT_ON, `pages_by_mode` dispatch), not the text-tree
definition. It confirms `devices.PKV` = index 1 but points to two unfetched sibling files
(`PKV/Indicator/PKV_base_page.lua`, `PKV/Indicator/PKV_page.lua`) as where the actual
controllers/indicators live — by analogy with `HelperAI_indicator.lua` dispatching into
`HelperAI_page_common.lua`. Grep for contact/o'clock/count across every synced Lua file (7 files)
= zero matches. **Still inconclusive** — need those two PKV page files, or the live probe
(`list_indication(1)` sampled alongside `list_indication(6)` during a naked-eye-only spot).

Related: [[project_aircraft_layer_live_io]], [[project_petrovich_perception]].
