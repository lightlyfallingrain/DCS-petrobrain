---
name: reuse-relative-direction-channel
description: Before designing any "Petrovich sees it, so aim/guide exactly" truth channel, reuse Percept.relative_direction via attack_run — it already exists, is exact, and is grep-fenced
metadata:
  type: feedback
---

An "exact while he is looking at it" ownship-relative direction already exists:
`Observation.relative_direction` (naked_eye_source, admitted + live LOS clear, truth-to-truth,
`RELATIVE_DIRECTION_SIGMA_DEG = 0.0`) → `Percept.relative_direction` → read under `belief/` only by
`attack_run.py` (fence in `test_attack_run.py`). Position belief never reads it. The pilot's
"two mechanisms" direction (`docs/acceptance/2026-10-14-attack-run-guidance-direction.md`) is its
specification.

**Why:** BL-B80's brief (2026-10-22) framed sight aim at the true target as a needed *new* exception
beside `detection_trace_writer.py`; tracing perception showed the datum and its fence were already
built for BL-14. Adding a consumer via one public function on the fenced reader
(`attack_run.seen_world_direction`, caller `sight_head.py` only) needed no new truth-holding module.

**How to apply:** for any new "aim/guide/track on what he sees" feature, add a consumer through
`attack_run` with its own grep fence and a differential no-leak test (belief/speech/memory/tools
identical with the consumer stubbed off), rather than a new exception. `Percept` carries no optic —
"seen through optic X" must be gated by the runner (e.g. `last_sight_look_sim`). See
[[verify-state-not-the-account-of-it]].
