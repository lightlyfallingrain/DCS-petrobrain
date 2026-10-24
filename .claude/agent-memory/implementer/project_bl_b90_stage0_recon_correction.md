---
name: bl-b90-stage0-recon-correction
description: Mid-task Stage 0a recon corrected the effector-sequences plan's guessed Lua forms; build the parser to the corrected forms, not the plan's worked example.
metadata:
  type: project
---

On `plans/effector-sequences/plan.md` (BL-B90) Stage 0b, a parallel Stage 0a recon pass against
the live Windows DCS install (build 2.9.30.28738) landed mid-implementation and corrected several
of the plan's own worked examples for `devices.lua`/`command_defs.lua`/`clickabledata.lua`:
devices.lua declares with `devices["NAME"] = counter()` (bracket-string), not the dotted
`devices.NAME = ...` the plan's TOML example implied; `command_defs.lua`'s tables are plain Lua
table constructors, not `tablename.field = value` dotted top-level assignments, except one table
(`device_commands`) built by a `for` loop with string-concatenated keys; and the 13
raw-table-literal elements use `device`/`hint`/`action`/`arg` field names, not the plan's guessed
`cockpit_device_id`/`name`.

**Why this matters beyond this one task:** the plan's own "Risks & Unknowns" section had already
flagged this exact risk ("the generator's parser is the one genuinely new, nontrivial piece of
code this plan adds... easy to get subtly wrong") and scheduled a parallel recon pass for exactly
this reason. The correction arrived as a structured message mid-task rather than before starting,
which meant discarding and rewriting an already-working first draft of the parser rather than
building once. **How to apply:** when a plan names a parallel investigator/recon pass as still
running, do not fully commit to the plan's own worked examples for the thing that recon is
checking -- expect a correction and keep the first draft loosely coupled to specific guessed field
names/forms, OR simply wait for the recon rather than starting on the un-recon'd part first, if
the task ordering allows it. When the correction does land, verify it changes behaviour
(ran the generator against both the pre- and post-correction fixture shapes) rather than assuming
the correction message's claims are already right -- it is itself a secondhand relay, not a
file read.

See also [[feedback_do_not_reinvent_the_wheel]] for the general "don't guess when you can read"
principle this is a specific instance of.
