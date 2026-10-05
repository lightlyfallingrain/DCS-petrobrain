---
name: dcs-driven-los-cone-scoping
description: X-B29 LOS hook cost shape — cone-scoped, bounded, drift risk only in a duplicated guard literal
metadata:
  type: project
---

Reviewed 2026-10-05 (X-B29, `feature/dcs-driven-los`, tip `bcc96fe`). APPROVED — MONITOR, no
required fix.

**The design's own measurement is the load-bearing fact: only ~10 units/poll ever reach the LOS
gate** (measured, flown sortie, plan §8), not the 172–195 in the 10 km bubble — because gate 0
(gaze) rejects 162 of those 172 before LOS is ever asked. Cone scoping removes work that was never
needed, not a budget compromise. Re-derive this before trusting any "whole bubble" cost estimate
on this feature.

**`MAX_SIGHTLINES_PER_CALL = 128` exists as two independent literals** — an outer Lua `local` (cosmetic/
documentation only) and an inner hardcoded `128` inside the `dostring_in` string literal (the one
that actually bounds the loop), with no mechanical guard tying them together. Flagged by Implementer
and Reviewer already. Worst case re-derived independently: 128 × 25 µs/sightline (peak,
buildings+terrain) ≈ 3.2 ms — safely under the 24–26 ms single-call cost that produced the user's
earlier felt stutter (`aircraft-layer/research/2026-10-05-elevation-cost-probe-results.md`). The
duplication is a drift risk (if someone retunes one and not the other), not a cost risk — the inner
literal bounds the call regardless of what the outer one claims.

**New per-frame (60 Hz) work was added to the same Lua Hook family**: a non-blocking look-direction
UDP socket poll (`pollLookDirection`, bounded at 20 datagrams/frame). Reasoned cheap by analogy to
`Export.lua`'s own `try_open_command_socket` (same non-blocking `receivefrom` shape, already shipped
live) — same disposition as [[project_spu8_intercom_cost_shape]]'s per-frame `get_argument_value`
reads. **No profiler exists for DCS-side Lua Hook per-frame cost in this project** — every number
for this file family is either a flown `bridge_call_ms` log line (1 Hz call cost) or reasoning by
precedent, never a frame-time measurement. Worth naming explicitly next time any per-frame Lua
addition is reviewed, since the gap keeps recurring and nothing closes it.

**Checked for the two scaling-shapes that have bitten this project before (BL-B23/BL-B26) and found
neither**: `_resolve_los_by_unit_name` is one `Counter` + one O(n) pass over the bubble, run once per
poll — not O(n²), not keyed on total-ever-seen. `annotate_los` is an O(1) six-field write onto an
already-indexed dataclass entry, called for every bubble candidate regardless of gate outcome, which
costs nothing extra (same dict write either way) rather than being a hidden multiplier.

**The engagement term's live-LOS rewrite is a net cost reduction**, not a new risk: it deletes a
live per-tick call into world-model (`_threat_has_los`, a three-point uncertainty sweep) and replaces
it with a plain attribute read. The pre-existing uncapped-watch-count condition
([[project_watch_reporting_scale_notes]], [[project_divides_between_and_group_tick_multiplicity]])
is untouched — this plan changed what each per-contact check costs, not how many contacts it runs
for.
