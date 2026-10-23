---
name: feedback-static-lookup-table-entries-need-per-entry-mutation
description: a hand-maintained static dict (helper signatures, command resets, device ids) is only as trustworthy as the entries a test actually exercises -- mutate an untested entry and watch the suite stay green before trusting "the table is correct"
metadata:
  type: feedback
---

Found reviewing BL-B90 Stage 0b (`body-layer/tools/generate_effector_registry.py`,
`plans/effector-sequences/plan.md`). The generator bakes ED's 22 helper-call signatures into a
static `_HELPER_SIGNATURES` dict (parameter positions for device/command(s)/crew, hand-transcribed
from a recon note) rather than parsing them at runtime. I cross-checked all 22 entries by hand
against the recon and found them all correct -- but only 3 of the 22 were exercised by any test. I
mutated an untested entry (`multiposition_switch`'s `crew_idx`, 10 -> 9) and reran the full
2481-test suite: it stayed green. The mutation was completely invisible, and a real version of this
mistake would have silently misattributed device/cmd/arg/seat fields for every one of that helper's
real-file call sites, without even tripping the generator's own "unhandled" fail-closed path (a
misread crew position frequently still parses as a valid integer).

**Why:** manually re-deriving a static table from a source document and checking it by eye is real
verification, but it is a one-time check against today's table -- it gives no protection against a
future edit to that same table, and nobody re-derives it by hand on every change. A reviewer's own
manual cross-check is not a substitute for the test suite having one.

**How to apply:** whenever a diff introduces or touches a hand-maintained static lookup table that
drives downstream parsing/field-attribution (a signature table, a per-table counter-reset
assumption, an id-to-name map), don't stop at "I checked the entries by hand and they're right" --
pick an entry the test suite does *not* exercise, mutate it, and rerun the suite. If it stays
green, that is itself a required-fix-worthy finding (missing coverage), independent of whether the
current table happens to be correct. The same pass on this generator also found a second, same-
shape gap: no guard against a table/device name being defined twice (confirmed by mutation: a
repeated `count = start_command` / same table name silently restarts the counter at 3001 and
reassigns a duplicate id with zero error, zero "unhandled", and no effect on the three-way
completeness invariant, which only watches `clickabledata.lua`, never `command_defs.lua`/
`devices.lua` internal consistency). Both are instances of the project's own "verify by mutation,
per entry, not per set" standing rule (`.claude/agents/reviewer.md`) -- this is that rule applied to
a static data table specifically, which is easy to mistake for "just data" and skip.
