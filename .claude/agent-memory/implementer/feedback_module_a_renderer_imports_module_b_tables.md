---
name: renderer-and-constant-table-split-avoids-circular-import
description: when a plan assigns word-table constants to module A and the renderer that reads them to module B, pass the tables into the renderer as arguments rather than having B import A's constants -- otherwise A importing B's renderer plus B importing A's tables is circular
metadata:
  type: feedback
---

`plans/attack-run/plan.md`'s Affected Modules section assigned the
`render_alignment_*` renderer family to `belief/speech.py` and the constants/
word tables (`ATTACK_RUN_LINED_UP_AZIMUTH_DEG` etc., Decision 11 REVISED:
"declared in attack_run.py... one place") to the new `belief/attack_run.py`.
Taken literally, this is circular: `attack_run.py` needs to call
`speech.render_alignment` to get text, and `speech.py` would need to import
`attack_run.py`'s tables to build that text -- `attack_run -> speech ->
attack_run`.

**Resolution used:** `speech.render_alignment(azimuth_deg, elevation_deg, *,
tier, azimuth_table, elevation_table)` takes the word tables as plain data
arguments. `attack_run.py` declares the tables once (satisfying the "one
place" rule) and passes them in at each call site. `speech.py` ends up with
zero import dependency on `attack_run.py`; `attack_run.py` has exactly one
dependency on `speech.py` (the renderer function + the speech-line type).

**How to apply:** whenever a plan's Affected Modules list splits "the data"
and "the code that renders the data" across two modules and both directions
of use are implied (the data owner calls the renderer; the renderer needs the
data), check for this shape before writing either module. The data owner
should pass its tables/constants into the renderer's call as arguments, not
rely on the renderer module importing them -- this keeps the dependency
one-directional (data owner depends on renderer, never the reverse) and scales
to a future second data owner (e.g. a tier-2 renderer) without revisiting the
decision.
