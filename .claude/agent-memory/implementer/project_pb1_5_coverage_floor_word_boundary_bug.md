---
name: project-pb1-5-coverage-floor-word-boundary-bug
description: A naive substring keyword check for "is this reporting name an aircraft" miscategorized two real SAM systems (SA-6, SA-10) as aircraft because of bare A-6/A-10 keywords.
metadata:
  type: project
---

While rebuilding `body-layer/tests/fixtures/object_type_coverage_sample.json`'s `"ground"`
bucket as a full enumeration (see [[feedback_coverage_floor_needs_real_nulls]]), an ad hoc
categorization script classified each of the 595 real `dcs_object_type` rows (from
`body-layer/src/perception/data/dcs_type_to_reporting_name.tsv`) into ship/wwii/air/ground using
plain `keyword in text.lower()` substring checks for the "air" bucket (aircraft type designators
like `"f-16"`, `"a-10"`, `"mig-29"`).

**What broke:** bare `"a-6"` (A-6 Intruder) and `"a-10"` (A-10 Warthog) matched *inside*
`"SA-6 launcher"` and `"SA-10 Flap Lid radar"` respectively — both real SAM-system ground types,
not aircraft. This would have silently dropped both from the ground population, exactly the
Finding-1/Finding-4-shaped domain-mismatch bug this whole coverage-fixture rework exists to
catch (see `aircraft-layer/research/2026-09-09-object-model-keyword-coverage.md`) — reintroduced
one layer up, in the test tooling itself.

**How it was caught:** cross-checked the new categorization against every entry already present
in the *previous* (pre-rework) fixture as a subset invariant — the old fixture's `"ground"`/
`"ground_deferred"` buckets already had both `"Kub 2P25 ln"` (SA-6) and `"S-300PS 40B6M tr"`
(SA-10) correctly bucketed as ground, so the invariant check failed loudly until the keyword
matching was made word-boundary-safe (regex with `(?<![a-z0-9])keyword(?![a-z0-9])` instead of
bare `in`).

**How to apply:** DCS's `"SA-N"` NATO SAM-designation convention collides with several Western
aircraft type codes as bare substrings (`A-6`, `A-10`, likely others at larger N). Any future
script matching real DCS reporting names/type strings against short alphanumeric keyword lists
must use word-boundary-safe matching, not bare substring containment — and should be validated
against a known-good prior categorization as a subset check before being trusted, not just
spot-checked by eye.
