---
name: project-watch-reporting-scale-notes
description: body-layer scale facts discovered reviewing watch-reporting -- watch count is unbounded via AttentionArea, harness technique for testing another worktree's branch code
metadata:
  type: project
---

From the `feature/watch-reporting` performance review (2026-09-24):

- **Watched-contact count is not capped anywhere in code.** Besides a player's direct
  `watch`/`priority` mark, `belief.attention.AttentionArea` + `effective_attention`
  (`body-layer/src/belief/attention.py`) grants watch-equivalent attention to every contact inside
  a live area (a "watch left" voice command), which can cover an arbitrary number of contacts. Any
  future per-watched-contact hot-path cost (LOS, or anything else added to `ContactStore.tick`'s
  watched-contact blocks) should be checked against this amplifier, not just against "the player
  manually watches N contacts."
- **`Observation.position_uncertainty` is populated by the perceiving channel's own error model**
  (`perception.source.PositionUncertainty`) for real detections -- a synthetic test contact built
  without it (as most existing `_observation()` test helpers do, `position_uncertainty=None`) has
  `Contact.last_position_uncertainty_m == 0`, which silently takes the cheap 1-sample path through
  `contacts._threat_has_los`'s uncertainty sweep instead of the real 3-sample path. Any timing/test
  work against LOS-adjacent code should set `position_uncertainty` explicitly to get worst-case
  behaviour, or it will look 3x cheaper than production.
- **Harness technique for reviewing a branch from a `main`-based worktree:** this worktree's git
  operations must stay inside the worktree (bare `cd` + `git` to the shared checkout is refused by
  a hook), and the worktree's own working tree is `main`'s content, not the feature branch's. To
  actually *run* the feature branch's code (not just read it), `git archive <branch> -- <subdir> |
  tar -x -C <scratch-dir>` extracts a real file tree into the scratchpad, which can then be
  `PYTHONPATH`'d directly -- confirmed working for `body-layer` against `body-layer/.venv/bin/python`
  (absolute path to the venv in the *original* checkout is fine to invoke; only `cd`-into-shared-
  checkout + git is blocked, not using its already-built venv as an interpreter).
