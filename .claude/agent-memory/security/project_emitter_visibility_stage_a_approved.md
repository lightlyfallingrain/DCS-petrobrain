---
name: emitter-visibility-stage-a-approved
description: Security deep-analysis verdict and verification method for BL-B72/AC-B7 Stage A (burning-unit emitter visibility) — APPROVED, and the closed-mapping pattern worth reusing on BL-B73/BL-B74
metadata:
  type: project
---

`plans/emitter-visibility/security.md`, reviewed at tip `1053265e9bec7411fc1a423d8142b9d64546c17c`.
**APPROVED**, two non-blocking recommendations only.

**Why this one is worth remembering beyond the verdict**: it is the first feature to deliberately
bypass gates the no-omniscience invariant previously treated as absolute (range/size, forest), and
the plan's review already caught one real boundary violation before this pass (the first
implementation let `Observation.provenance` cross into `Percept` wholesale and weakened the
truth-boundary guard test to match). By the time Security saw it, the fix-pass had already closed
it via `Percept.emitter_kind` populated through a `dict.get`-only mapping
(`_EMITTER_KIND_BY_PROVENANCE`) with no override path for an unregistered value.

**Verification method that actually caught/confirmed things, worth repeating on `BL-B73`/`BL-B74`
(gun fire, SAM launch)**:
- Don't trust "gate N is untouched" from a diff summary — read the actual span of
  `check_visibility` between the two bypassed gates directly. Gate 4 (terrain LOS) sits physically
  between gates 3 and 5 in the function body; confirming it has zero `emitter` references by eye
  is cheap and is the real check, not the plan's claim about it.
- Re-run the reviewer's own mutation yourself rather than accepting a pasted red/green — did this
  for the `Percept.provenance` re-addition; it reproduced exactly.
- Check `_OBSERVABILITY_EXEMPT_KINDS`/`_WATCHED_ONLY_KINDS` (`belief/callouts.py`) by reading the
  frozenset literals directly whenever a new `EventKind` is added — this project's own retro
  recorded a prior miss where a set keyed on `EventKind` silently covered a transition it was never
  written for. `CONTACT_BURNING_SEEN` is in neither set; checked directly, not from the adjacent
  comment claiming it.
- Trace a derived-from-ground-truth signal (`getLife()`/`getLife0()`) hop by hop to confirm the raw
  value never crosses past the predicate that collapses it to a bounded, perceivable signal — grep
  for the raw field names (`life`/`life0`) outside the two files permitted to hold them.

**The one open structural gap, carried forward rather than fixed**: nothing *mechanical* stops a
future `Observation.provenance` producer from being folded into `Percept` wholesale again, beyond
the restored `test_percept_has_no_truth_carrying_field` entry itself. That test is a real, live
guard (confirmed by mutation) — but it is the only thing standing between "closed signal" and "the
boundary moves again", and it moved once already in this feature's own lifetime. Worth checking
again at `BL-B73`/`BL-B74`'s plan-review pass: do they follow the `_EMITTER_KIND_BY_PROVENANCE`
closed-mapping shape by default, or does a new producer try the wholesale-passthrough shortcut
again now that two emitter kinds exist to copy from.

See also [[emitter-visibility-seams]] (architect's memory, the structural seams this plan landed
on) for the design-time context this verification built on.
