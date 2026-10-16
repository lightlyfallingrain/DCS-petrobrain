---
name: emitter-visibility-stage-b-firing-channel-cost
description: AC-B8/BL-B73 firing-event channel cost shape — O(events)/O(active-emitters), not O(theatre²); LOS sort-key splice reads the firing-units table once per call, not per comparison
metadata:
  type: project
---

Reviewed 2026-10-16 (`feature/emitter-events` @ `6e61488`, Stage B of the emitter-visibility
feature). APPROVED — MONITOR, no required fix. Full report:
`plans/emitter-visibility/performance-stage-b.md` (Stage A's own pass is a separate file,
`plans/emitter-visibility/performance.md` — don't conflate the two, they review different commits).

**The collector-side `EmitterTracker` (`aircraft-layer/src/collector/firing_receiver.py`) is
O(events-in-batch) for `ingest()` and O(active-emitters) for its prune pass and `snapshot()` —
never O(theatre) and never a cross-product.** Sustained fire from many units does not create a
new cost shape: each additional firing unit adds one dict entry and one prune check, nothing
nests. Even in the still-unconfirmed worst case (`S_EVENT_SHOOTING_START` retriggering mid-burst,
the project's own open DCS question), a retriggering burst costs more *events processed*,
linearly — not a different asymptotic shape. That open question is a correctness question
(watchdog floor), not a performance one; don't let a future review conflate the two.

**Body-layer's `resolve_emitters` (`perception/emitters.py`) does 4 passes over `raw_objects`
where Stage A's `burning_emitters` alone did 2** (`burning_emitters` + `firing_emitters`, each one
`Counter` pass + one result-build pass) — still O(N) once per poll over the same theatre-wide list
every other join in this module already walks (velocity, LOS). Doubling an already-"clean
negative" O(N) pass stays a clean negative; it is not a new cost class.

**The LOS Hook's sort-key splice (`petrobrain-line-of-sight-hook.lua`) reads
`PB_ACTIVE_FIRING_UNITS` exactly once per call, outside the comparator** (`local firingUnits =
PB_ACTIVE_FIRING_UNITS or {}` immediately before `table.sort`), not per-candidate or
per-comparison. The comparator itself adds two O(1) hash lookups per comparison vs. one float
compare before — a constant-factor change to an already-bounded (≤128-candidate,
`MAX_SIGHTLINES_PER_CALL`) sort, dwarfed by the same Hook's own per-candidate raycast cost
([[project_dcs_driven_los_cone_scoping]]'s 25 µs/sightline peak). Worth checking this exact
pattern — "is a joined-in lookup table read once outside the loop, or re-resolved per iteration" —
on any future Lua splice of this shape; it is the one thing that could have turned a cheap
mitigation into an expensive one and it did not here.

**No DCS-side per-event/per-frame Lua profiler exists in this project, and this feature inherits
that gap rather than introducing it** — same standing note as
[[project_dcs_driven_los_cone_scoping]]'s per-frame look-direction poll. `world.addEventHandler`'s
`onEvent` runs for *every* engine event (not just the five kinds this feature filters to), with an
O(1) two-lookup filter (`eventNames[event.id]`, `ALLOWED_KINDS[kind]`) before early-returning on
anything else — reasoned cheap by shape and by the probe's own live precedent, never measured.
Worth naming again next time any per-event or per-frame Lua Hook addition is reviewed, since the
gap keeps recurring and nothing closes it.

See also [[project_bl11_los_gate_cost_collapsed]] (gate 4's own cost, unchanged by this stage) and
[[project_dcs_driven_los_cone_scoping]] (the sibling Lua-cost review this one extends).
