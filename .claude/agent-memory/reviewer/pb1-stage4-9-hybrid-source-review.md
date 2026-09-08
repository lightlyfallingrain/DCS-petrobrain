---
name: pb1-stage4-9-hybrid-source-review
description: PB-1 stages 4-9 (HybridPerceptionSource, association.py) review outcome — APPROVED clean
metadata:
  type: project
---

Reviewed the mid-flight redesign of `plans/pb1-perception-logger/plan.md` (original two-tier
real-feed/proxy split scrapped after a live spike found every numeric-geometry channel dead,
replaced by a single `HybridPerceptionSource`: real HelperAI detection-text gate +
`LoGetWorldObjects`-derived geometry via a new `association.py`). Verdict: APPROVED, zero required
fixes.

What held up under direct verification (not trusted from implementer notes):
- `association.py`'s algorithm matched the plan's "Association design" section step-for-step,
  including the zero/one/ambiguous three-way decision and named tunable constants (no inline
  literals for range cap / forward-hemisphere / tie margin).
- The detection gate is structurally real: traced every early-return path in
  `HybridPerceptionSource.poll()` and confirmed no path constructs an `Observation` before
  `classification` (HelperAI's live text) is confirmed truthy.
- `Observation.bearing_deg`/`range_m` stay non-optional; the zero-candidate path returns `None`
  from `associate()` and `poll()` returns `[]` — no placeholder geometry ever fabricated.
- `petrovich_indication.py`'s recursive-descent parser has zero trace of the LGPL reference impl
  (`asherao/DCS-ExportScripts`) grepped for by name; degrades gracefully (skip, don't raise) on
  malformed input, tested against a "garbage" fixture.
- `GET /petrovich_indication/latest` mirrors `/world_objects/latest`'s cache/server/API shape
  exactly, zero interpretation logic on the aircraft-layer side.
- `Export.lua`'s new `list_indication(6)` push reuses the existing `last_export_t` throttle gate
  (checked once at top of `LuaExportAfterNextFrame`) and existing socket/debug-log pattern — no
  bypass.

One judgment call worth remembering: `TYPE_MATCH_TIE_MARGIN=0` (strict-tie-only counts as
ambiguous) was the implementer's resolution of genuinely ambiguous plan phrasing ("one is
unambiguously top-scored (score margin above a threshold)"). Accepted as reasonable — it's the
conservative reading (favors flagging more scenes as ambiguous/low-confidence over fewer).

One real but non-blocking gap found by close reading, not by trusting docstrings: debounce in
`hybrid_source.py` keys only on classification *text*, not position/ID — two different
same-type detections back-to-back with no intervening empty frame would be silently merged. The
plan's own debounce requirement only covers "clear-then-reappear-with-same-text still re-emits"
(tested), not this case. Filed as optional, not required, since no stable ID exists in the data
to fix it properly, and it's implicitly covered by the plan's own "debounce tuning unspecified"
risk note. Flagged for the stage-7 live acceptance test to actually probe.

See [[feedback_check_agent_memory_staged]] — sixth recurrence of implementer agent-memory files
left unstaged; staged them directly as part of this review rather than blocking on it, since
content was sound.
