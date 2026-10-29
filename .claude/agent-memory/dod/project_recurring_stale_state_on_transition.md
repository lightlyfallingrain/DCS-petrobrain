---
name: recurring_stale_state_on_transition
description: this defect shape -- state that should reset/carry on a transition and doesn't -- has now recurred ten times across four features (BL-14 x4, BL-B64/BL-B80 x3, BL-B89/BL-B98 x2, BL-B67 x1); raise it at Architect time for any "mode/phase with more than one field that should move together" feature, not only at Reviewer/Security; BL-B67's instance is the first where the Co-moving Fields table was already correct and the code just didn't follow it
metadata:
  type: project
---

`BL-14` (the attack run) accumulated four distinct instances of the same defect shape before it
ever reached DoD, each caught by a different reviewer pass rather than by one systematic check:

1. `drain_attack_run` committed `last_spoken_*` state as if a line had been spoken, even when
   channel occupancy suppressed the print (Reviewer, Stage 4-5 pass).
2. `drop target`/the generic cancel path cancelled the standing task but left
   `runner.attack_run_state` non-`None`, so the gaze claim and the "engaged" flag survived past the
   run's own end (same Reviewer pass).
3. A stale `attack_target` task silently remained "the" active one after re-selecting a different
   target with no intervening cancel -- every reader of "the current target" kept resolving to the
   oldest task, not the one the readback had just confirmed (Security deep analysis).
4. `AttackRunState.last_known_target_alt_m` carried the *previous* target's remembered altitude
   into the *new* target's first tier-2 tick after a mid-run re-point, because the field is
   run-level, not keyed to contact identity (Security fix review, found while verifying fix #3).

**Why this is a category, not bad luck**: every one of the four is the same shape --
some piece of state meant to describe "the current X" has a lifetime that does not actually track
X's identity, and nothing enforces that the two must move together. The fourth was found only
because a reviewer called the pure decision function directly instead of trusting the wrapper
(see `feedback_run_the_card_utterances_through_the_matcher.md`-adjacent lesson: call the thing
that actually decides, not the thing that wraps it).

**Process signal, not just a code pattern**: this recurred four times in one feature's review
cycle alone, caught progressively later each time (Reviewer -> Security -> Security-fix-review).
A cheaper earlier check -- at Architect or Implementer time, asking explicitly "which state here
is scoped to the lifetime of a selected/engaged target, and what resets it when that identity
changes?" -- would plausibly have caught #2-#4 as one audit rather than three separate discoveries.
Worth raising at Architect for any future feature with a "selected/active X" concept (next
candidate: `BL-B62`/`BL-B63`, the group-view/fast-lane work, both of which will have their own
notion of "the current target").

**Recommendation approved by the user**Recurred again, `BL-B64` (the 9K113 sight), 2026-10-15 -- now a two-feature pattern, not a
one-feature cluster.** At least two more instances of the same shape, in the same project area
(`belief/optic_policy.py`'s phase/mode state machine), caught by two different later roles:

5. `OpticState` is documented as "frozen and replaced rather than mutated," which reads as if
   every transition carries every field forward -- but two phase-entry branches construct
   `OpticState(...)` fresh rather than via `replace()`, so a newly added persistent field
   (`actual_aim_*`) silently reset to its default on exactly those transitions (caught by the
   Implementer's own test, per its own agent-memory note
   `feedback_decide_fresh_dataclass_construction_drops_fields.md`).
6. A pilot's "Observ off" command set `OpticState.home_phase` to `SCANNING`, but `decide()`'s
   `phase is SIGHTING` dispatch never read `home_phase` -- the two fields were assumed to move
   together once `phase` had already entered `SIGHTING`, and nothing enforced that. Found by
   Reviewer Pass 2 via direct reproduction (building the diverged state by hand), not by reading --
   every existing test happened to keep `phase`/`home_phase` in agreement, so the gap was invisible
   at the unit level.

**The category is now confirmed rather than merely suspected**: two unrelated features, both
built around a phase/mode state machine with more than one field that is supposed to move
together, each produced multiple instances of exactly this shape, and in both cases at least one
instance was caught only by a later role (Security or a Reviewer pass doing direct reproduction)
rather than by the Implementer or an earlier Reviewer pass. **Standing recommendation, now with two
data points behind it**: any Architect plan introducing or extending a phase/mode state machine
with more than one piece of state that must move together should name, as an explicit plan
section, every field that must track every other field's transition, and which construction/
dispatch sites are responsible for keeping them in agreement -- rather than leaving it to be
discovered per-field by whichever role happens to build the diverged state first.

**Recommendation approved by the user (2026-10-15) and now in the Architect role file.** The
user's own words: *"any plan introducing a phase/mode state machine with more than one co-moving
field should name, in the plan, which fields must track which transitions -> good catch, approved,
fix please."* `.claude/agents/architect.md` step 6a (and its Output Format's Co-moving Fields
table) now requires this whenever a plan introduces a phase/mode state machine with two or more
co-moving fields, at least one externally written and at least one internally written; it is also
reflected in `docs/AGENT_ROLES.md`'s Architect section. **If this shape recurs after that step
exists, the gap is the step not firing (Architect skipped it, or the trigger didn't match a real
case), not that the rule is missing** -- check that before writing a fourth memory entry for the
same category.

**Third occurrence, 2026-10-22, `BL-B80` (`plans/9k113-sight-pointing/plan.md`) -- the step fired
and still missed it.** This plan *did* carry a Co-moving Fields table (two state machines,
`OpticState.phase`/`home_phase` and the Export.lua per-frame loop), so Architect's step 6a ran, not
skipped. Reviewer still found a seventh instance of the shape:

7. `GuidanceUnitState.sight_az_raw`/`sight_elev_raw` are set by `refresh_readback` on every numeric
   sample and never cleared back to `None` -- so once any sight readback has ever arrived,
   `perception/naked_eye_source.py`'s gaze-cone builder (which reads `OpticState.actual_aim_*_deg`
   generically, for naked-eye and binocular perception, not only sight perception) keeps anchoring
   to the literal 9K113 head position for the rest of the mission regardless of which optic is
   actually in use -- defeating the plan's own gyro-alignment `BINOCULAR_OPTIC` cap everywhere, not
   only during the window the cap was built for.

