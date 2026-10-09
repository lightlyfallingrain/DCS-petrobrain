# WM-W6 — Line-of-sight query primitive

- [x] **Line-of-sight query primitive (no M-number — a cross-subproject refactor, not a
  milestone; done, merged 2026-09-12).** #status/done `query.line_of_sight.line_of_sight_clear(conn, theatre,
  observer, target)` — an ownship-agnostic point-A-to-point-B terrain-masking LOS check, moved
  verbatim (no behavior change) from body-layer's `perception/geometry.py`, which now owns only a
  thin delegating wrapper for its own ownship-to-contact case. Motivation: makes general-purpose
  A↔B visibility queries available to future consumers (Mission Interpreter, a future brain-layer
  tool) without depending on body-layer's own perception pipeline. Uses `tuple[float,float,float]`
  (x, z, alt_m) points, `store.reader.sample_grid` directly (not `describe_position`, to avoid its
  settlement/road join overhead for a bare elevation read — rationale restated in the new module's
  docstring). See `plans/world-model-los-generalization/plan.md`.
