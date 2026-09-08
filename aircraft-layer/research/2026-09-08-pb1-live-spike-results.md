# PB-1 live spike results (2026-09-08)

Follow-up to `2026-09-07-petrovich-perception-export.md`, whose central open lead was
"live-probe-only" territory. This note records the actual live-DCS results from
`plans/pb1-perception-logger/plan.md` stage 1, run across 4 test flights by the user with an
iteratively-updated test `Export.lua` (`win-mac-sync/to-windows/Export.lua`, disposable, not
merged).

## Method

Mi-24P test sorties with manually-placed ground targets (Ural trucks), debug-log-gated probes
added incrementally as each run's result suggested the next candidate API. `HELPERAI_DEVICE_ID`
confirmed as `6` (0-indexed position in `indicators_list-grepped.lua` matched
`ccHelperAIIndicator_Mi24`'s registration order); `ASP17_DEVICE_ID` confirmed as `2`
(`ccASP17`'s position) the same way.

## Findings, in order tested

**1. `list_indication(6)` (HelperAI) — CONFIRMED WORKING, classification text only.**
Run 2+ (once a target was actually selected, not just spotted) returned real, changing content:
`middle_list_text` / `lower_list_text` / `lower_lower_list_text` = `"Ural truck"`. This is
Petrovich's own spotting/"eyesight" callout channel (the voice callouts the user described live:
"truck, 11 o'clock") — a real, per-frame, non-omniscient signal that Petrovich actually noticed
something, with a coarse classification string. **No numeric field of any kind appears anywhere
in this dump** — the `crosshair` child (which Session 1's file read predicted would carry
`az_text`/`el_text`/`hdg_text`) stayed empty (`children are {}`) across all ~4000 samples spanning
4 flights, including flights where the sight was actively used. Those three controller names never
appeared even once. Wire format matches Session 2's finding exactly: nested tree
(`-----...-----\n<name>\n<value-if-any>\nchildren are {...}`), not the flat one-block-per-controller
shape originally guessed from the kneeboard example — recursive, with values only on leaf text
nodes.

**2. `LoGetTargetInformation()` / `LoGetLockedTargetInformation()` / `LoGetSightingSystemInfo()` —
DEAD END, confirmed nil.** All three returned `nil` for an entire flight (run 3), sampled every
~0.2s, despite `LoIsSensorExportAllowed() == true` throughout. This is a clean, direct
confirmation of Session 1 finding 5 (the ED-Skunkworks maintainer's "FC3-legacy, we don't
normally export these" claim) — these functions exist and are documented (found verbatim in
`Export.lua.reference-file-from-DCS-installation.lua`, the stock template shipped with this DCS
install, including a `distance` field on `LoGetTargetInformation`'s target table and a
`ScanZone.position.distance_manual` field on `LoGetSightingSystemInfo` for `Manufacturer=="RUS"`
sights) but are simply never populated for Petrovich/Mi-24P. Not worth further investigation.

**3. ASP-17 optical sight (`list_indication(2)`) — DEAD END for geometry, structurally
explained.** Correctly enumerates real controller names (`SymbologyBox`, `total_field_of_view`,
`asp17_grid`, `FlexCross` and its children `RollPointer`/`FlexCrossLine1-4`/`distance_border`/
`Distance_Sector`/`effective_distance_sector`) — confirming `list_indication`'s tree-walk reaches
this device fine — but **every value was empty across all samples in every flight** (run 3: 315
samples, 1 distinct body; run 4: 567 samples, 1 distinct body). Reading
`win-mac-sync/from-windows/asp17/ASP_17V_page.lua` (primary source, retrieved this session)
explains why: these elements' `.controllers` entries (`{"FlexSight_Pos"}`, `{"FlexSight_Distance"}`,
`{"FlexSight_Effective_Dist"}`, etc.) are geometric/numeric animation-drive params (position
offsets, sector angles), not text — `list_indication` has nothing to print for a non-text
controller, hence the name-with-empty-value pattern every time.

**4. `get_param_handle("FlexSight_Pos"/"FlexSight_Distance"/"FlexSight_Effective_Dist"):get()` —
DEAD END, confirmed stuck at 0.** Following directly from finding 3's explanation, this is the
standard Export API for reading a named cockpit param as a number regardless of text-addressing.
The call mechanism works (no errors, no nil) — genuinely callable from Export.lua, closing out
Session 1's original central open lead in the general sense — but all three params returned
exactly `0` for all 252 samples in run 4, even though HelperAI's list (probe 1, same flight,
same time window) shows real changing detection content, confirming a target genuinely was
tracked. These specific named params do not reflect live sight state via this read path, for
reasons not further investigated (could be a naming/handle mismatch, a param the render pipeline
sets on the GPU/native side rather than through the Lua-visible param-handle table, or a
different naming convention entirely — not resolvable by more live probing without another primary
source, e.g. compiled engine internals, which this project treats as out of scope, see
"Reverse-engineering scope decision" below).

## Reverse-engineering scope decision (2026-09-08, user-directed)

User asked directly whether reverse-engineering (or actively affecting) DCS's compiled
Petrovich-detection engine internals was worth pursuing, given the Lua-side leads are now
exhausted. Answered and accepted: **out of scope.** Petrovich's detection logic is confirmed
compiled/native (Session 1 finding 6: "no definitions for Petrovich AI... exist anywhere in
[HelperAI's Lua] module file"), not reachable via any documented Lua/Export API. Reaching it would
require memory-reading/DLL-injection-class reverse engineering — a different order of engineering
effort than anything else in this project, no sanctioned API surface, breaks DCS's EULA/anti-cheat
posture, fragile across every game patch, and directly violates this project's own
read-only-DCS-access invariant (`world-model/docs/CONVENTIONS.md`). Not pursued; not planned.

## Net conclusion for PB-1 design

Every numeric-geometry channel tested (4 independent APIs/mechanisms across 4 live flights) is
dead. The one channel that works is real, live-confirmed, and valuable in a different way: a
genuine "Petrovich actually noticed this, and here's roughly what he thinks it is" signal, text
classification only, no position data. This converges the tier design cleanly:

- **Detection gate**: HelperAI's `list_indication(6)` parsed for populated `middle_list_text`
  (and siblings) — real, non-synthetic, bounded by what Petrovich's own AI actually flagged.
  Satisfies the "Petrovich must not be omniscient" invariant structurally, not via a heuristic.
- **Geometry (bearing/range/position)**: must come from `body-layer/src/perception/geometry.py`'s
  already-built ownship + `LoGetWorldObjects` derivation (already implemented per
  `plans/pb1-perception-logger/plan.md` stages 2-3) — no tier ever gets this from Petrovich's own
  systems directly, confirmed now across every tested channel, not just the two the original
  research anticipated.
- **Association problem, newly surfaced**: HelperAI's text carries no stable ID and no
  position — matching "Ural truck" to a specific `LoGetWorldObjects` entry (when several similar
  objects exist nearby) is an open design question the original two-tier plan didn't need to
  solve, since Tier 3 never needed to associate against a real detection event. This is the
  concrete design gap for Architect to resolve, not a re-run of stage 1's spike.

This is neither the plan's original "Tier 1" (a full real feed with real bearing) nor "Tier 3" (a
pure geometric proxy) — it's a hybrid the two-tier framing didn't anticipate: real detection
existence + gated classification, synthetic geometry. `plans/pb1-perception-logger/plan.md`'s
stage 4 branch ("Tier 1 succeeded" vs. "Tier 1 failed") needs to be replaced with this hybrid
design rather than picked between as originally framed.
