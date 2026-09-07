---
name: petrovich-perception-recon
description: Whether Mi-24P Petrovich AI gunner's target/detection state is externally extractable (PB-0 blocker)
metadata:
  type: project
---

2026-09-07 desk-research pass (no DCS access this session): no confirmed external channel exists for
Petrovich's target list. DCS-BIOS's actual Mi-24P.lua module (read directly from
DCS-Skunkworks/dcs-bios on GitHub) defines only clickable-cockpit device/arg pairs for the gunner
station (I9K113 Shturm sight dev7, PUVL dev6, ASP-17V dev16, ASO-2V dev9) — zero Petrovich/HelperAI/
target-list state. This extends the prior aircraft-layer finding (FC3-only TWS functions, "we don't
normally export these sorts of things" — ED-Skunkworks maintainer) specifically to Petrovich.

VAICOM PRO's Mi-24P support is confirmed radio-only, explicitly excludes Petrovich functions. No
community precedent found for reading Petrovich target awareness externally — genuinely unexplored.

**UPDATE (same session, part 2):** user retrieved and pasted all 4 relevant files from the Windows box
(`HelperAI_indicator.lua`, `HelperAI_page.lua`, `HelperAI_page_common.lua`, `elements_defs.lua`) plus
both forum threads' full content (previously 403'd). Read in full — **zero `get_param_handle` calls
anywhere**; Petrovich's target-list/crosshair UI uses named `controllers` (`middle_list_text`,
`upper_list_text`, `lower_list_text`, `az_text`, `el_text`, `hdg_text`, `list_red_arrow`, etc.) resolved
by DCS's native/compiled indicator dispatch, not Lua. The get_param_handle lead is **falsified for this
file chain**. New positive lead: these controller names plausibly match what `list_indication()`/
`list_cockpit_params()` are built to query (confirmed real+usable via a forum reply from Bailey, a known
DCS-BIOS/export-tooling author — needs a Hook-script or DCS-BIOS-lua-console context per another reply,
Export.lua-specific callability still unconfirmed). **Confirmed negative: no range field exists anywhere
in Petrovich's UI** — only heading/azimuth/elevation angles; range must always be derived externally
(ownship pos + LOS/terrain ray-cast) even in the best-case extraction scenario. Still-open: HelperAI's
device ID (needed for `list_indication(n)`), whether controllers are individually addressable or one
blob, list-row string content format, target-ID persistence — all need a live in-mission probe.

Full findings (now much stronger, primary-source-based): `aircraft-layer/research/2026-09-07-petrovich-perception-export.md`.

**Session 2 (same day, PoC attempt) — no live DCS access this session either; desk research only, but stronger.**
Found real, actively-used community code (`asherao/DCS-ExportScripts`, LGPL-3.0, fork of `s-d-a/DCS-ExportScripts`,
106 stars) whose `ExportsModules/Mi-24P.lua` calls `list_indication(8)` directly from Export.lua for THIS aircraft
(kneeboard chaff/flare counters, not HelperAI) — **falsifies PravusJSB's "needs a Hook" claim, at least generally**;
Export.lua-callability of `list_indication` for Mi-24P is now confirmed-via-real-code, not inferred. Its
`lib/Tools.lua` `getListIndicatorValue()` shows the exact wire format: `list_indication(n)` returns one raw STRING
(not a table) with repeating blocks `-----...-----\n<Key>\n<Value>\n`, one block per currently-populated named
controller — resolves "blob vs individually-addressable" as "both": one string call, but controller names appear
as parseable keys inside it. Still open: HelperAI's own device ID (needs `device_init.lua` from Windows box,
filename/path itself unconfirmed), whether absent-controller-when-no-target holds, target-ID persistence.
`LoGetWorldObjects` coalition/visibility scope now CONFIRMED (user pasted the 403'd forum thread's opening
post): global/unfiltered in multiplayer by default (returns all connected aircraft/objects, no own-aircraft
filter built in) — matches the Session 1 fallback-design assumption, primary-source-confirmed not inferred.
Same post flags an edge case: export sometimes fails on public multiplayer servers, works locally (low risk
for this project — own DCS instance). `LoGetWorldObjects` field list
(ID/Name/Country/Coalition/LatLongAlt/Heading, no Pitch/Bank/Yaw; Country/Coalition still search-summary-only)
is otherwise search-summary-sourced, not a primary Hoggit page read (couldn't find correct URL slug, 404'd 3x).
Licensing note for Architect: DCS-ExportScripts is
LGPL-3.0, reusable, but recommended reimplementing its ~15-line list_indication-parsing pattern directly rather
than adopting the whole framework, consistent with this project's stdlib-only/"deliberately dumb" Export.lua policy.
