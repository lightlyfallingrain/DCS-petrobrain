# Cones slice 2 — the three model decisions, settled

User decisions 2026-09-21, taken before an architect pass because each sends the design somewhere
different and none is answerable from the code.

## 1. Optic multipliers are per-tier

**Decision: per-optic, per-tier multipliers** — not one magnification with optic-dependent
thresholds.

Two independent sources say the current model is wrong: ED's
`recognition_distance_ratio_threshold` is 0.25 naked-eye against 0.5 for optics (glass buys
proportionally more recognition than detection), and the 2026-09-21 sortie measured presence scaling
sub-linearly with magnification while class scales supra-linearly. `optics.py` currently treats an
optic as a magnifier with the tiers belonging to the eye.

Per-tier was chosen because it is what was actually measured. It costs a calibration entry per optic
per tier, which is accepted.

### The multipliers, and why they come from the BTR-60 alone

Derived against the naked-eye baseline (BTR-60 3.1 / 0.4 / 0.2 km):

| optic | presence | class | type |
|---|---|---|---|
| binocular (Б-6 6×30, handheld) | 2.42 | 3.50 | 3.00 |
| 9K113 wide (×3.3, stabilised) | 3.55 | 7.00 | 6.50 |
| 9K113 narrow (×10, stabilised) | 5.81 | 13.75 | 15.00 |

The same arithmetic on the infantry observations gives **different** numbers (binocular class 3.33,
9K113 wide class 3.33, narrow 7.50). That is not measurement noise and must not be averaged away —
see decision 3. It is the clamp.

**Note the stabilisation effect is visible in this table**: the handheld ×4 binocular buys less
presence (2.42) than the stabilised ×3.3 sight (3.55). Lower magnification, more detection range.

**Known unmodelled residual:** the presence multipliers still differ between units (binocular 2.42
for the BTR, 3.33 for infantry). The likely cause is that a BTR at 3.1 km is already
contrast-limited while infantry at 0.6 km is acuity-limited, and magnification helps acuity limits
more than contrast limits. Flagged, not modelled — a single per-optic constant will be somewhat
wrong for one class of object either way.

## 2. Both direction and dwell — they are different mechanisms

**Decision: build both.** User: *"Direction limits attention area, dwell is looking at something
with intent."*

That sentence is the design:

- **Direction** is a *filter* — it bounds where attention is, and composes with the now-unbounded
  sector `AttentionArea` (`todo/todo.md`, merged 2026-09-21). It answers *where is he looking*.
- **Dwell** is an *act* — sustained attention on something specific, with intent. It answers *what
  is he working on*.

They are not two spellings of one timer. ED supplies numbers for the dwell half
(`average_det_time_max_dist_*`: 1 s → 10 s air, **10 s → 60 s ground**, scaled by skill; optic scan
time scaling with scanned-area ÷ field-of-view) and the user's own diagram supplies the direction
half (`docs/concept/STATE_TRANSITIONS.md`: `ahead → left → ahead → right`, forward-weighted).

Neither substitutes for the other: a scan pattern with no dwell teleports between sectors, and dwell
with no pattern never decides where to point.

## 3. Distinctiveness: a default plus an exception field

**Decision: a per-`op_class` default, with a per-type exception field for the units that need one.**
User: *"A vehicle shape is vehicle shape. Human shape is very distinct. Radar dishes as well."*

This avoids fabricating a distinctiveness value for ~150 profile rows — the failure mode that
produced the S-300's 5.0 m generic in the first place.

### The measured anchor, and the clamp that explains infantry

Naked-eye class ÷ presence ratio:

| unit | ratio |
|---|---|
| BTR-60 | **0.13** |
| Infantry AK | **1.00** |

Infantry classifies at *exactly* its detection range, at all four instruments. Composition that
reproduces this without per-unit multipliers:

```
class_range = min(presence_range, base_class_range × optic_class_mult × distinctiveness)
```

**Checked against every infantry row.** Naked: clamped ✓. Binocular: predicts 0.6 × 3.50 = 2.1,
clamps to 2.0 ✓. 9K113 wide: predicts 4.2, clamps to 2.0 ✓. 9K113 narrow: predicts 8.25, clamps to
4.5 ✓. All four fall out of the clamp.

**This is why the optic multipliers come from the BTR-60**: it is the non-distinctive baseline, so
its ratios are the optic's own contribution uncontaminated by clamping. Infantry's apparent
"different multipliers" are the clamp seen edge-on.

**One row does not fit**: infantry *type* through the 9K113 wide — predicted 1.3, observed 0.6,
identical to the binocular row. Could be real (×3.3 and ×4.0 are close) or could be that the two
looked the same in the cockpit. **Recorded as unexplained rather than fitted to.**

### Which classes get which default

Not settled here beyond the user's own three groupings — vehicles ordinary, humans distinct, radars
distinct. The S-300 evidence supports the radar grouping: it was identifiable at 4.5 km where the
model said 345 m, which is the same shape of error as infantry's.
