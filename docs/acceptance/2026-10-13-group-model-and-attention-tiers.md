# The group model, attention tiers, and what the attack run needs — user direction, 2026-10-13

**Captured verbatim before any planning pass**, per the standing direction of 2026-10-05. This came
out of the `/explore` on whether `BL-14` needs a contact record per unit, and it answers that
question by **reframing it**: the answer is not "fold or do not fold" but *resolution depends on
attention*. That reframing is the most consequential thing in this document.

It also supersedes nothing yet. It is an input to planning, and the structure below is explicitly
offered as a concept rather than a decision — his words: *"Not final word, but concept."*

---

## Part 1 — the three questions, answered

### "step right" walks what the pilot sees, not what Petrovich holds

> *"when I say step right, select the next target to the right from ownship perspective, i.e. what I
> see out the window"*

**Consequence.** The list being stepped through is the *world*, not the belief store. So a group that
Petrovich has resolved into four records while six vehicles sit there cannot serve `step right`
correctly at target-selection time: the pilot's third press would land on his fourth record while his
eye is on a vehicle Petrovich never founded. Per-unit records are a requirement for *selectable
targets*, confirmed — but see Part 3, which bounds *when* that requirement applies.

### Aiming is at a unit, and the tolerable error depends on the weapon

> *"aiming at unit. With guns and rockets a 40 m error could be acceptable since the pilot then
> aligns the attack visually, but absolutely not with 9K113, it must be exact."*

**This is the sharpest constraint in the document, and it splits the acceptance criterion in two.**
The bounded-fold work (`BL-B58` option 2) gets a held position to **40 m**, i.e. 2.29° at 1 km,
under the naked-eye channel's own `BEARING_SIGMA_DEG = 3.0`. By his reading that is **acceptable for
guns and rockets** — the pilot closes the loop with his own eyes — and **not acceptable for the
9K113**, where the copilot must hold the sight on the target for the missile's whole flight.

So "is 40 m good enough" has no single answer: **it is good enough for the weapon that lets the
pilot correct, and not for the one that does not.** Anything built for ATGM guidance needs a
materially better position than the fold-bounded figure, and that is a per-weapon requirement rather
than a global one.

### Whether he is wrong about the count depends on what he can see

> *"being wrong: it depends on what he actually sees, LOS."*

Not a defect to be eliminated, then — an honest consequence of perception, and the existing
line-of-sight machinery is what decides it. This is consistent with the whole no-omniscience line
and means an undercount is acceptable **when it reflects what was visible**, and only then.

---

## Part 2 — what a group is, in his own words

> *"group is a collection of units in somewhat same location. That through certain similarity belong
> together. Be it location only, location and movement, unit types etc.*
>
> *group consists of individual units*
>
> *we could think of groups as follows. Not final word, but concept"*

```
group {
- id
- position
- iff=unknown/friendly/enemy/neutral/civilian/mixed   <-- deferred, but needed later
- units_by_classification = [
  "unknown" = [],
  "armor" = [],
  "truck" = [],
  "infantry" = [],
  "air defense" [
    "LRSAM" = [<unit info>],
    "AAA" = [
      { type = zsu, location=..., other_data, ... , iff=}
    ],
    "unknown" = [<unit info>,...]
  ],
  etc
  ]
}
```

> *"For reporting purposes each branch of the tree can be collapsed into high level understanding:
> group, classes of units, more detailed classes, types, individual units.*
>
> *A group can be treated as a group but also as it's indivudual members.*
> *Contact reports treat groups as groups/collections to reduce noise and just state the important
> things.*
> *Things far away are more imprecise by nature. The closer something gets, the more precise
> information we can detect."*

**What is new here against what is built.** Today's `Group` (BL-12) carries a `composition` as a
flat multiset of `(op_class, count)` plus a separate `air_defence_composition`. His structure is a
**tree with collapsible branches** — group → class → sub-class → type → individual unit — where the
*same* structure answers a noise-reducing group callout and a precise per-unit query, depending on
how far down it is read. `iff` is named as a field, **deferred but needed later**.

The flat composition is a lossy projection of that tree. Nothing built is wrong, but the shape is
narrower than the one he is describing, and `air_defence_composition` existing as its own field is
a symptom of the tree being flattened — in his structure it is just the `"air defense"` branch.

---

## Part 3 — attention tiers, verbatim

