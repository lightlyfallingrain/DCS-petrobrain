---
name: op-class-sam-tiers-are-project-judgment
description: HelperAI_lengths_ng.lua's OP_SRSAM/OP_MRSAM/OP_LRSAM are ambient-callout speech vocabulary only -- no DCS/HelperAI source maps a specific unit type to one of them. object_model.py's existing SAM op_class rows are this project's own real-world-range judgment calls, cross-checkable against body-layer/data/threat_envelopes.json.
metadata:
  type: reference
---

**When asked "what op_class does HelperAI/ED assign to SAM system X" -- stop and check this first.**
The premise is usually false. Confirmed across six recon sessions
(`aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md` Session 6
Q2, exhaustive read of `HelperAI_lengths_ng.lua`'s full fragment table): `OP_SRSAM`/`OP_MRSAM`/
`OP_LRSAM` are three coarse range-tier *words* in Petrovich's composed ambient "N contacts, H
o'clock" callout vocabulary -- nothing maps a specific DCS `object_type` (or even a NATO SAM
designation) to one of the three. The native composer that picks a fragment is compiled and
unreachable from any Lua grep across the whole install.

**Consequence: every SAM-system `op_class` row already in `body-layer/src/perception/
object_model.py`'s `_KEYWORD_PROFILES` (S-125/SA-3, 2K12 Kub/SA-6, S-300/SA-10, etc.) is this
project's own real-world-range judgment call, not an ED/HelperAI classification.** What *was*
verified against real DCS data for those rows is only "does this keyword substring-match a real
DCS `object_type`" (against `HelperAI_reporting_names.lua`'s 595-row catalogue, committed at
`body-layer/src/perception/data/dcs_type_to_reporting_name.tsv`) -- never "does ED agree this is
short/medium/long range." `aircraft-layer/research/2026-09-09-object-model-keyword-coverage.md`
names this gap explicitly for every SAM system beyond the handful it covered: "SA-2/5/10/11's many
radar/CP/launcher components ... were not attempted -- assigning them a correct SR/MR/LR class
needs real-world per-system verification this pass didn't do."

**The right tool for that real-world verification already exists in the repo**:
`body-layer/data/threat_envelopes.json` (28 entries, Hoggit wiki `Threat_Database` extraction,
`range_max_m` per system). Cross-check a new system's real max range against the existing bucket
anchors before recommending a tier -- as of 2026-11-12: `OP_SRSAM` anchor S-125/SA-3 ≈ 25.0 km,
`OP_MRSAM` anchor 2K12 Kub/SA-6 ≈ 35.6 km, `OP_LRSAM` anchor S-300PS/SA-10 ≈ 74.1 km. This
project's own `threat.py` module docstring (lines 51-57) already documents that these buckets are
not drawn to one consistent km threshold (`OP_SRSAM` alone spans ~5.2-25 km) and calls that a
known property, not a defect -- so don't expect a bright line; report the real-range comparison
and let Architect pick the bucket, per the standing "report, don't decide the architectural
implication" rule.

See [[body-layer/research/2026-11-12-sa2-op-class-assignment.md]] for the worked SA-2 case (which
op_class it should be is still open -- 51.9 km sits between the MRSAM and LRSAM anchors).

**Separately confirmed, same session**: a SAM site's non-weapon components (rangefinder, missile
trailer) have real reporting-name rows in the 595-row TSV just like the radar/launcher do -- they
don't "fall through to unclassified" in the reporting-name vocabulary. Whether they get an
`op_class` at all is a design choice, not a DCS fact: the S-300 precedent in `object_model.py` is
that a fixed site's *radar* rows get the *same* `op_class` as the launcher (tagging "part of this
kind of site," not "this object can shoot you") plus `installation_component=True` -- worth
applying by analogy to a rangefinder/trailer, but that's an extension of precedent, not a verified
fact about those specific DCS types.
