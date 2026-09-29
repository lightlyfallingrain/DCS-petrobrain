---
name: group-reporting-stage4
description: Stage 4 wiring (CalloutScheduler + _handle_report) and the sparse-scene cohesion degeneracy it exposed
metadata:
  type: project
---

Implemented `plans/group-reporting/plan.md` Stage 4 on `feature/group-reporting`
(base `6fb99b4`): `CalloutScheduler.tick` and `CrewConsole._handle_report` both now
speak a persisted `belief.groups.Group` via `render_group_disclosure`; `group_candidates`
(the old event-level report-space bucketer) is deleted.

**Mid-task course correction pattern**: the coordinator sent two follow-up messages
*after* the initial dispatch, each overriding a "settled decision" in the dispatch
itself (first: pairs now form real groups, not a residual; second: the "pair" vs
"a couple of" word choice tracks classification specificity, not group size — extend
the existing `differentiated` gate, don't add a parallel branch). Both arrived as
follow-up messages mid-implementation, not at dispatch time. Lesson: don't treat a
dispatch's "Decisions Requiring User Input... Recommended: X" as final — the user may
answer during the run, and the answer can *invert* the dispatch's own recommendation.
Re-check for such messages before finalizing.

**Real, load-bearing discovery, not a bug I introduced**: `belief.groups.
_cluster_contacts`'s relative-gap cohesion has no absolute radius by design (documented,
intentional — "a loose line of vehicles reads as one group in an empty desert"). At
`GROUP_REPORTING_MIN_MEMBERS=2` this becomes reachable with just two contacts: with only
two contacts in the whole store, each is the other's *sole* nearest neighbour, so the
cohesion threshold is always some multiple of their own mutual gap — meaning any two
contacts, however far apart (verified at 500 km), cohere as a group whenever they are
the only two that exist. This is *not* a floor-3 problem (2 contacts never reached that
floor before), so it's newly reachable, not newly broken. Combined with `_handle_report`
speaking the *whole* group from one in-scope trigger member, this can pull a contact
*outside* a requested clock/sector into the report answer. Flagged for the user/architect
in `plans/group-reporting/implementation.md` and `body-layer/ROADMAP.md`; not fixed —
changing the cohesion algorithm or `_handle_report`'s "whole group speaks" design is a
mechanism decision beyond an implementer dispatch's scope.

**Test-fixture trap this causes**: any *existing* body-layer test that puts exactly 2
(or a handful of nearby) contacts in a fresh `ContactStore` with nothing else tracked —
the default shape of almost every fixture in this suite — now incidentally coheres into
a real `Group` under `store.tick()`. If that test's own assertions didn't anticipate
group speech, it silently breaks. Fix pattern used repeatedly here: `store._groups.
_groups = {}` directly after `store.tick(...)`, with a comment explaining why, rather
than fighting the (correct) cohesion algorithm with contrived geometry — geometry tricks
don't actually work here, since *any* 2-contact pair coheres regardless of distance.

**Association-ambiguity gotcha while writing tests**: refining one member of an
already-cohering group via a second `store.ingest(...)` (the normal test pattern for
classification refinement elsewhere in this file) spawns a *new* contact instead of
refining the intended one — `belief.association_over_time.passes_gate` returns `True`
against *every* nearby existing member for a fresh, wide-covariance percept, so the
ambiguous-match safety rule correctly refuses to guess. Confirmed directly, tested up to
800 m spacing, still ambiguous. Workaround: mutate `Contact.classification` directly
between two `store.tick()` calls to drive `ContactStore.tick`'s own before/after
`last_emitted_classification` comparison, bypassing association entirely — legitimate
when the test is isolating event-derivation/speech-wiring behaviour, not classification
fusion itself.
