---
name: bl-b110-coupling-extension-safe
description: BL-B110 Stage 1 extended tuning.py's cross-key coupling check from 3 keys/1 invariant to 5 keys/2 invariants (I2, WORST_REVISIT_S vs LOST_THRESHOLD_S/GROUP_REIDENTIFY_WINDOW_S); traced real()/sequence() call sites directly and confirmed every new coupled key still routes through the same reject-to-default path, no bypass.
metadata:
  type: project
---

`plans/expected-area-check/plan.md` (BL-B110) Stage 1 extended `body-layer/src/tuning.py`'s
`_check_scan_decay_coupling`/`_COUPLED_KEYS` from the original 3 keys/1 invariant (I1,
`project_configurable_constants_crosskey_assert_gap.md`'s fix) to 5 keys/2 invariants: I2 checks
`WORST_REVISIT_S` (`OBSERVED_WINDOW_S + GLASS_BUDGET_PER_CYCLE_S + n_sectors(SCAN_PLAN)`) against
both `LOST_THRESHOLD_S` and `GROUP_REIDENTIFY_WINDOW_S` (`2 * POSITION_HALF_LIFE_S`).

**Why this needed a real trace, not a skim**: this is exactly the hazard class
[[project_configurable_constants_crosskey_assert_gap]] and
[[project_bearing_line_search_divisor_floor]] both describe — a module-level `assert` coupling
independently-tunable constants, invisible to per-key `lo`/`hi` bounds. Confirmed by reading
control flow, not docstrings: `real()`/`sequence()` call `_check_scan_decay_coupling` for every
member of `_COUPLED_KEYS` before binding (tuning.py ~460/532); on violation every file-mentioned
coupled key is marked `cross_key_rejected`, and `real()`'s own rejection branch forces that key
back to its code default — the new `decay.py` `assert WORST_REVISIT_S < min(LOST_THRESHOLD_S,
GROUP_REIDENTIFY_WINDOW_S)` is only a backstop for a *code-default* violation (genuine programming
error), never reachable from a bad override file. No bypass found.

**How to apply**: whenever this coupling check is extended again (a Stage 2/3 of this same
feature, or an unrelated future tunable), re-trace the same three things rather than trusting the
docstring: (1) is the new key actually added to `_COUPLED_KEYS`, (2) does every accessor that key
goes through actually call the coupling check before binding, (3) does the rejection path actually
fall back to the code default rather than keeping the bad value. This is a cheap, mechanical check
and is exactly what the prior incident's own retro says a skim misses.
