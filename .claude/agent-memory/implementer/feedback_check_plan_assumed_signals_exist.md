---
name: check-plan-assumed-signals-exist
description: A plan's diagram/prose can assert a signal "already exists, already warm" that a code read shows was never built -- verify, don't inherit the claim
metadata:
  type: feedback
---

On the BL-16 LV-1 amendment (`plans/flight-lift-vector/plan.md`), the Architect's own diagram said
the take rule reads "the estimator's own averaged bank phi_bar ... already warm every mode" as a
reused, not-new signal. Reading `flight_control.lua`'s actual estimator (`fc_est`, `est_sample`)
showed no such running average existed — `measured.bank_deg` was always the raw, single-frame
`LoGetADIPitchBankYaw` read. The plan's own "Tuning constants" section had half-acknowledged this
("the bank-averaging window... reuse w_v_s") without the main diagram text ever saying the base
signal itself was new.

**Lesson**: when a plan's diagram or prose states a signal/mechanism "already exists" as the
premise for a design, grep for it before building on top of that premise. It cost nothing here
(the fix was adding one ring + one derived field, same pattern as every other estimator channel),
but building the take-rule logic against a signal that silently didn't exist would have been a
runtime nil-arithmetic crash in Lua, not a type error caught before running.

Separately, on the same amendment: the plan asked for a new Lua-only profile constant
(`bank_hold_threshold_deg`) for a threshold that turned out to already exist, wire-tunable, under
a different name (`fc_limits.takeover_level_bank_deg` / body-layer's `TAKEOVER_LEVEL_BANK_DEG`),
with a docstring stating exactly the same rule. A plan's "first cut, new constant" is itself an
unverified claim about what the codebase lacks — grep for the semantic before minting a duplicate,
same as the "do not reinvent the wheel" rule asks generally, but specifically worth doing even when
the plan itself proposes the new thing.

See: `plans/flight-lift-vector/implementation.md`, "LV-1 amendment" section, "Not built as
written, and why".
