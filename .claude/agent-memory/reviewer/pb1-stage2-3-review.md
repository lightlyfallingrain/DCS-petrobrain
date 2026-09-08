---
name: pb1-stage2-3-review
description: PB-1/body-layer stage 2-3 review outcome and the mypy-cwd-hard-failure variant found in body-layer's cross-subproject seam
metadata:
  type: project
---

`feature/pb1-perception-logger` (commits 08ba9c0/6cd5be6/90e749f, body-layer BL-0 scaffolding +
aircraft-layer world_objects endpoint) reviewed APPROVED WITH MINOR FIXES. All six
implementer-flagged deviations checked out as genuine on independent verification (LOS bypass of
`describe_position`, lat/lon-vs-x/z handling, mypy cwd quirk, true-heading consistency, no-network
world-model seam, fixture provenance) — first review in this project where every single flagged
item survived scrutiny with no walkback needed.

**New variant of the mypy-cwd-config-discovery quirk** ([[worldmodel-mypy-path-requires-cwd]] in
the implementer's memory): world-model's and aircraft-layer's `mypy_path` never reaches outside
their own `src/`, so a repo-root invocation of the documented `mypy <subproject>/src` command
silently degrades to non-strict-but-still-green — misleading but not a hard failure. Body-layer's
`mypy_path` includes `../world-model/src` (the in-process seam), so the *same* repo-root
invocation instead hard-fails with `import-not-found` on `query.describe`/`store.reader`.
Reproduced directly: `mypy body-layer/src` from repo root → 2 errors, `Config File: Default`;
`cd body-layer && mypy src` → clean pass, `Config File: .../body-layer/pyproject.toml`. Flagged as
a **required fix** (not optional) per the existing ruff-cwd-quirk precedent
([[project_ruff_cwd_dependent_isort]]): a failure on the *literal documented canonical command*
is a required fix, not a quirk to wave off, especially since a future session/CI/DoD run following
`body-layer/CLAUDE.md`'s Commands block verbatim will see a false "type errors" result on clean
code. Ruff was proactively immunized against the equivalent cwd-flip via an explicit
`known-first-party` list in `body-layer/pyproject.toml` — worth citing as the model fix pattern
when this recurs in a future cross-subproject-seam subproject.

**Also notable**: fifth-recurrence unstaged-agent-memory issue ([[feedback_agent_memory_path_recurrence]])
did NOT recur this time — all three agents' (architect/implementer/investigator) memory writes
were committed in `90e749f`. Worth confirming stays fixed going forward rather than assuming
solved permanently.
