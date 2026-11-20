---
name: reference-euler-rate-body-rate-transform
description: Standard ZYX Euler-rate-to-body-rate kinematic transform for aircraft/helicopters -- use to convert LoGetAngularVelocity-style body rates into heading/pitch/roll rates for any turn-rate or damping question.
metadata:
  type: reference
---

For any future flight-dynamics question involving body rates (`p, q, r` from a gyro-style getter
like `LoGetAngularVelocity`) vs. Euler angle rates (`φ̇, θ̇, ψ̇` — roll/pitch/heading rate as a
human or a shaper thinks of them), the standard ZYX Euler-sequence kinematic transform is:

```
p = φ̇ − ψ̇·sinθ
q = θ̇·cosφ + ψ̇·cosθ·sinφ
r = −θ̇·sinφ + ψ̇·cosθ·cosφ
```

For near-level flight (θ ≈ 0, a non-climbing turn) this reduces to `p ≈ φ̇`, `q ≈ ψ̇·sinφ`,
`r ≈ ψ̇·cosφ`. In a steady 60° bank turn: `q ≈ 0.87·ψ̇`, `r ≈ 0.5·ψ̇` — body yaw rate reads *half*
the true turn rate at 60° bank, and body pitch rate is nonzero even though the aircraft is not
actually pitching relative to the horizon (it is pitching around the turn). This is textbook
aircraft kinematics (Stevens & Lewis, *Aircraft Control and Simulation*; Padfield, *Helicopter
Flight Dynamics* ch. 3), not helicopter- or DCS-specific, and not something that needs
re-deriving or re-sourcing next time it comes up.

**It does not tell you which frame a specific DCS getter returns** — that is always an empirical
question for a live probe (see `aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`
for `LoGetAngularVelocity`'s measured axis mapping on the Mi-24P, which is a different, already-
answered question from this one). Use this transform once the frame is known, to convert between
the two, or to predict what a damping/turn-rate signal *should* read in a steady turn so a
measurement can be checked against it.

Full writeup and sourcing: `aircraft-layer/research/2026-11-20-helicopter-flight-dynamics.md`,
Finding 1.
