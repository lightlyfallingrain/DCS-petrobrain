# `object_model.py` keyword-table coverage against ED's real DCS type-name catalogue

**Date:** 2026-09-09
**DCS version:** not independently re-verified this session — same source material as
`2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md` Session 5 (`HelperAI_*.lua`
files fetched from the Windows DCS install that session; `2.9.29.27278`)
**Theatre:** n/a (Lua-data/classification question, not terrain-specific)

### Question

`body-layer/src/perception/object_model.py`'s `profile_for()` classifies a `LoGetWorldObjects`
`object_type` string into a size/`op_class` profile via case-insensitive substring keyword
matching, for `perception.visibility`'s angular-radius range threshold and
`perception.naked_eye_source`'s ED-vocabulary output quantisation (PB-1.5,
`plans/pb1.5-naked-eye-detection/plan.md`). The keyword table was hand-authored without
validation against real DCS type strings. A Reviewer pass on PB-1.5's implementation flagged the
`OP_SHIP` keywords (`cruiser`/`frigate`/`corvette`/`destroyer`/`boat`/`ship`) as a likely
domain-mismatch bug: real DCS ship `object_type` values are hull/proper-noun model names
(`"Slava"`, `"leander-gun-achilles"`), not English hull-class descriptors, and the table's own
regression test (`test_ship_keyword`) asserted against a fabricated string (`"Grisha corvette"`)
that would pass even if every real ship type fell through to the fallback. This finding measures
that claim (and spot-checks the SA-3/6/8/9/13/15 keywords the same way) against ED's own
DCS-type-name catalogue, and records the fix's before/after numbers.

### Method

**Resource: ED's own DCS-type -> Petrovich-reporting-name mapping.** The Mi-24P module's
`HelperAI_reporting_names.lua` (fetched from the Windows DCS install; a gitignored copy sits at
`win-mac-sync/from-windows/`, per this project's standing convention for install-derived Lua —
cite this research doc, not that path) contains a complete, literal `[dcs_object_type] =
"petrovich_reporting_name"` table entry for every unit type Petrovich's AI can classify and
report — **595 rows, 376 distinct reporting names**. This is authoritative for what
`LoGetWorldObjects`'s `object_type` field actually contains (the key side of the table), and
the reporting-name side is a far more regular vocabulary than the raw type names, useful for
grouping types by real-world class (ship, SAM system, etc.) without guessing.

All 595 `dcs_object_type` keys were extracted to a scratch TSV and checked programmatically
against `object_model.py`'s keyword table (both the pre-fix and post-fix versions) with a small
script — not a live DCS probe; this is a static-data check, reproducible from the same Lua file
whenever it needs re-running. — **evidence:** reproduced-locally (script run against the fetched
file this session) — **source:** `win-mac-sync/from-windows/HelperAI_reporting_names.lua`
(cited via this doc).

### Findings

**Finding 1 — the `OP_SHIP` domain-mismatch is confirmed, and worse than "unreachable": it was
accidentally "working" via coincidence.** None of the six pre-fix keywords
(`cruiser`/`frigate`/`corvette`/`destroyer`/`boat`/`ship`) ever matches a real ship's
*hull-class* description, because `object_type` never carries one. But the pre-fix table still
classified **6** of the 595 types as `OP_SHIP` — purely because `"boat"`/`"ship"` happen to occur
as literal English-word substrings inside a few unrelated-looking compound identifiers
(`"Dry-cargo ship-1"`, `"Dry-cargo ship-2"`, `"Higgins_boat"`, `"Ship_Tilde_Supply"`,
`"Uboat_VIIC"`, `"speedboat"`). This is not the keyword table "sort of working" — it is
undirected luck (an author writing a descriptive compound identifier happened to embed an
English word), and the other 51 real ship types were completely unreachable
(`"Slava"`-class `"MOSCOW"`, `"KILO"`, `"CVN_71"`, `"leander-gun-achilles"`, etc. — none contain
any of the six keywords). — **evidence:** reproduced-locally — **source:** script run against
`HelperAI_reporting_names.lua`'s 595 `dcs_object_type` keys.

**Finding 2 — the SA-3/6/8/9/13/15 keywords have the identical bug, and are worse: zero
coincidental hits.** The pre-fix keywords (`"sa-3"`, `"sa-6"`, `"sa-8"`, `"sa-9"`, `"sa-13"`,
`"sa-15"`) are NATO reporting-name shorthand, not DCS type strings. Real DCS type names for these
systems are component/hull identifiers with no NATO designation embedded at all: SA-3's launcher
is `"5p73 s-125 ln"`, SA-6's is `"Kub 2P25 ln"`, SA-8's is `"Osa 9A33 ln"`, SA-9's is
`"Strela-1 9P31"`, SA-13's is `"Strela-10M3"`, SA-15's are `"Tor 9A331"` / `"CHAP_TorM2"`. None
of these six keywords matched **any** of the 595 real type names — 0 hits, not even a lucky one.
This means every SA-3/6/8/9/13/15-class object in this project's theatres was silently falling
back to `OP_GROUPSOMETHING` / `DEFAULT_SIZE_M = 5.0` before this fix, despite the table appearing
(by inspection, and by the worked-example test `test_sa3_keyword`, which used a fabricated
`"SA-3 Launcher"` string with the same masking problem as `test_ship_keyword`) to cover these
systems. — **evidence:** reproduced-locally — **source:** same script/file as Finding 1.

