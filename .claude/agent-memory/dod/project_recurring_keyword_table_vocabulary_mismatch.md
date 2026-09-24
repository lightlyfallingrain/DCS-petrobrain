---
name: recurring-keyword-table-vocabulary-mismatch
description: 3rd occurrence of two independently-authored keyword/name tables silently under-joining because they use different naming conventions for the same real-world things.
metadata:
  type: project
---

Three separate occasions now where code joins two vocabularies that were each authored
independently, and the join silently under-covers rather than erroring:

1. PB-2 Stage 0 — scope-channel type-match scored 0 on real objects because DCS internal type
   strings (`"5p73 s-125 ln"`) never matched ED's human-readable reporting names
   (`"SA-3 launcher"`).
2. Vision-range-calibration — F10-map display names (`"T-62"`, `"BMD1"`) failed
   `object_model.profile_for` lookup against raw `LoGetWorldObjects` type strings (`"T-62M"`,
   `"BMD-1"`), because F10 labels diverge from raw DCS type spellings.
3. watch-reporting (2026-09-24) — `belief.threat._derive_class_envelopes` joins
   `threat_envelopes.json`'s Hoggit-wiki unit names through `object_model.profile_for`'s
   DCS-type-keyed table; only ~3 of ~19 SAM/AAA rows actually match, because the two tables were
   authored against different naming sources.

**Why: `object_model.profile_for`'s keyword table is the recurring collision point** — it was
built against DCS internal/raw type strings, and every external data source (F10 labels, Hoggit
wiki names, any future imported table) speaks a different vocabulary. Each of the three fixes so
far treated its own symptom locally (independent fixture truth, a documented backlog item) rather
than giving `object_model.py` a canonical cross-vocabulary alias table.

**How to apply:** when a plan or implementation introduces a join through
`object_model.profile_for` (or any keyword-matched lookup) against a table sourced from outside
this codebase's own DCS-internal naming, flag the join-rate risk explicitly during Architect or
Implementer, before it ships — check a sample of the join, don't assume substring matching will
catch real-world name variants. This is now a 3rd recurrence at DoD/backlog-discovery time; worth
raising at Architect instead of being found three times running.
