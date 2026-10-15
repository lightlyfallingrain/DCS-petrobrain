---
name: emitter-visibility-seams
description: the seams a detection-only perception override lands on in body-layer, and the two that look available but are not (threat band, LOS sightline cap)
metadata:
  type: project
---

From the `BL-B72` Architect pass, 2026-10-15 (`plans/emitter-visibility/plan.md`). These are
structural facts about body-layer's perception/belief seams that cost real reading to establish and
are not obvious from any one file.

**Seams that already exist and should be reused, not rebuilt:**

- **`Observation.provenance: str` is free-form** and today only ever carries
  `PROVENANCE_VISIBILITY_FILTER_ONLY`. Any new admission path can mark itself there with **no schema
  change** to `Observation`, `Percept` or `Contact`. Same for `Observation.source`, deliberately not
  closed to a `Literal` (`perception/source.py`'s own docstring explains why).
- **"Detection only" needs no new classification path.**
  `naked_eye_source._classification_for_tier("lowres", …)` already returns
  `object_model.DEFAULT_OP_CLASS` at level 1. Forcing `VisibilityResult.tier = "lowres"` is the
  whole of a presence-only admission.
- **The per-candidate-modifier pattern is established three times over** — `gaze`, `group_salient`,
  `live_los_clear` are each resolved by the *caller* (`naked_eye_source.poll`) and handed to
  `check_visibility` per candidate, keeping joins and set lookups out of the gate function. A fourth
  modifier follows the same shape and needs no new design.
- **Clustering answers cardinality for free at long range.** It is angular and position-only, so
  several units admitted at 9 km collapse into one cluster with a `count_bucket`. No group machinery
  needs changing. The thing to *protect* with a test: `group_salient_ids` runs over the whole bubble
  pool **before** visibility, so an admission override inside `check_visibility` structurally cannot
  widen detection for a candidate's non-emitting neighbours — pin it so a refactor cannot undo it.

**Two seams that look available and are not:**

- **`belief/threat.py`'s `envelope_for()` keys on `ClassificationBelief`.** A `PRESENCE`-only
  contact matches no envelope and lands in `callouts.py`'s `_DEFAULT_THREAT_BAND = 0` — the
  *lowest* priority. So any feature whose whole point is "this thing is urgent but unidentified"
  **cannot** route through the existing threat path; it needs its own `EventKind` with a priority
  set independently of classification. This inverts the obvious design and is easy to miss, because
  nothing in the threat module says "classification is the only input".
- **`petrobrain-line-of-sight-hook.lua` caps at `MAX_SIGHTLINES_PER_CALL = 128`, sorted
  nearest-first**, inside a 10 km bubble and a 180°-wide look wedge
  (`logger.LOOK_DIRECTION_FOV_HALF_DEG = 90`). Truncation therefore drops the **far** candidates,
  and `check_visibility`'s gate 4 is fail-closed on `live_los_clear is None`. **Any feature that
  admits distant candidates is silently capped by this**, and the failure presents as "the feature
  doesn't work" rather than as a cap. The wedge itself is never the problem — it is far wider than
  the 15° gaze focus cone.

**Where event-shaped state belongs.** body-layer perception is deliberately recomputed-per-poll and
stateless (`Gaze` is a frozen value recomputed every tick and never stored — `perception/gaze.py`'s
"Gaze needs no state at all"). So an accumulating state machine over DCS events belongs in the
**aircraft-layer collector**, which already owns per-feed caches and an event queue
(`f10_command_receiver`), and should publish a *polled snapshot*. That keeps replay deterministic
and keeps every perception input the same shape.
