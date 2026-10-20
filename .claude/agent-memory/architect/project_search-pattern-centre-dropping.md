---
name: search-pattern-centre-dropping
description: logger._search_sweep/belief.optic_policy.search_pattern never applied a commanded sector's own centre -- pre-existing defect found while designing the 9k113-narrow-search split, not fixed for the existing caller
type: project
---

`body-layer/src/belief/optic_policy.py`'s `search_pattern` had no centre parameter before
`plans/9k113-narrow-search/plan.md`'s 2026-10-20 amendment, and its caller
`logger._search_sweep` discards the commanded sector's own centre it unpacks from
`SECTOR_WEDGE_DEG` (`_, half_width_deg = SECTOR_WEDGE_DEG[...]`). Every generated azimuth was
symmetric about 0.0 regardless of which sector (`ahead`/`left`/`right`/`full`) was commanded.

**Why:** this was harmless by accident under code that only ever called `_search_sweep` for the
*whole* sector and never had reason to compare the result against the sector's own centre. It
stopped being harmless the moment a caller needed a sub-span with a genuinely non-zero centre
(the 9k113-narrow-search split: ±60°-straddling sectors split into in-regard/out-of-regard
sub-spans at −75°/−45°/45°/75°). Found by tracing the geometry needed for that split, not by a
bug report — today's shipped OBSERV-off binocular search for `left`/`right`/`full` sectors
actually sweeps around 0° (dead ahead) instead of around that sector's own centre.

**How to apply:** `search_pattern` now takes an optional `center_azimuth_deg: float = 0.0`
(default is a true no-op for `_search_sweep`'s own existing, unchanged caller). The fix is applied
only at the *new* call sites the 9k113-narrow-search plan adds (`_sight_in_regard_sweep`/
`_sight_out_of_regard_sweep`); `logger._search_sweep`'s own `SCANNING`-at-home caller is
deliberately left broken, out of that plan's scope, with a Risks-section recommendation to file it
as its own backlog item. If you touch OBSERV-off binocular search for a non-`ahead` sector, check
whether that item exists and whether this is now the right place to fix it.
