---
name: project_configurable_constants_crosskey_assert_gap
description: X-T26 configurable-constants review — a module-level assert coupling two independently-tunable constants survived per-key bounds validation and crashed the process; verified by direct mutation, not reading. Recurred on 9k113-narrow-search/BL-B85, this time via copying the assert without the coupling-check that makes it safe.
metadata:
  type: project
---

X-T26 (`plans/configurable-constants/plan.md`, Stages 1-2) made ~15 body-layer constants
independently tunable via a `tuning.py` loader whose whole premise (Decision 4 REVISED / 4a) is
"a bad value warns and continues on the code default; nothing refuses to start." The implementer
found and documented, rather than fixed, that `belief/decay.py` has a **module-level
`assert OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S`** — and `POSITION_HALF_LIFE_S`, `FOCUS_DWELL_S`,
and `SCAN_PLAN` (which together determine `OBSERVED_WINDOW_S`) are all three in the curated
tunable set. Per-key `lo`/`hi` bounds cannot see this: each of `FOCUS_DWELL_S=5.0` and
`POSITION_HALF_LIFE_S=20.0` is individually inside its own declared range, but combined they trip
the assert and crash the process at import — a disguised "refuse to start" in a feature whose
entire point was never to do that.

**Verified by direct execution, not by reading the plan's description of it**: wrote a two-key
TOML override, set `PETROBRAIN_TUNING`, and reproduced the `AssertionError` live. This is the
pattern [[feedback_every_guard_entry_needs_a_failing_counterfactual]] and
[[feedback_mutate_the_assertion_not_just_the_accessor]] both point at — a set-level/per-key
guard that looks complete on a skim of bounds declarations hides a cross-entry interaction a
single mutation reveals in seconds.

**Why: a per-key validator is not the same shape of safety net as a cross-key invariant.** Any
future "make constant X configurable" pass in this project should grep for module-level `assert`
statements that reference *derived* values built from more than one tunable constant
(`belief/decay.py`'s own comment already names the derivation chain:
`OBSERVED_WINDOW_S = perception.gaze.SCAN_CYCLE_PERIOD_S = len(SCAN_PLAN) * FOCUS_DWELL_S`) before
assuming per-key bounds are sufficient.

**How to apply**: whenever a plan or review involves multiple constants that feed one shared
downstream invariant (an assert, a derived ratio, a structural precondition), do not trust
"each key has its own declared bounds" as proof the combination is safe — combine two in-bounds
values and run it. Flag any hard `assert`/raise reachable from a tunable-constant's own module as a
required fix if the project's stated policy for that feature is "never refuse to start," regardless
of whether the implementer already wrote it up as a known gap.

**Recurred, 2026-10-20, `9k113-narrow-search`/`BL-B85` (`body-layer/CLAUDE.md`'s "Tuning" section is
the user-facing writeup).** A prior review round of mine *suggested* "an import-time assertion (the
same pattern `belief/decay.py` uses)" as an optional fix for a new coupling
(`OPTIC_RETRY_INTERVAL_S < SIGHT_STALL_COOLDOWN_S`) — without checking that `decay.py`'s own bare
assert is only safe because `tuning.py`'s `_check_scan_decay_coupling` pre-validates and falls back
*before* it runs, and that `_check_scan_decay_coupling`'s `_COUPLED_KEYS` is hardwired to exactly the
three original keys (its own docstring: *"Not a general mechanism... nothing generalises this to a
second coupling without writing a second named check"*). The implementer took the suggestion at face
value and added only the bare assert. Result: `SIGHT_STALL_COOLDOWN_S=40.0` alone (one key, inside
its own declared `lo=30.0, hi=400.0`, every other key at its code default) reproduces the exact same
import-time crash the original X-T26 finding did — reproduced directly again, not inferred.

**The sharper lesson this time**: *suggesting* "do what `decay.py` does" is not itself safe advice
unless the suggestion names the actual protecting mechanism (`_check_scan_decay_coupling`), not just
the visible assert line next to it — a bare assert that happens to read the same way as a protected
one is not evidence of protection. When recommending or reviewing a "mirror an existing precedent"
fix for a cross-key invariant, check what *actually* makes the precedent safe before treating it as a
template, and verify the new instance the same way (construct the override, run the import,
don't just confirm the assert text matches).
