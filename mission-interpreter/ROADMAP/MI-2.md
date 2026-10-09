# MI-2 — World enrichment

- [x] **MI-2 — World enrichment.** #status/done Done (`plans/mi2-world-enrichment/plan.md`): world-model's
  `src/api/server.py` (`WorldModelAPIServer`, three read-only `GET` routes wrapping
  `describe_position`/`find_place_by_name`/`line_of_sight_clear`, theatre-mismatch validated as a
  `400` to prevent silently-wrong-projection results) is this project's first HTTP seam, called by
  `mission-interpreter/src/world_enrich/world_model_client.py` (`WorldModelClient`, raises on every
  failure -- no "not built yet" expected-empty state). `src/world_enrich/enrich.py`'s
  `enrich_mission` walks a `CrewAvailableMission` (route waypoints, one representative position per
  group, every trigger zone) into a parallel `EnrichedMission` tree (`schema.py`), mirroring
  `belief.enrichment`'s "zero shared surface" precedent rather than mutating MI-1/MI-1.5's frozen
  dataclasses. Per-unit enrichment and free-text briefing-prose place extraction are explicitly out
  of scope this stage (deferred to MI-4). Does not change what MI-3 should be -- MI-3 still needs a
  first Mission Understanding schema, now with `EnrichedMission` as an available input alongside
  `CrewAvailableMission`.
