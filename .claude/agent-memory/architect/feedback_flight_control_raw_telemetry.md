---
name: feedback-flight-control-raw-telemetry
description: Flight-control laws steer on raw telemetry (velocity/acceleration with running averages), never a model of what the pilot feels; the no-omniscience rule is for perception, not control
metadata:
  type: feedback
---

For mode-1 flight control, the user rejected a "felt load" (`LoGetAccelerationUnits`) collective
loop: *"No need to model how pilot would feel it. For flight control, code is allowed to know and
act on raw telemetry data. Deltas probably need to be a running average to filter out vibration."*
(2026-11-20, `plans/flight-lift-vector/explore-notes.md`).

**Why:** Petrovich's perception is bounded (no omniscience), but the control law is not
perception; pilot-perception modelling added a gravity/body-frame signal that needed its own
filters and fallbacks (and was the root of the goal check's "sinks in every bank" finding).

**How to apply:** in any control-law plan, measure in the world frame from raw velocity (position
deltas or `LoGetVectorVelocity`), derivatives as running averages; use feed-forward nudges from the
desired state for fast response. Do not reach for instrument ranges or felt quantities as loop
inputs. Also from the same answers: pedals fly the slip ball only (no deliberate extra pedal).
Related: [[feedback-briefs-quote-the-plan]].
