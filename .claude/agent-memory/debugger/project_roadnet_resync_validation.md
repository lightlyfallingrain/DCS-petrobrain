---
name: project-roadnet-resync-validation
description: roadnet/container.py's resync envelope check missed denormalized-float garbage; fixed 2026-09-04, but the underlying resync technique is not proven exhaustively safe.
metadata:
  type: project
---

`roadnet/container.py::find_next_point_block` (the scan-forward resync technique shared by
`.routes` and `.rn4` parsing) validates candidate point blocks via `_triple_plausible`: finite +
coarse magnitude bounds (`|x|,|z| < 1e6`, `-2000 < y < 6000`). Before 2026-09-04, this missed
denormalized/subnormal float64 values (e.g. `1.36211130863e-312`) — they're finite and near-zero,
so they trivially pass the envelope even though they're never genuine DCS coordinates (they're
what you get reinterpreting non-float trailer bytes as a float64). This let a false-positive
resync match through as real geometry: DCS road feature `id=3711` in the Latakia store, garbage
points + zero padding, causing `describe_position(0,0)` to answer a bogus `nearest_road=0.0m`.

Fixed by rejecting any nonzero coordinate component with magnitude `< 1e-6`
(`_is_denormalized_garbage` in `container.py`). This exact filter was already proven necessary in
the exploratory recon script (`research/2026-09-04-m5-roadnet-byte-decode.md` Session 2) but never
made it into the production validator — worth remembering as a general pattern: **check whether a
recon script's validated filter/threshold actually made it into the production parser it informed,
don't assume it did.**

**Why:** the fix closed the specific denormalized-magnitude failure mode (confirmed zero such
points remain in the rebuilt store), but the full `.routes` whole-file walk still dropped by 28
routes (not just the 1 in the Latakia region) after the fix — meaning ~27 more false-positive
resync matches existed elsewhere in the file under the old validator. This is measured evidence
the resync-false-positive risk (`sync_loss_events`, originally ~2% of matched blocks) is real
beyond this one instance, not proof it's now fully closed — a false match that happened to decode
into small-but-*normal*-magnitude envelope-compliant values would still slip through.

**How to apply:** if a future bug report involves implausible/corrupted `roadnet`-derived geometry
(a road route with an oddly short/long length, weird jumps, or exact-zero padding), check
`_triple_plausible`'s envelope logic first — this is a known-fragile spot, not fully hardened.
Full writeup: `world-model/research/2026-09-04-m5-stage4-validation.md`'s "Correction" section,
`plans/roadnet-resync-false-positive/debug.md`.
