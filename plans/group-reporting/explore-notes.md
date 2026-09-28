# Explore: what makes units "one group" — user conversation, 2026-09-28

Held after the 2026-09-28 sortie, whose log showed 52 contacts of which 3 were ever plural, and
~5 contact reports per minute for 25 minutes (`plans/contact-fragmentation-at-range/
2026-09-28-log-analysis.md`). The user's verdict: *"we badly need grouping, currently all units get
single call outs and it's way too much noise. Fixing this is priority."*

This is the evidence `plans/group-contact-model/plan.md` Stage 5 (composition) was deferred
**waiting for** on 2026-09-19 — *"may never be built... do not start on reasoning alone; the
evidence has to come from a sortie."* The deferral's own condition is now met.

## What the user wants to hear

> *"Units that perceptually belong to single group, like outpost or convoy, should get single
> contact report. Then speak more when there is something important to know. That model of 'group'
> -> 'tanks and IFVs' -> '2 tanks in front, 3 IFVs' or something like that. More signal, much less
> noise."*

> *"The closer things are, the more important they are, because they can be a threat. If there's 5
> units 5 km away, all I need to know that there's a group. If those units are 1 km away, I really
> want to know if there's AAA in there and what else classifications are available. But again, not
> as repetitive constant lines, but as '1 shilka, 2 tanks, several trucks'."*

Two rules fall out, and the second is the one that kills the noise:

1. **Detail is earned by range**, because range is threat. Far: the fact of a group. Near: what is
   in it, with the threat named.
2. **Speech is triggered by refinement, not by detection.** Each line must say something the
   previous line did not. A contact being detected is not, by itself, news.

**Confirmed by the user**: the line mixes exact and vague in one breath — *"1 Shilka, 2 tanks,
several trucks"* — which is the 2026-09-19 rule (exact counts only beside firm identification) still
holding, and **threat orders the line**, so the Shilka leads on capability, not on count.

## What makes units one group: it is associative, not geometric

The user's own framing: *"It's really an associative question, 'do these objects belong together?'"*

A gaze-wedge proposal was put to him and **refuted immediately**:

> *"a convoy traveling on road is one group, no matter if it fits into single sector. I could fly
> through the middle of it and it would then be on both sides of ownship, but be single group."*

So group membership is **not** bearing-contiguous, not bounded by a sector or a look, and cannot be
computed from the observer's angular frame the way `perception.clustering`'s separability is. A
group can span 180°.

Four cues, all from his description:

- **Proximity** — the obvious one, and the only one currently modelled anywhere.
- **Common fate (shared motion)** — the discriminator that does the work he describes here:
  > *"A convoy might pass a checkpoint that has units, still convoy is its own group and checkpoint
  > it's own."*

  Spatially interleaved, perceptually two groups. What separates them is that the convoy is
  *moving together along a road* and the checkpoint is not. Movement detection already exists
  (merged 2026-09-22, over the mission-sandbox velocity feed), so this cue has a data source.
- **Figure–ground contrast, relative to local density** — grouping threshold is not absolute:
  > *"In a wide open desert, like my test mission is, a wide line of objects is observably a group,
  > because it stands out from nothingness. In area where there's a lot of things, a group is
  > something that is much more tightly together and can be observed that way."*

  So the same 400 m spread is one group in empty desert and not one group in a cluttered area. A
  fixed radius cannot express this; the separation that counts as a boundary has to be judged
  against the typical separation nearby.
- **Similarity** — implied by the reporting vocabulary (*"tanks and IFVs"*), and by a pair of
  aircraft in formation reading as one thing.

## Groups split and merge, and that is normal, not an edge case

> *"That same convoy can break into smaller pieces. That typically happens in DCS, if some units are
> destroyed. A part of the convoy continues ahead, while the tail section cannot and so the convoy
> breaks into two groups."*

> *"Also a pair of aircraft are a group, in theory. Lead and wingman. Often they fly in formation, an
> obvious group. But they can separate to individual units. And in case of aircraft, again merge into
> a unit. Ground unit groups can split and merge too, though that does not happen so often."*

Note what this demands: a group is not a per-tick recomputation whose output happens to be stable.
It is something with **identity over time** — it can be the same convoy after it loses three
vehicles, and two groups where there was one, which is a *reportable event* in itself ("the convoy
has split") rather than a bookkeeping detail. Split/merge is the normal life of a group, and the
aircraft case makes merge as ordinary as split.

## Open, for the architect rather than the user

- Whether a `Group` is persisted belief state with its own lifecycle (parallel to `Contact`) or a
  view recomputed per tick with stable association. The split/merge-with-identity requirement above
  is the constraint that decides it, and it points hard at the former.
- How figure–ground contrast is expressed mechanically — the honest version is that the boundary is
  a *relative* gap (a separation much larger than the typical separation among neighbours), not a
  constant. Whatever is chosen must not become another tuned radius, which is exactly what the
  angular-separability rework deleted from `perception/clustering.py`.
- The relationship to `belief.callouts.group_candidates`, which already groups *at speech time* by
  matching words and adjacent clock. That mechanism is not wrong, but it is a different thing —
  grouping by how a report reads, not by what belongs together in the world. Decide whether it
  survives alongside a real group model or is subsumed by it.
- `docs/concept/STATE_TRANSITIONS.md` already carries *"group of units at one location is a single
  threat, reported by its highest-capability member"*, and `BL-B11` (threat-based report
  prioritisation, deferred) holds the spec for the threat ordering this needs. Neither was written
  with this model in mind; both should be read before designing.
