---
name: feedback-bounded-magnitude-isnt-optional-severity
description: A bounded/small-magnitude risk is not automatically "optional" severity — check whether it violates a stated invariant first
metadata:
  type: feedback
---

When classifying a finding as Required vs. Optional, don't let "the worst case is small in
magnitude" downgrade something that violates a module's own explicitly stated invariant (e.g. a
docstring promising "never a silent drop," "always counted," "provenance never collapsed"). Those
are two separate axes: magnitude/urgency (how bad is the worst case) and correctness-against-spec
(does the code do what it claims to do). A small worst-case magnitude can still mean "required fix,
low urgency" — it does not mean "optional."

**Why**: caught this on myself mid-review of `osm-landcover-optimization` — first drafted the
hole/outer-ring post-simplification topology gap as "optional" reasoning from its bounded ~60m
worst case and lack of an observed anomaly in real Stage 6 data. On rereading my own draft before
committing, noticed `build/ingest_osm.py`'s own module docstring states every drop/degenerate
condition is "always a counted skip... never a silent drop," and this exact gap is the one silent
exception to that stated convention — which makes it a required fix regardless of how small the
worst case is. See [[project_osm_landcover_optimization_minor_fixes]] for the full incident.

**How to apply**: when a finding's severity write-up leans on "bounded"/"small"/"no observed
anomaly" as the reason to downgrade to optional, explicitly check first whether the code or its
own docstring/module comments state a convention the finding violates. If yes, it's required
(possibly low-urgency-but-required); the boundedness argument belongs in a "severity note"
explaining why it's not an emergency, not in the required/optional classification itself.
