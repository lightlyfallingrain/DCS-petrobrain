---
name: bl-b47-air-defence-class-level-security
description: BL-B47 APPROVED; a widening predicate that is only ever OR'd into a speech decision cannot lose a warning, and closing the producer space makes "0 lost" total.
metadata:
  type: project
---

`BL-B47` (`fix/air-defence-class-level`, tip `a8bf3cc`, 2026-10-10) repointed
`belief.speech._is_air_defence` from `object_model.profile_for` to `_summary_op_class` /
`classification.parent_class_of`, so a **class**-level SAM belief (`OP_SRSAM`, …) is recognised.
**APPROVED, no required fixes.** Report: `plans/air-defence-class-level/security.md`.

**Why:** three reusable arguments came out of it, each stronger than the enumeration everyone
focused on.

1. **A predicate that is only ever OR'd into a speech decision cannot lose a warning.** Both call
   sites read `is_air_defence_repeat = not is_new_class and _is_air_defence(facts)` then
   `if is_new_class or is_air_defence_repeat:`. Widening it is monotone in speech, structurally. This
   is a *call-site* property and it settles "could a threat that used to be announced now be
   silent?" outright — no enumeration needed. **Look for this shape first**; it is cheaper and more
   total than a sweep.
2. **Close the producer space and "0 lost over N candidates" becomes total rather than a sample.**
   The reachable belief-classification values are exactly: `profile.op_class` (10 declared),
   `reporting_name_for(object_type)` (595 rows in
   `perception/data/dcs_type_to_reporting_name.tsv`), `DEFAULT_OP_CLASS`
   (`clustering.py:370`), and DCS cockpit-indication free text (`hybrid_source.py:263`). Producers:
   `naked_eye_source._classification_for_tier` (`:1150`). For any value **not** starting `OP_`,
   `_op_class_of` delegates to `profile_for`, so the two resolvers are identical by construction —
   which covers the free-text channel without enumerating it.
3. **The one latent trade, for a future pass.** `classification._op_class_of`
   (`classification.py:73-76`) early-returns any non-default `OP_*` string, so a future `op_class`
   that is air defence by keyword but absent from `AIR_DEFENSE_OP_CLASSES` would *lose* a verdict.
   19 air-defence keyword keys could collide this way. Unreachable today. This is the concrete
   mechanism that turns `BL-B51` (three copies of the class set, only `crew_console`'s has a `<=`
   drift guard) from tidiness into a silent air-defence miss — and the omission already cost
   `OP_LRSAM` months of silence in the other copy.

**How to apply:** when a believed classification is resolved anywhere, check it goes through
`parent_class_of`, not `profile_for` — the latter keyword-matches *type* designations and drops every
class-level belief into the default bucket. `OP_ZU23` resolves correctly through `profile_for` **by
accident** (the literal string matches the table's own `"zu23"` keyword), so any probe that samples
only `OP_ZU23` finds nothing.

**The ratchet decision, and its lapse condition.** `BL-B50`'s repetition hazard: measured through
the real scheduler gate, the fix takes 1 line → 10 in 10 ticks in the one configuration where
`is_air_defence_repeat` is the sole carrier — but the ratchet is reachable **today at the identical
10/10 with no air defence anywhere, pre- and post-fix**, and in steady state the fix adds **zero**
lines. Shipped because blocking buys no exposure reduction and costs a guaranteed silence on a
class-level SAM. **Recompute if (a) a sortie log shows group membership flipping on consecutive
ticks, or (b) `BL-B48`'s `EAGER` 6 km-wide infantry cohesion reaches a flown build** — that is the
ratchet's only missing ingredient. Probe method: [[probe-through-the-real-suppression-path]].
