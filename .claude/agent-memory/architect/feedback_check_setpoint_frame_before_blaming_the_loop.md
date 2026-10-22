---
name: check-setpoint-frame-before-blaming-the-loop
description: When a measured closed-loop steady error is attributed to the controller (needs integral/deadzone comp), first check whether the setpoint's reference frame differs from the plant's -- the frame mismatch can BE the disturbance (BL-B80, 9K113 run 10)
metadata:
  type: feedback
---

BL-B80's brief said run 10's 0.06-0.10 deg steady error meant "the loop needs an integral term or
deadzone compensation". The numbers fit a different cause better: the probe held its target fixed
in the **airframe** frame while the 9K113 sight is **world**-held, so heading drift (~0.07 deg/s) was
a ramp disturbance; ramp / loop gain (1 /s) = 0.07 deg, exactly the band. Putting the setpoint in
the world frame removes the disturbance instead of fighting it.

**Why:** a probe's convenient frame (hold the mark at 0.500) is not the product's frame, and a
controller fix sized from the probe would have been built against an error the real design does
not have.

**How to apply:** before designing a controller fix from a measured error, write the error as
(disturbance / gain) and ask which disturbance has that size. If it is a frame mismatch between
setpoint and plant, fix the frame and re-measure before adding controller terms -- stage the
controller work behind that measurement (v2 plan Stage 5 is gated on Flight B for this reason).
Related: [[bl-b80-elevation-calibration-derivation]].
