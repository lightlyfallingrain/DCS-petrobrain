# BL-B14 — Contact report fine tuning

- [ ] **BL-B14 — Contact report fine tuning — a running list, appended to as real sorties surface things.** #status/open
  Opened 2026-09-18 from the first flights with TTS live. These are about what Petrovich *says* and
  how it sounds, not about what he believes; most touch `belief/speech.py` and
  `belief/enrichment.py` only. Grouped by what they cost.

  **Cheap — wording, in `speech.py`. ✅ All shipped 2026-09-19 (`9035317`).**
  - **Spell units out.** "m" and "km" must become "meters" and "kilometers"; TTS does not handle the
    shorthands. Note `_format_range_km` and `_round_enrichment_fragment` both currently emit them.
  - **Acronyms need spacing or expansion.** TTS reads a designation as one token. Wanted: "M I 8".
    **"SAM" is the exception** — a well-known word TTS already says correctly, so this is a
    per-token table, not a blanket rule. *Shipped: the table applies only at `type` level, and
    "SAM" is a `class`-level word, so it is structurally out of reach rather than protected by an
    exception entry. Two of this bullet's original examples were wrong and were corrected during
    implementation: "LR" occurs nowhere in the vocabulary (checked the class table and all reporting
    names) and was left out rather than given an invented use; the real string is "Mi-8", mixed
    case.*
  - **"very close" under 0.5 km.** Replaces a bare range figure at the distance where the exact
    number stops mattering and the fact of proximity starts to.

  **Cheap — thresholds, in `enrichment.py`. ✅ Shipped 2026-09-19 (`9035317`).**
  - **Within 10 m of a feature → "on the road"** (and the same for any feature reference, not just
    roads). *User correction 2026-09-19: originally written as "0 m", which a first pass read
    literally with a float-noise epsilon, leaving a 0.5-10 m gap that rendered as "near a road
    (~4 metres)". Within ten metres you are on it, and no eye resolves the difference.*
  - **Between ~10 m and ~100 m → "next to the road"**, with the side named. *Shipped without the
    side, which needs the bearing below. Note a deliberate gap: 0.5-10 m still renders as
    "near X (Nm)", disclosed in the code rather than silently rounded into one of the neighbours.*
  - These replace the current "near X (~200m)" shape entirely at short distances. The existing
    1000 m `NEAR_FACT_RADIUS_M` gate stays above them.

  **Needs world-model support — the one expensive item. Unblocked 2026-10-05, not done.**
  - **"200 meters north of the road"** and **"next to the road, north side"** both need the
    *direction from the feature to the contact*. `query.describe.RoadInfo` carries `distance_m` and
    `orientation_deg` (the road's own heading) but **no such bearing**, and neither do
    `SettlementInfo` or `WaterInfo`. So this is a `describe_position` change in world-model, not a
    phrasing change in body-layer. Given a bearing *and* the road's existing `orientation_deg`,
    "which side" falls out; without the bearing, neither does. Sequence this before the two wording
    items that depend on it rather than half-building them.
    **`plans/terrain-feature-probing/plan.md` Revision 3, Stage 4 closed the world-model half**:
    `RoadInfo`/`SettlementInfo`/`WaterInfo`/`TerrainLineInfo` all now carry `bearing_deg: float |
    None` (direction from the feature's closest point to the query position, via `store.reader.
    closest_point_on_feature`). This bullet does **not** go to `[x]` — the two wording items above
    are body-layer phrasing and are still unbuilt; only the world-model dependency they were blocked
    on is gone.

  **Deferred (user, 2026-09-19):**
  - [>] **Airborne contacts should be called "aircraft" or "helicopter"**, refining to
    fighter/bomber/attack/transport. Check what actually exists before scoping: whether the
    perception channel can tell a contact is airborne at all (candidate altitude versus terrain
    elevation is available to the naked-eye channel, but nothing currently reads it that way), and
    whether `object_model`'s `OP_*` vocabulary has air classes or needs them. This is plausibly a
    classification change rather than a speech one, which would put it outside this item.