> *"We probably need tiers of attention."*

> *"- low:*
>   *- there's units out there, but they are far away. Beyond class detection distance*
>   *- expected info: `<where>` and far/mid-distance and few/several/many*
>   *-> collapse to group level report*
> *- medium:*
>   *- units at <= 5km*
>   *- expected info: `<where>` and how far and few/several/many, rough classification "there's
>     armor" etc.*
>   *-> group and classification level report*
> *- high:*
>   *- watched units, units selected as targets, units player asks about by "describe group ..."*
>   *- expected info: `<where>` and how far and few/several/many per classification*
>   *- can select individual units and their exact position*
>   *- watched units get eyes-on more often, so also data about them is better*
>   *- target units get constant eyes-on, so given LOS does not break, Petrovich is looking at them
>     near-constantly (attention stealing behaviour when implemented) and knows their position as
>     perfectly as belief allows, should be practically perfect at near distance.*
>   *-> report dependent on action*
>     *- attack runs get attack run specific guidance per individual unit*
>     *- "where are they?" -> group position report*
>     *- "where's that Shilka" -> report on Shilka*
>     *- "what armor is there" -> report on armor, types and counts*
>     *- etc. these are not exact wordings, but examples"*

---

## Why this resolves the question it was asked to answer

The open question was: does `BL-14` need a contact record per unit, or accurate positions for the
records Petrovich holds? The measured dilemma was that **bounding the fold fixes accuracy and cannot
fix existence** — two of six real units had no record at all, before and after — while *not* folding
reverses `D5` and produces 82 contacts for 2 units.

His tiers dissolve that. **Resolution is a function of attention, not a global policy:**

- At **low** and **medium** tier, the fold's undercount is not merely tolerable, it is the *correct*
  behaviour — the expected output is `few/several/many` and a rough class, which is exactly what a
  collapsed tree gives. Noise reduction is the goal there.
- At **high** tier, Petrovich is looking at those units near-constantly, so the evidence to resolve
  individuals *exists* in a way it does not at range. His own words: *"knows their position as
  perfectly as belief allows, should be practically perfect at near distance."*

So the fold is not the enemy of `BL-14`; **unconditional** folding is. What is needed is that
promotion to high tier (watch, target selection, or a direct question) drives the belief layer to
resolve the group into individuals, rather than the ambiguity policy being one setting for all
ranges and all attention states.

**That is a different and larger piece of work than the within-group split considered earlier**, and
it is better: it has a stated trigger, it matches where the evidence actually is, and it leaves the
noise-reduction behaviour untouched where it is wanted.

---

## Consequences worth recording now, before anything is planned

1. **`BL-14` cannot be planned as a pure consumer of today's group model.** It needs per-unit
   records for selected targets, and the mechanism that produces them (attention-driven resolution)
   does not exist. Either `BL-14` grows that scope or it is sequenced behind a milestone that does.
2. **The 9K113 constraint is a hard one and may not be reachable from the naked-eye channel at all.**
   "Must be exact" against a believed position whose own bearing noise is 3.0° is a demanding
   requirement; it probably implies the 9K113's own optic path, with its much tighter angular
   precision, is the only channel that can serve ATGM guidance. Worth checking before `BL-14`
   assumes a position good enough for missile guidance can come from anywhere else.
3. **The tree structure interacts with BL-12's merged `Group`.** `composition` and
   `air_defence_composition` are a flat projection of his tree; `iff` has no home yet. Any move to
   the tree is a data-model change to code merged yesterday, and `docs/PROCESS.md`'s
   superseding rule applies — the flat form was not wrong, it was narrower.
4. **Attention tiers overlap existing machinery and must be reconciled, not reinvented.** `BL-4`'s
   attention levels, `Attention`/`effective_attention`, the watch mechanism, and the 5 km figure he
   names here against the existing 10 km player bubble and the naked-eye class-detection ranges from
   the vision calibration. A plan should start by mapping his three tiers onto what exists rather
   than adding a fourth concept beside them.
5. **`iff` is deferred by his own note** — *"deferred, but needed later"*. Do not build it; do not
   design it out either.

---

## Status

Captured, not planned. The `/explore` that produced it is complete for the question it was asked.
Next step is a planning pass that decides how much of this belongs to `BL-14` and how much to a
preceding milestone — and that decision is his.
