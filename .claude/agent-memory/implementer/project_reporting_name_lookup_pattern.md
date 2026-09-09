---
name: project-reporting-name-lookup-pattern
description: For DCS object_type-keyed keyword matching, resolve to ED's regular reporting-name vocabulary as a second pass instead of hand-authoring more raw-type regexes.
metadata:
  type: project
---

`body-layer/src/perception/object_model.py`'s modern-ground-unit coverage fix (session
2026-09-09, `aircraft-layer/research/2026-09-09-object-model-keyword-coverage.md`'s "Update"
section, `plans/pb1.5-naked-eye-detection/implementation.md`) established a reusable pattern:
when a DCS-sourced identifier field is irregular (`object_type` values like `CHAP_T90M`,
`ATZ-5`, `B600_drivable`), don't keep hand-authoring more raw-string keywords/regexes against it
— check whether `HelperAI_reporting_names.lua`'s 595-row DCS-type -> reporting-name mapping
covers the same types under a *regular* name (`T-90M`, `Ural fuel truck`, `Aircraft tug`) and
key a second pass on that instead. The mapping is committed at
`body-layer/src/perception/data/dcs_type_to_reporting_name.tsv`, loaded via
`perception/reporting_names.py`'s `reporting_name_for()`.

**Why:** raw `object_type` naming is inconsistent by design (internal DCS asset/module IDs);
ED's own reporting-name vocabulary is what Petrovich's AI itself speaks, and is far more regular
because it's meant for humans. Coverage against real data went from ~24% to ~64.5% (304-type
modern-ground denominator) essentially "for free" once matching moved to the right vocabulary,
with roughly the same keyword-table size.

**How to apply:** any future module facing the same "raw DCS identifier is irregular, keyword
table coverage is thin" problem (not just object_model.py) should check this mapping first
before assuming a bigger/fuzzier matcher is needed. Two guardrails that made this safe:
(1) try the existing raw-string table first, unconditionally — the reporting-name pass only
runs when that finds nothing, so it's additive/zero-regression by construction; (2) any
deliberately-excluded category (here: WWII units, via ED's own `"Old "` reporting-name prefix)
needs an explicit skip-guard in code, not just "don't add a keyword for it" — a broad keyword
aimed at the in-scope category (`"truck"`) will otherwise catch it anyway since the guard-less
default is "match if the substring is there."

Related: [[feedback-verify-keyword-vocab-against-real-strings]] (the discipline of checking
every new keyword against real reporting-name/type strings for collisions before adding it —
same script-based method, extended here to the second table).
