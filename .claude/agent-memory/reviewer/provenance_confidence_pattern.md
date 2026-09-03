---
name: provenance-confidence-pattern
description: The dataclass+confidence+source shape from coordinates/projections.py is this project's template for any empirically-fitted registration/transform module
metadata:
  type: project
---

`world-model/src/coordinates/projections.py`'s `TmercParams` dataclass (frozen dataclass with
`source: str` prose citation + `confidence: Literal["provisional","confirmed"]`) is the
established pattern for any module that encodes an empirically-derived (not ED-documented)
DCS-internals claim. `world-model/src/raster/registration.py` (M2 Stage 2,
feature/m2-rastercharts-registration) copied this shape correctly: frozen dataclass, `source`
citing exact research-doc session numbers and residuals, `confidence="provisional"` not silently
upgraded.

**Why:** CLAUDE.md's provenance/confidence checklist item is easy to satisfy shallowly (just
adding *a* confidence field) but the actual bar in this project is the `source` string being
specific enough to trace a claim back to the research doc session and control points that
justify it — not just "empirically fit."

**How to apply:** when reviewing a new coordinate/registration/transform module, diff its
dataclass shape and `source`/`confidence` field content directly against
`coordinates/projections.py` rather than checking the checklist item in the abstract. Flag a
`source` string that doesn't name a specific research-doc session/date, or a `confidence` that
looks upgraded beyond what the cited research actually established (e.g. "confirmed" for a fit
with a documented >1% residual).
