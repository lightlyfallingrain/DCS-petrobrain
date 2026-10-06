---
name: cli-path-mkdir-degrade-policy-misses-valueerror
description: BL-11 Stage 5's first caller-controlled mkdir — the degrade guard catches OSError but pathlib raises ValueError, and `~` is never expanded; probe recipe included
metadata:
  type: project
---

`BL-11` Stage 5 (`feature/bl11-tick-cost`, 2026-10-06) is the first place a body-layer **CLI
argument creates directories**: `logger._per_run_log_paths` resolves `--detection-trace` /
`--belief-truth-log` / `--speech-log` and calls `parent.mkdir(parents=True, exist_ok=True)`.
Reviewed APPROVED; three low findings, all on the same five lines.

**The reusable lesson is the exception-type mismatch, and it will recur anywhere a
"degrade instead of crash" policy wraps `pathlib`:**

- `Path.with_name()` raises **`ValueError`**, not `OSError`, when the final component is empty
  (`.`, `/`, `""`). A `try: … except OSError` degrade guard does not catch it, so the stage's own
  stated guarantee ("an unwritable log should cost the sortie its trace, not its crew") is
  escapable by a one-character typo. Compounded by the stamping call sitting *outside* the `try`.
- `pathlib.Path` **never expands `~`**, and there is no `expanduser` anywhere in `body-layer/src`.
  Before a `mkdir` that was a write failure; with one it silently creates a directory literally
  named `~` in the CWD. Latent only because this branch removed the repo's last two `~` call sites
  from `run-scripts/`.
- `mkdir(exist_ok=True)` **does** degrade correctly when the parent is an existing *file*
  (`FileExistsError` is an `OSError`), and cannot overwrite or delete anything. Unbounded
  `parents=True` on argv is **not** a traversal finding — argv is the operator's own intent. Rate
  the blast radius (N empty directories, no overwrite, no delete) rather than inflating it.

**Probe recipe, 20 lines, worth rerunning on any future path-handling change** — import the path
helper, loop it over `['logs/x.jsonl', '~/x.jsonl', '/abs/x.jsonl', '../../x.jsonl', 'logs/', '.',
'/', '']` printing result-or-exception, then `chdir` into a `TemporaryDirectory` subdir and
replicate the production `mkdir` lines against: a `~` path, a parent that is a file, a symlinked
parent, a deep typo, and `../escaped/`. Reading the code gives you three of these; the probe gives
you all eight and the exact errno text to quote.

See also [[project_body_layer_bounded_growth_accepted_pattern]] for the house style on rating
local single-user risk honestly.
