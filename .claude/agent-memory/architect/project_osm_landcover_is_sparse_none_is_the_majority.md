---
name: osm-landcover-is-sparse-none-is-the-majority
description: Measured on the real syria-full store — 42-96% of ground positions have NO mapped landcover and only 1-3% are inside forest, so inside_landcover's None can never be read as a positive terrain claim.
metadata:
  type: project
---

Measured 2026-10-13 against `world-model/data/world-model/syria-full.sqlite` (read-only; the probe
is committed as `world-model/tools/measure_landcover_coverage.py`):

| region (±30 km, 2 km grid) | no mapped landcover | inside forest | areal forest |
|---|---|---|---|
| Latakia | **95.9%** | 2.8% | 3.2% |
| Damascus | 79.2% | 1.9% | 2.0% |
| Aleppo | 62.7% | 0.4% | 0.6% |
| Hama | 42.0% | 0.8% | 0.8% |
| Palmyra | 96.1% | 0.0% | 0.0% |

Of 44,811 landcover polygons: `built_up` 25,446 · `fields` 21,428 · **`forest` 9,710** ·
`orchard` 7,171 · `scrub` 4,027 · `barren` 2,475.

**Why it matters:** `describe_position`'s `inside_landcover` returns `None` for *"open ground or
simply unmapped"*, and these numbers say unmapped is the **majority** case everywhere and the
overwhelming one in the forested coastal belt. So any design that treats `None` as a positive claim
about the ground is wrong by 42–96%. In `plans/forest-occlusion/plan.md` the choice was between
"unmapped = open" (permissive) and "unmapped = forest" (blinding); the second would have blinded
Petrovich on most ground units in the theatre. The table is what decided it, in one command.

**How to apply:** before designing any behaviour keyed on a landcover class — a gate, a spoken
fact, a confidence term — run that probe for the region concerned. Two numbers are needed and
neither is guessable: the positive rate (how often it fires) and the `None` rate (how often the
data simply is not there). Also: the areal fraction and the road-adjacent fraction **disagree**
(roads avoid woods), so sample both and say which one the design depends on.

Cost figure from the same pass, in case a per-candidate landcover test is ever contemplated:
`store.reader.containing_polygons(conn, ["landcover"], x, z)` is **0.075 ms median / 0.271 ms p95**
per point — against `describe_position`'s 84.6 ms in situ (`BL-11` amendment A7). Still 15 ms for
200 candidates, i.e. past a 12.6 ms poll budget uncached, so gate ordering and a quantised-position
memo are both load-bearing.

Related: [[bl11-stage4-orphaned-the-offline-los-primitive]],
[[find-n-in-the-repo-before-accepting-n-is-more-than-we-need]].
