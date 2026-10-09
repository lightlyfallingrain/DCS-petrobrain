# BL-W24 — Cones slice 2A + 2A.5

- [x] **Cones slice 2A + 2A.5 — DONE, merged 2026-09-21.** #status/done The first two sub-slices of the
  detection-cones slice 2 milestone (`plans/detection-cones-slice2/plan.md`).

  **2A** (`7d82018`): an `Optic` carries per-tier range multipliers instead of one magnification
  (unaided 1/1/1, binocular 2.42/3.50/3.00, BTR-60-derived); `distinctiveness` as a per-`op_class`
  default plus per-type exception; and the clamp `class = min(presence, …)` making
  `type ≤ class ≤ presence` structural. It reproduces the measurement it was built from — infantry
  class collapses onto presence at every optic, the 1.00 ratio observed at all four instruments.
  Also fixed `clustering.py`'s acuity floor, recorded benign by two prior reviews: its slackness
  proof holds only while the active optic's presence multiplier is ≤ 4.0, and the 9K113 narrow's
  5.81 expired that premise silently.

  **2A.5** (`a06f1e8`): the naked-eye intake cap counts **groups**, not objects — ten trucks in one
  glance is one perceptual event, the same ten spread across a sector is ten. `clustering.py`
  already computed that distinction; only acting on it was missing. Fixed a real defect on the way:
  a capped-out group was dropped permanently rather than retried.

  **What these deliver is the model's shape, not calibrated numbers** — and the acceptance position
  says so rather than overstating. Infantry binocular computes 1452 m against an observed 2.0 km.
  Four `xfail`s carry that gap visibly: 2A moved the binocular presence multiplier to 2.42 while
  `LOWRES_ANGULAR_RADIUS_RAD` still encodes the flat 4.0 it was derived against. They are a
  tripwire — if recalibration happens and they do not turn green, the recalibration was wrong.

  **Next: 2B** (gaze as a filter; F10 scans finally steer perception), behaviour-preserving by
  construction. Then 2C (the o'clock scan loop) and conditionally 2D.

