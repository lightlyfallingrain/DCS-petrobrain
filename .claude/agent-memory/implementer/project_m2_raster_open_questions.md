---
name: project-m2-raster-open-questions
description: M2 RasterCharts registration open items as of Stage 4 (2026-09-03) — level semantics, recurring ruff drift
metadata:
  type: project
---

As of M2 Stage 4 (plans/m2-raster-understanding/), two open items worth knowing before
touching `world-model/src/raster/` or its research doc again:

- **RasterCharts' `level` filename suffix (`-2`/`-1`/`00`/`01`) semantics are still
  unresolved for the `.tif.dds` (RasterCharts) container specifically.** All locally
  sampled RasterCharts tiles are `level="00"` only — no other level was ever pulled. A
  *different* container (`clipmaps/*.tif.clipmap`, session 9 in the recon doc) has a
  confirmed `level*32` header encoding with `-1`=coarse fallback / `00`=full detail, but
  that finding does NOT transfer to RasterCharts — the two are different custom containers
  sharing only a naming convention, per session 6's finding. Closing this needs a live-WSL
  probe pulling a non-`00` RasterCharts tile. Do not assume the clipmap semantics apply to
  RasterCharts without verifying.
  **Why:** avoiding exactly this kind of unverified-DCS-internals leap is a hard project
  rule (root CLAUDE.md, docs/CONVENTIONS.md).
  **How to apply:** if `registration.py`'s `default_level` ever needs to change from `"00"`,
  get a WSL probe first — don't reason by analogy from the clipmap finding.

- **A `ruff check` import-sort (I001) finding in `world-model/tests/test_coordinates.py` has
  now recurred 3 times across M2 Stages 2, 3, and 4**, each time "fixed" in the feature
  branch but reappearing by the next session. Root cause not found — plausibly a ruff
  version/config drift between environments, or something in the branch/merge workflow
  silently reintroducing it. Worth actually investigating (e.g. `ruff --version` diff
  across machines, check `pyproject.toml` ruff config for anything nondeterministic) before
  M2 Stage 5 close-out rather than re-fixing it a 4th time.
  **Why:** repeatedly re-fixing the same finding without diagnosing it means it'll keep
  costing a small chunk of every future session's checks.
  **How to apply:** if you hit this finding again, check `ruff --version` and diff
  `pyproject.toml`'s `[tool.ruff]` section against what the fix actually changes before
  just re-applying `--fix` again.

See [[verify_full_suite_not_just_new_files]] for the general pattern this recurrence is an
instance of.