**Why the existing table didn't catch it**: the table's own worked examples are fields *internal*
to the phase/mode machine itself (`home_phase`, `observ_observed_since_sim`, the Export.lua
per-frame timers) -- a field that is written by one subsystem but read *generically* by a third,
unrelated consumer (naked-eye perception reading a field the sight subsystem owns) sits one hop
outside what the table's framing asks the writer to enumerate. The category is the same (state that
should reset/gate on a transition and doesn't), but the table as currently scoped prompts for
"fields inside this state machine," not "fields this state machine writes that something *outside*
it reads unconditionally."

**Process signal for next retro**: consider widening step 6a's prompt from "which fields must track
which transitions" to also ask "does anything outside this state machine read one of these fields
unconditionally, and if so, does it need to gate on the same transition?" -- this is the third
feature in this category and the first where the existing mitigation was in place and still didn't
reach the actual instance.

**Fourth and fifth occurrences, 2026-10-25, `BL-B89`/`BL-B98` (`plans/9k113-scan-procedure/`) --
two more instances in one feature, same `optic_policy.py`/`body.py` state machine, caught at two
different roles again:**

8. `_start_glance_away` unconditionally nulled the believed sight aim (`look_azimuth_deg`/
   `look_elevation_deg`) on every entry, for both its call sites -- but both only ever fire while
   OBSERV stays on, so "resume at last position" was only ever true when the aim happened not to
   have been nulled yet. The resume functions (`_back_to_home`, `_enter_binocular_search`) carry
   the aim through unchanged rather than re-deriving it, inheriting whatever the shared nulling
   call left behind. Caught by a pre-existing test that encoded the correct documented behaviour
   and failed against the real code (Stage 1's review), filed as `BL-B98`, fixed by a Debugger
   pass.
9. `body.py`'s `point_request_transition` apply block reset `OpticState.look_started_sim = None`
   for *every* token in a 13-entry superseding-command set, without checking whether a bounded
   look was actually running -- clobbering the field's two other, pre-existing, documented
   consumers (the sight's own per-target look clock, the idle 3-leg search cycle's per-leg clock)
   whenever almost any other command fired mid-look. Caught by Reviewer, via mutation-testing the
   diff's own flagged risk area, not by reading.

**This is now five occurrences across three features** (`BL-14` x4, `BL-B64`/`BL-B80` x3 counting
the widened read above, `BL-B89`/`BL-B98` x2) in the same project area every time --
`belief/optic_policy.py` and the attack-run state machine, both phase/mode machines with co-moving
fields. Instance 9 is exactly the shape the "process signal" above asked to widen the Co-moving
Fields table for ("a field this state machine writes that something outside it reads
unconditionally") -- except here the *reader* set is what grew (a brand-new mechanism, the bounded
look, was added as a third consumer of an already-shared field), not a pre-existing reader that was
missed. **Open question for the next retro, sharper than before**: the Co-moving Fields table
checks "which fields must move together" at the point a plan is written; it does not prompt
"if this plan adds a new consumer to an *existing* shared field, re-audit every other consumer of
that field" -- which is what would have caught #9 before implementation. Both #8 and #9 were still
caught before merge (Stage 1 review, Stage 2 review respectively), so the gate is not failing
qualitatively -- but the category has now recurred enough times in one subsystem that a structural
fix (e.g. a lint/grep rule flagging any `replace()`/assignment to a field with more than one
documented reader, outside that field's own "owning" function) may be cheaper than catching it by
hand a sixth time.

**Tenth occurrence, 2026-10-29, `BL-B67` (`plans/bl-b67-atgm-run/plan.md`) Stage 3 -- the table was
correct this time, the code just didn't follow it.** A variant worth distinguishing from #1-#9:

10. The plan's own Co-moving Fields table already named the right behaviour for "engage missiles,
    ATGM run active, new target" -- re-point `attack_run_state` (existing reset) but keep `atgm`'s
    `phase`/in-flight/`selected_step`, resetting only the range latches and `contact_id`. The
    Stage 1 construction site in `body.py` (the engage-apply block) built a wholesale-fresh
    `AtgmRunState(contact_id=...)` on *every* `engage ... missiles`, including a re-point while a
    run is already active -- contradicting the table it was built from. Caught at Stage 3 review
    (not Stage 1's, where the site was written), verified inert by grepping the whole snapshot for
    `atgm_run.decide` call sites (none in production code yet -- Stage 7 wires it in), and made a
    named, hard precondition on Stage 7's own dispatch rather than a "nice to remember" note.

Unlike #1-#9, this was not a gap in the table itself (Architect's step 6a worked correctly here) --
it was an implementation that didn't match an already-correct table, on a construction site written
one stage before the table's relevant row became live. **This suggests the table's value is being
spent at write-time but not re-checked at the construction site when it is written** -- the
Implementer who wrote Stage 1's `AtgmRunState(contact_id=...)` either didn't check it against the
"new target, run active" row (not yet reachable that stage, so plausibly deferred rather than
missed), or checked it and the gap was still introduced. Either way: **a Co-moving Fields table
should be re-checked against the actual construction/dispatch sites again at the stage that first
makes a table row's transition reachable, not only at the stage that writes the construction site**
-- DoD flags this as the mechanical gap worth raising at Architect/Reviewer for any future plan that
stages a state machine's construction site and its activation in different stages.

**Now ten occurrences across four features.** This has recurred enough, in the same subsystem, that
it is process debt rather than a code-review miss each time -- the DoD role's own instruction asks
to flag this at the role sequence rather than keep absorbing it at Reviewer. Candidate earlier
check: when a plan stages a state machine's construction and its wiring-in separately (as BL-B67
does, Stage 1 builds the site, Stage 7 wires `decide()` in), Architect's step 6a output should
explicitly ask "does every row of this table hold at every stage boundary between now and the stage
that makes it reachable, or does a later stage need to re-verify it" -- making the re-check an
Architect-authored gate on the later stage's own dispatch, rather than relying on whichever Reviewer
happens to read the construction site again.
