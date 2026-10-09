# BL-B34 — Stale "5 Hz" docstrings

- [x] **BL-B34 — RESOLVED 2026-10-06, and the interesting half was wrong.** #status/done The three comment-only
  docstrings (`logger.py:1446`, `belief/brain_client.py:12`/`:274`) are stale and go with [[BL-11]]
  Stage 1. **But `perception/motion.py:91`'s "objects arrive at 5 Hz, velocity at 1 Hz" is
  CORRECT** — verified against the installed Lua rather than the plan quoting it: `Export.lua:143`
  `EXPORT_INTERVAL_S = 0.2` gates the `LoGetWorldObjects` send at `:881`, and
  `petrobrain-mission-telemetry-hook.lua:91` `POLL_INTERVAL_S = 1.0` gates the velocity send. Both
  are **producer** rates, and the bound they guard is
  `|world_objects_t_sim − unit_velocity["dcs_model_time_s"]|` — a difference between two *producer*
  sim stamps, which body-layer's own `_DEFAULT_POLL_INTERVAL_S` cannot enter. No threshold depends
  on the consumer rate.

  **Recorded at length because this comment has now been misread twice** — by [[BL-B30]]'s original
  premise and by this entry — each time as a claim about the poll loop. The fix was to add the
  provenance to the comment, not to change behaviour. Kept `[x]` rather than deleted so a third
  reader finds the answer instead of re-deriving it. See `plans/callout-observability-gate/debug.md`.

- [ ] **BL-B34 (original text) — Four stale "5 Hz" docstrings, and one of them is a behavioural
  assumption.** #status/open
  `logger.py:1446`, `belief/brain_client.py:12` and `:274` are comments and cost nothing but the
  misreading they already caused ([[BL-B30]]'s premise, and a wrong budget figure in the
  performance-reviewer's own memory). **`perception/motion.py:91` is different** — it asserts
  *"objects arrive at 5 Hz"* as the basis of `plans/movement-detection/plan.md` Decision 3, so
  movement detection may be reasoning from a sample interval five times shorter than the real one.
  That half is a correctness question for a debugger, not a cost one.
