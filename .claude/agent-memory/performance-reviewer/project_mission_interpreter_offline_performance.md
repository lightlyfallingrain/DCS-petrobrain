---
name: project_mission_interpreter_offline_performance
description: Mission-interpreter whole-subproject performance pass (X-B8) — framing for an offline, no-hot-path subproject, and the one real finding (serialized world-model enrichment calls)
metadata:
  type: project
---

Mission-interpreter (`mission-interpreter/`) runs once, pre-mission, offline — no per-tick/per-poll
path exists anywhere in it. Reviewed 2026-10-16 (`mission-interpreter/research/
2026-10-16-performance-review.md`, X-B8's mission-interpreter slice). Framing worth reusing if this
subproject is reviewed again: the right question is wall-clock the pilot waits through, not a hot-
path budget, and the roadmap itself records that MI-6's output currently reaches **no
pilot-reachable code path** in body-layer (`mission_phase` touches four body-layer files, none of
them `attention.py`/`callouts.py`/`crew_console.py`) — so a perf problem here costs desk time only,
not flight time, until the brain layer wires it in.

**The one real finding**: `world_enrich/enrich.py` calls `WorldModelClient.get_describe_position`/
`get_find_place_by_name` once per route waypoint, per group, per trigger zone, per threat signal —
fully serialized (plain generator/tuple comprehensions, no thread pool, no batching), and
world-model's server (`world-model/src/api/server.py`) exposes no batch route to call into even if
batched client-side calls wanted one. Transport overhead itself is negligible — measured 0.29 ms/
call against a trivial local `http.server` double — the real per-call cost is world-model's own
`describe_position` query, **136.8 ms mean / 497.7 ms p95** against the real syria-full store
(`world-model/research/2026-10-05-performance-review.md` finding 2 — cite, don't re-derive).
Verdict landed **APPROVED — MONITOR**, not NOW: no real mission's enrichable-item count (waypoints
+ named groups + zones + threat signals) is measured anywhere — the Outpost test missions
(`MI24-outpost-M03/M04/M06.miz`) and the Bagram sample are both absent from any checkout (mission
content isn't committed) — and the acceptance card's own 1:12-3:19 wall-clock is dominated by
Ollama model load/inference, which this finding doesn't touch. If picked up later: fan the
independent calls out with a thread pool on mission-interpreter's side rather than adding a batch
endpoint to world-model's server (cheaper, one-subproject change).

Other stages checked and cleared: `.miz` parsing (`miz/reader.py`, measured 2.37 ms against the
committed synthetic fixture — linear, one-time tree copy for `DictKey_*` resolution, not
quadratic); MI-4 synthesis (`synth/synthesize.py`) is one LLM call per mission, not per threat
signal/location — no hidden per-item fan-out; MI-6's compact artifact (`runtime/compact.py`)
deliberately drops heavy `WorldRef` JSON blobs by design and is loaded once at body-layer startup
(`body-layer/src/logger.py:2746`), not per-poll; MI-5's question detector is pure/synchronous, no
I/O beyond pilot-paced stdin.
