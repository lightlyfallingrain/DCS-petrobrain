# SA-2 (S-75 Volkhov) components: what `op_class` do they actually get, and from where

**Date:** 2026-11-12
**DCS version:** not re-verified this session — same source material as the two cited prior
sessions (`aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`
Session 5, DCS `2.9.29.27278`; `aircraft-layer/research/2026-09-09-object-model-keyword-coverage.md`)
**Theatre:** n/a (Lua-data/classification question, not terrain-specific)

### Question

What `op_class` does HelperAI/`HelperAI_lengths_ng.lua` (or whatever DCS internals actually drive
Petrovich's ambient classification) assign to the four real DCS `object_type` strings for SA-2
(S-75 Volkhov) components — `SNR_75V`, `RD_75`, `S_75M_Volhov`, `S_75_Zil_Trailer` — before adding
rows for them to `body-layer/src/perception/object_model.py`'s `_KEYWORD_PROFILES`?

### Findings

**The premise of the question does not hold — no DCS/HelperAI source assigns a per-unit-type
`op_class` to anything, SA-2 included.** This is the single thing that had to be settled before the
SA-2 rows themselves could be reasoned about. — **evidence: documented (re-confirmed by re-reading
the two research docs this project already has, not re-probed this session)**:

- `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md` Session 6,
  Q2 (full exhaustive read of `HelperAI_lengths_ng.lua`'s 131-line fragment table): `OP_SRSAM`/
  `OP_MRSAM`/`OP_LRSAM` are three composed-speech *vocabulary fragments* in Petrovich's ambient
  "N contacts, H o'clock" callout — a coarse range-tier *word*, nothing more. **"No
  specific-unit-type vocabulary exists in this bank at all... there is no per-model fragment (no
  'T-72', no 'Ural', no 'SA-3' specifically — only the SAM-*range-tier* classes
  `OP_SRSAM`/`OP_MRSAM`/`OP_LRSAM`)."** There is no table anywhere in that file, or any other Lua
  file read across six sessions of recon, that maps a specific DCS `object_type` (or even a NATO
  SAM designation) to one of these three fragments. The native code that decides *which* fragment
  to speak for a given target is compiled and was never reached by any Lua grep.
- `aircraft-layer/research/2026-09-09-object-model-keyword-coverage.md`'s "What was deliberately
  left uncovered" section states this explicitly for exactly the case this investigation is
  about: *"standalone SAM-system radars/command posts beyond IRIS-T (Patriot, Hawk, NASAMS,
  Roland, Rapier, **SA-2**/5/10/11's many radar/CP/launcher components) were not attempted —
  assigning them a correct SR/MR/LR class needs real-world per-system verification this pass
  didn't do."* SA-2 is named by name as a known, not-yet-attempted gap, not as something already
  resolved.

**Consequence: the existing SA-3/SA-6/SA-8/9/13/15/SA-10 `op_class` rows already in
`object_model.py` are this project's own real-world-knowledge judgment calls, not an extraction
from any ED source.** What *was* verified against real DCS data for those rows is narrower than it
reads at first: `object_model.py`'s own docstring and the 2026-09-09 research doc confirm the
verification was "does this keyword string occur as a substring of a real DCS `object_type`" (a
string-matching feasibility check against the 595-row `HelperAI_reporting_names.lua` catalogue),
**not** "does ED's own native classification agree this system is short/medium/long range." No
such native agreement was ever checked, because — per the finding above — there is nothing to
check it against. — **evidence: documented**, same two sources.

**The project's own range-tier assignments, cross-checked against real max engagement ranges
already committed in this repo (`body-layer/data/threat_envelopes.json`, sourced from
`wiki.hoggitworld.com/view/Threat_Database`):**

| system | `object_model.py` `op_class` | real `range_max_m` (threat_envelopes.json) |
|---|---|---|
| S-125 / SA-3 | `OP_SRSAM` | 25,002 m (~25.0 km) |
| 2K12 Kub / SA-6 | `OP_MRSAM` | 35,558 m (~35.6 km) |
| S-300PS / SA-10 | `OP_LRSAM` | 74,080 m (~74.1 km) |
| **S-75 Devina / SA-2** | **not yet assigned** | **51,856 m (~51.9 km)** |

— **evidence: reproduced-locally** (read directly from `body-layer/data/threat_envelopes.json`
this session; the SA-3/SA-6/SA-10 `op_class` values are read directly from
`body-layer/src/perception/object_model.py`'s `_KEYWORD_PROFILES`, lines 246–320).

SA-2's real 51.9 km reach sits **between** the project's existing MRSAM example (Kub, 35.6 km) and
its LRSAM example (S-300, 74.1 km) — materially closer to S-300's figure than to Kub's in absolute
terms (51.9/74.1 ≈ 70% of the LRSAM anchor vs. 51.9/35.6 ≈ 146% of the MRSAM anchor), but this is
offered as context for Architect's decision, not as a resolved answer — `threat.py`'s own module
docstring (line 51–57) already records that this project's SR/MR/LR buckets are not drawn to a
single consistent km threshold (`OP_SRSAM` itself spans SA-3's ~25 km down to SA-13's ~5.2 km, a
~5x internal spread) and explicitly calls that "a property of this project's own `op_class`
buckets, not a defect." So there is no bright line in this project's existing scheme that a 51.9 km
system crosses unambiguously into one bucket or the other; it is a judgment call the SA-3/SA-6/SA-10
rows already made the same way, now facing a harder case than any of those three.

**On the component question (rangefinder/trailer vs. radar/launcher) — real DCS type strings and
reporting names confirmed, no HelperAI classification gate found for any of them:**

All four strings exist in the committed, already-verified
`body-layer/src/perception/data/dcs_type_to_reporting_name.tsv` (the same 595-row
`HelperAI_reporting_names.lua` extraction the SA-3/SA-6/S-300 rows were checked against):

```
RD_75           -> "SA-2 rangefinder"           (line 369)
SNR_75V         -> "SA-2 Fan Song radar"         (line 407)
S_75M_Volhov    -> "SA-2 launcher"               (line 409)
S_75_Zil_Trailer -> "SA-2 missile trailer"       (line 411)
```

— **evidence: reproduced-locally** (grep against the committed TSV this session).

**All four appear in Petrovich's reporting-name vocabulary, so none of them "falls through to
unclassified" in the sense the task description asked about** — that's a different question from
op_class, and the answer to it is no: the reporting-name table (what text appears in the scope
channel's `list_indication`) has a row for every one of the four, including the rangefinder and
the trailer. What has **no** source anywhere is a native op_class gate for any of them — same
finding as above, repeated here because a rangefinder/trailer could plausibly be the one case
HelperAI's ambient vocabulary skips as "not a weapon-bearing unit"; it is not skipped from the
*reporting-name* vocabulary, and there is no evidence either way about the *ambient-callout*
vocabulary specifically, because (as established above) no per-type gate into that vocabulary
exists in any readable source for any system, SA-2 included.

**There is existing precedent in this file for how to bucket a non-launcher component of a fixed
SAM site**, worth surfacing since it bears directly on `RD_75`/`SNR_75V`/`S_75_Zil_Trailer`: the
S-300's two radar rows (`"s-300ps 40b6m tr"`, `"s-300ps 64h6e sr"`) both carry
`op_class="OP_LRSAM"` despite being radars, not launchers — the project's existing convention
is that `op_class` represents "this is part of a [range-tier] SAM site," not "this specific
sub-component is itself the weapon." Both S-300 rows also carry `installation_component=True`,
matching the existing S-125 (SA-3) launcher row's own `installation_component=True` — the
documented rule (`ObjectTypeProfile.installation_component`'s docstring) is that this flag is set
for "a genuine fixed, multi-component air-defence site," which real-world S-75 unambiguously is
(`body-layer/research/2026-10-01-sam-site-geometry.md`'s own S-75 section: "classic
'flower'/star site... control van," cited there as real S-75 doctrine, not this project's
invention).

### Reproducible Test

This was a static-data/document-review question, not a live-DCS probe — nothing new to run. The
checks that *would* upgrade "no HelperAI classification gate exists" from "documented absence
across six recon sessions" to a harder negative:

1. Re-run the exhaustive `grep -rIi` sweep (already performed once, per
   `2026-09-08-...md` Session 5 Finding 4) for any literal SA-2-specific string inside
   `HelperAI_lengths_ng.lua`'s native-code-facing filename table and the compiled `Mi24.dll`/
   `CockpitMi24.dll` — not expected to find anything new (the fragment table is coarse-class-only
   by construction, confirmed exhaustively for every class, not just SA-2), but would close the
   "could be a hashed/non-literal comparison" caveat the prior session already flagged for a
   structurally identical question (Session 6, Q1's caveat).
2. A live probe is not useful here: even a confirmed live `list_indication`/ambient-callout sample
   naming an SA-2 unit as "short/medium/long range SAM" would tell us ED's *speech* output for
   that encounter, not a general per-type rule — and Session 5/6 already established the ambient
   channel is not reliably Lua-observable in the first place (the callout is native-composed, and
   whether any exported value mirrors it is still the project's single oldest open recon question,
   unresolved since 2026-09-08).

### Possible Approaches

Since there is no ED source to defer to, this is squarely an Architect/user decision, not something
this investigation can resolve further. Two shapes worth naming:

1. **Treat SA-2 as its own bucket decision, informed by the real range table above.** 51.9 km is
   closer to the LRSAM anchor (S-300, 74.1 km) than to the MRSAM anchor (Kub, 35.6 km) by the ratio
   test above, but this project's own `OP_SRSAM` bucket already tolerates a ~5x internal spread
   without being called a defect — so "SA-2 is MRSAM, just at the top of that bucket's range" is
   not obviously wrong either, and would keep `OP_LRSAM` as "only the genuinely very-long-reach
   systems" (S-300 is the only current member). Architect's call, with both numbers now on the
   table.
2. **All four components should likely share one `op_class`** (whichever bucket SA-2 is given),
   with `installation_component=True` on all four — matching the S-300/S-125 precedent that a
   fixed multi-component site's radar and launcher rows get the same class, not a
   "radar is special" exception. `RD_75` (rangefinder) and `S_75_Zil_Trailer` (missile trailer)
   have no weapon of their own, same as the S-300's two radar rows, and the existing convention
   treats that as irrelevant to `op_class` (which tags "part of this kind of site," not "this
   specific object can shoot you").
3. **Keyword specificity**: `"s_75"`/`"s-75"` as a shared prefix would need checking for false
   positives the same way every other row in this table was (per the module's own stated
   methodology) — not done this session, since it is a one-line check once the op_class decision
   is made, and is implementation work, not recon.

### Unresolved

- Whether SA-2 should be `OP_MRSAM` or `OP_LRSAM` is a genuine open judgment call, not a fact this
  investigation can supply — flagged to Architect with the real-range comparison table above as
  the deciding evidence, per this project's standing "report the finding, don't decide the
  architectural implication" rule.
- Whether the native ambient-callout composer ever actually speaks SA-2 as a SAM-range-tier word
  at all (vs. some other fragment, or never appearing in the ambient channel because the HelperAI
  classification channel's gate is weapon-selection/NABL-dependent in a way this project has not
  fully mapped) remains the project's oldest open recon item and is unrelated to the keyword-table
  decision above — the keyword table drives this project's *own* `op_class` tagging for the
  scope/reporting-name and naked-eye channels, not anything DCS natively speaks.
