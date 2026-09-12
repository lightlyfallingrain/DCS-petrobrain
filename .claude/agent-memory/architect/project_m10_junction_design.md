---
name: m10-junction-design
description: M10 road-junction milestone's arm-counting resolution and a pipeline.py doc discrepancy found while planning it
metadata:
  type: project
---

M10 (road-network junctions, `plans/m10-road-junctions/plan.md`) resolved an open question
the tactical-landmarks parent plan left unsettled: whether a junction's "degree" counts
distinct `road` feature ids or something else. Resolution: **degree = sum of arms**, where
every road endpoint at a clustered coordinate contributes 1 arm and every
endpoint-landing-on-another-road's-interior-vertex (T-junction) contributes 2 arms for the
through-road (it continues in both directions) + 1 for the terminating road. This makes a
plain 2-road endpoint coincidence (degree 2, likely just one physical road split into two
`.routes` polylines) correctly excluded, while a genuine T-junction (only 2 distinct road
ids, but degree 3) is correctly included. Reusable if a future milestone (e.g. the
backlogged "bridges" feature, road x water intersection, explicitly flagged as reusing the
junction-clustering technique) needs the same arm-vs-feature-id distinction.

**Why**: the parent plan's own phrasing ("≥3 distinct road feature ids") would either drop
every T-junction (which are only 2 feature ids per the recon's own methodology) or force
counting interior-vertex matches as full "feature ids" which double-counts nothing
structurally meaningful. Sum-of-arms is the smallest rule that matches both the recon's
"T-junction's third route counts as 3" framing and the "2 is just route continuation"
exclusion the parent plan already committed to.

**How to apply**: any future road-topology feature (bridges, more junction subtypes) that
clusters `.routes`-derived endpoints/interior vertices should reuse this same arm-counting
convention rather than re-deriving a threshold from raw feature-id counts, unless a
concrete counter-example is found during real-data validation (M10 Stage 2 explicitly
flagged this as unverified against DCS ground truth, not merely a style choice).

Separately: `plans/world-model-tactical-landmarks/plan.md` (the M9/M10 scoping plan)
describes a "layers=" selector mechanism it says exists in `build/pipeline.py` for
choosing optional pipeline stages — **this does not exist**. `build_region` instead takes
one explicit optional path parameter per layer (`routes_path`, `probe_output_path`,
`srtm_tile_paths`, ...), each independently None/absent-guarded with its own `*_skipped`
flag on `BuildReport`. Verify this kind of claim against the actual current file before
trusting a parent/prior plan's Affected-Modules section — plans can drift from the code
they describe even within the same session chain.
