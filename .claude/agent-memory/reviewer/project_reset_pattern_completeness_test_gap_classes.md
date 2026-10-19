---
name: reset-pattern-completeness-test-gap-classes
description: "the re-invoke-__init__ reset pattern (BL-15) gives a real completeness guarantee only for classes whose __init__ can be called with no/preservable-only args -- classes needing live collaborators (perception sources) fall back to a hand-written field list with no such guarantee"
metadata:
  type: project
---

Reviewing `plans/bl15-mission-start/plan.md` (BL-15 Stage 1/2): the project's
"re-invoke `__init__`" reset pattern (`reset_for_new_mission()` calls
`self.__init__(...)`, passing only preserved fields, so any new field resets
to the constructor default automatically) gives a genuine, mutation-verified
completeness guarantee for `ContactStore`, `TaskStore`, `MissionMemory`,
`ConsolePerceptionRunner`, `CrewConsole` — their tests enumerate
`dataclasses.fields()`/`vars()` at test time, so a new field is automatically
poisoned-and-checked with no hand-maintained list to fall out of sync. I
mutation-tested this directly (removed the implementer's `init=False` trap
fix for `_last_look_direction`, watched the completeness test fail with the
exact field named) — it is load-bearing, not decorative.

**But `NakedEyePerceptionSource`/`HybridPerceptionSource` cannot use this
pattern** — their constructors need live collaborators
(`world_model_conn`, `theatre`, `aircraft_client`) that can't be
re-synthesized for a throwaway "fresh instance" comparison. Their
`reset_for_new_mission()` clears a hand-picked list of dedup/counter
attributes directly, and their tests assert that same fixed list by name.
**A new dedup/counter field added to either class later has no test that
would catch its omission from the reset.** This is the plan's own
acknowledged tradeoff, not a hidden defect — but it is the one place in this
feature where the stated safety property ("a newly added field resets by
default, no second hand-maintained list") does not actually hold.

**How to apply, next time this pattern recurs**: when reviewing a
reset/completeness mechanism, check whether every class involved can
actually use the "diff against a fresh instance" form, or whether some
class's constructor forces a hand-written field list instead. The two
classes are not just a smaller instance of the same test — they are a
structurally weaker guarantee, worth calling out explicitly in the review
rather than letting "there's a reset test for this class too" read as
equivalent coverage. A cheaper partial fix for the hand-written-list case:
enumerate `dataclasses.fields()` and assert every field name is accounted
for by one of three buckets (preserved/constructor-required,
per-poll-overwritten, explicitly-reset) — catches an unclassified new field
without needing a synthesized fresh instance.

See also [[reinvoke-init-reset-pattern-trap]] (implementer memory) for the
`init=False` + plain-`default` trap this same completeness test caught.
