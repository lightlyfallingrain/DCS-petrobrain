# Position uncertainty must key on observed movement — user direction, 2026-10-13

**Captured before any planning pass**, per the standing direction of 2026-10-05. Design direction on
what Petrovich believes, arriving while `BL-B58` option 2 was being designed — and it bears directly
on that design, so it was also sent to the architect mid-pass.

---

## His words, verbatim

> *"Regarding position going stale from unit movement. Not all units move. Many of them don't.
> Therefore if unit is not moving, it is expected not to move in near future. Therefore expected
> distance travelled by that unit over shortish period of time (couple of minutes) is zero.*
>
> *Position uncertainty caused by movement must be based on whether movement is observed or not."*

---

## What it changes

`BL-12` Stage 2b made uncertainty growth **per class** — `plausible_speed_mps(op_class,
installation_component=…)`, the one shared table feeding both the association gate's elapsed-motion
inflation and `group_matches` test 5's displacement bound. Every row a stated assumption: 0 for
entrenched, 2 m/s infantry, 8 armour, 15 trucks, 8 default.

His direction is that **class is the wrong primary key**. A T-72 sitting still is not an 8 m/s
problem; it is a 0 m/s problem, and the thing that distinguishes the two is **observation**, not
type. Class remains the right bound for a unit that *is* moving, or one whose motion was never
observed — it becomes the fallback rather than the rule.

**Why this is not a tuning tweak**: it changes what the gate is a model *of*. Today it models "how
far could a thing of this type have gone"; he is asking for "how far could *this* thing have gone,
given what was seen of it". That is the same move the project already made from quantised range
buckets to a fused covariance — from a property of the category to a property of the belief.

---

## The datum exists, and sits where it is needed

Verified at `1884775`, not assumed:

| what | where | state |
|---|---|---|
| `MotionState = Literal["moving", "stopped"]` | `body-layer/src/belief/motion.py:48` | built |
| `Contact.motion: MotionBelief \| None` | `body-layer/src/belief/contacts.py` | folded per contact via `fold_motion`; **honestly `None`** when no channel supplied motion evidence |
| `plausible_speed_mps(op_class, *, installation_component)` | `body-layer/src/belief/position_belief.py:193` | the **single** shared table, consumed by the gate's inflation *and* `group_matches` test 5 |
| `Group.movement_state` | `belief/groups.py` (BL-12 Stage 4) | majority of members' motion, honestly `None` |

So the change has an obvious shape: motion state becomes an input to the one function both
consumers already call, which keeps `BL-B51`'s lesson intact — one table, never two that drift.

**The honest asymmetry to design around** (flagged, not decided): `None` is not `"stopped"`. A
contact seen only through the scope/hybrid channel never receives a motion percept at all, and
`belief/motion.py`'s own docstring says it stays honestly `None` rather than being assumed still.
Treating `None` as stationary would hand Petrovich a confidence he has not earned — the
no-omniscience boundary in its usual form.

---

## The one question his wording leaves open

He bounds the claim himself — *"over shortish period of time (couple of minutes)"* — and that bound
is load-bearing. A unit observed stationary **ten minutes ago** may well have driven off; a unit
observed stationary **ten seconds ago** almost certainly has not. So "observed stopped ⇒ zero
growth" cannot be unconditional over arbitrary elapsed time, or belief becomes more confident the
longer it goes unchecked, which is the wrong direction.

Candidate shapes, for the `/explore` or the plan:

- **Zero until a horizon, then the class rate.** Growth stays ~0 while the motion belief is fresh
  (his couple of minutes), then opens to the class speed. One new constant, and it is exactly the
  quantity he named.
- **Zero, with the existing staleness machinery doing the work.** The motion belief already has a
  demotion countdown (`motion_pending_stop_since_sim`) and the project already has
  `POSITION_HALF_LIFE_S`, whose docstring was corrected during BL-12 precisely because its old
  derivation from a flat 20 m/s no longer held. Worth checking whether a horizon already exists
  before minting one.
- **Growth proportional to how stale the motion belief is** rather than a step. More faithful,
  harder to justify a curve for without evidence.

**None of these is chosen here.** His direction is unambiguous on the principle and explicitly
bounded in time; the horizon is the calibration, and the project's standing habit is that a number
he owns gets measured or marked a stated assumption, not slipped in.

---

## Why it matters right now, beyond being correct

Three live things turn on it:

1. **`BL-14` needs per-unit positions** (his direction, same day,
   `2026-10-13-tree-cover-direction.md`). A stationary unit whose believed position does not drift
   is a unit an attack run can be aimed at. This is the cheapest available improvement to position
   quality, and it is subtraction rather than addition.
2. **It attacks `BL-B58`/`BL-B59`'s root cause from a second direction.** The drift defect needs an
   *ambiguous* fold to fire, and ambiguity needs the gate to be wide. The incident scene is infantry
   unobserved for 20 s; at 2 m/s the gate opens 40 m, and that width is what admits two candidates.
   Narrowing the gate for observed-stationary contacts reduces how often the fold happens at all —
   which is upstream of bounding how far it moves a position when it does.
3. **It may shrink `BL-B24`.** That entry is two contacts ~17 m apart, both reacquired after a 120 s
   gap, each inside the other's inflated gate. If both were observed stationary, neither gate
   inflates and the pairing never becomes ambiguous.

---

## Next step

Not planned here. It is a change to `BL-12` Stage 2's calibration premise and wants its own entry,
sequenced against `BL-B59` and the tree-cover work already queued. The architect designing
`BL-B58` option 2 has it in hand as of today, because the bound it is choosing may want to reuse
`plausible_speed_mps` — whose meaning this direction changes.
