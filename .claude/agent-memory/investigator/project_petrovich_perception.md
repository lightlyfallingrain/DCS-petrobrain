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