**Finding 3 — the ship category is larger than the initial word-based sweep found: 57 real
types, not 47.** A first pass searched reporting names for hull-class words (`"cruiser"`,
`"frigate"`, `"corvette"`, `"destroyer"`, `"boat"`, `"ship"`, `"carrier"`, `"sub"`, `"patrol"`)
and found 47 matching types. Broadening the search (`"vessel"`, `"craft"`, `"tug"`, `"landing"`,
`"cutter"`) found 10 more real naval-vessel types the narrower sweep missed: `"Dry-cargo ship-1"`
/ `"-2"` (civilian cargo vessel), `"HandyWind"` / `"Seawise_Giant"` (civilian tanker vessels —
`Seawise_Giant` is the real-world supertanker), `"HarborTug"` (harbor tug), `"Higgins_boat"`
(WWII landing craft), `"Schnellboot_type_S130"` (WWII fast attack craft), `"ZWEZDNY"` /
`"atconveyor"` (civilian vessel / cargo vessel), `"speedboat"` (fast attack craft). Both sets are
now covered (57 total OP_SHIP keyword entries in the fixed table) — this category is small and
fully enumerable against ED's own list, so covering it exhaustively is not the same class of
scope decision as the open-ended armor/truck vocabulary (see Unresolved). — **evidence:**
reproduced-locally — **source:** same script/file, second broader keyword pass.

**Finding 4 — spot-checking `"tank"` (an existing `OP_ARMORED` keyword, out of this fix's scope)
surfaces the same class of bug elsewhere, unfixed.** `"tank"` currently matches 8 real type names,
and **none of them are armored vehicles**: `"ATZ-60_TANK"`, `"Coach a tank blue"` /
`"...yellow"` (rail coach models), `"German_tank_wagon"` (rail tank car), `"M978 HEMTT Tanker"`
(a wheeled fuel tanker truck), `"S-3B Tanker"` (a carrier-based tanker *aircraft*),
`"TZ-22_TANK"` (a towed fuel tank trailer), `"Tankcartrinity"`. This is the same domain-mismatch
pattern as Findings 1–2 (a plausible English word that doesn't match what it was meant to match,
and additionally *false-positive-matches* several unrelated real types) but was not part of the
Reviewer's required-fix scope (ships + SAM/SPAAG spot-check only) and was not fixed this session
— flagged here as a discovered, not-yet-actioned issue. — **evidence:** reproduced-locally —
**source:** same script/file.

### Coverage numbers (all 595 real `dcs_object_type` values)

| | Before this fix | After this fix |
|---|---|---|
| `OP_GROUPSOMETHING` (fallback) | 525 (88.2%) | 464 (78.0%) |
| `OP_SHIP` | 6 (coincidental, see Finding 1) | 57 |
| `OP_SRSAM` | 0 | 8 |
| `OP_MRSAM` | 0 | 2 |
| `OP_ARMORED` | 23 | 23 (unchanged) |
| `OP_TRUCK` | 19 | 19 (unchanged) |
| `OP_INFANTRY` | 13 | 13 (unchanged) |
| `OP_ZU23` | 8 | 8 (unchanged) |
| `OP_SPAAG` | 1 | 1 (unchanged) |

Overall fallback rate: **88.2% -> 78.0%**. The "before" numbers reproduce exactly what the
Reviewer's prompt cited (`OP_GROUPSOMETHING` 525/88%, `OP_ARMORED` 23, `OP_TRUCK` 19,
`OP_INFANTRY` 13, `OP_ZU23` 8, `OP_SHIP` 6, `OP_SPAAG` 1), confirming this session's script
matches that analysis.

### Unresolved / backlog

- **The remaining 78.0% fallback is still real and mostly out of scope for this fix.** The bulk
  of the 595 types are aircraft/helicopters, buildings, artillery, and SAM systems this table
  never attempted to cover (`object_model.py` targets ground vehicles + ships only; air-target
  classification would be a different, larger scope decision, e.g. `OP_HELI`/`OP_JET` from the
  same ED vocabulary). Deriving a broader table from this same source file remains the backlog
  item the Reviewer already flagged (`plans/pb1.5-naked-eye-detection/review.md`'s "Optional
  Refinements"), now with a concrete resource (`HelperAI_reporting_names.lua`, all 595 rows) and
  a repeatable measurement method (this doc's script) to build it against, rather than guessing.
- **Finding 4's `"tank"` false-positive/false-negative bug is unfixed.** It sits in
  `OP_ARMORED`, not the ships/SAM-SPAAG scope this session's fix covers. Worth a small follow-up
  (likely: a more specific keyword, or an explicit exclusion list for the tanker/rail-wagon false
  positives) the next time `object_model.py` is touched.
- **The 595-row source file itself is not committed to the repo** (gitignored, per this
  project's convention for install-derived Lua under `win-mac-sync/from-windows/`) — only a
  curated ~90-entry sample of individual real type-name strings is committed, at
  `body-layer/tests/fixtures/object_type_coverage_sample.json`, for `object_model.py`'s own
  coverage-floor regression test. Reproducing this doc's full-595 numbers requires re-fetching
  the source file from a Windows DCS install and re-running the extraction script (not itself
  committed; a short one-off, described in Method above).
