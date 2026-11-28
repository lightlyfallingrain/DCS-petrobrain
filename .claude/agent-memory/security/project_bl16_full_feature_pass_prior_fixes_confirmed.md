---
name: project_bl16_full_feature_pass_prior_fixes_confirmed
description: BL-16 whole-feature security deep analysis (all stages, feature/bl16-lift-vector-law @ cf03d63e) -- APPROVED, no new findings; confirms the two M3 terrain-relay findings and the flight_authority NaN/int crash from earlier per-stage passes are fixed in the merged tree, and that the 2026-11-28 "LAN false command is not a finding" rule retires nothing by name from this feature's prior reports
metadata:
  type: project
---

User asked for one security pass over the whole of BL-16 (not just the latest small change) after
~249 commits across P-ICS/P0/P1, mode-1 M1/M2, flight-desired-state Stage 2/3, lift-vector
LV-0..LV-3, M3 (terrain floor), M4 (SAU). Doing a whole-feature pass after each stage already had
its own is useful for exactly one thing here: **re-verifying that findings deferred across stages
actually landed**, not finding new cross-stage interactions — this codebase's per-endpoint
defense-in-depth posture (closed vocabularies, `isfinite`+range on every numeric field, fixed-arity
`%d`-only Lua splice templates) is applied so consistently that a new stage rarely opens a
genuinely new category of risk; it mostly reuses the same seam (the `flight_lease`/command-sender/
effector-engine triad) its predecessor stage already hardened.

**What this pass actually earned its keep on**: two "owed before BL-16 DoD" items named directly
in `body-layer/ROADMAP/BL-16.md` (terrain relay `x`/`z` magnitude bound, 32-point cap) and one
already-fixed-in-batch item recorded in `[[project_bl16_flight_authority_nan_int_crash]]` all
needed a **live read of the current code**, not a trust of the roadmap's own "owed"/"fixed" prose
— all three were confirmed actually fixed (`_terrain_relay_passes_bounds` in
`aircraft-layer/src/api/server.py`, `_as_optional_float`/`_as_optional_degrees_0_360` in
`body-layer/src/belief/flight_authority.py`), consistent with this project's own standing
"verify state, not the account of it" rule.

**The 2026-11-28 threat-model rule** ("a LAN peer sending a false but well-formed command is not a
finding, only OWASP-style issues are") retired nothing by name from this feature's nine prior
`security-*.md` reports — every one of their findings was already an OWASP-style issue (unbounded
input, a missing bound, a non-finite-at-boundary crash), never the "false command accepted" shape
the new rule excludes. Worth checking this explicitly rather than assuming a scope narrowing
always retires something — sometimes the existing record was already scoped correctly and the new
rule only makes that scoping explicit.

**How to apply next time**: for a "whole feature" security pass after N per-stage passes already
ran, spend the budget on (1) reading every prior report's filed/non-blocking findings and
confirming each is actually fixed in the current tip (grep the exact guard/check named in the
report, don't trust the roadmap's "fixed" claim alone), (2) one grep sweep for the eval/exec/
subprocess/secrets categories across the whole diff, (3) tracing whether any stage reintroduced a
channel an earlier stage retired (here: no raw-axis `LoSetCommand` write path leaked back into
`src/api`/`src/schema`/body-layer), rather than re-deriving each stage's own analysis from
scratch.
