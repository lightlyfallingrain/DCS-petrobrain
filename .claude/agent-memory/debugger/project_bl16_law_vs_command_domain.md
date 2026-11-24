---
name: bl16-law-vs-command-domain
description: BL-16 flight_control -- the law reasons in physical directions (collective + = up) but SIGN maps to DCS command direction (2087 + = down); a SIGN change never re-signs the law. Check LAW_DIR, not only SIGN, when an axis runs away.
metadata:
  type: project
---

On 2026-11-24 (debug-2026-11-24c) the collective ran to full up at every mode-1 take. Cause: `SIGN.collective`
became −1 on 2026-11-18 (M0-C), but `law_update`'s collective terms (integrator, rising-collective guards,
torque feed-forward) assume up-positive and were fed the command directly. Fix added `LAW_DIR` + `law_domain`
in `flight_control.lua`. The RPM-floor lockout had been masking the runaway in one direction.

**Why:** "command domain" (SIGN-mapped, what LoSetCommand takes) and "law domain" (physical) were treated as
one thing in every comment ("already SIGN-mapped, the domain the output stage writes"). Toy-plant law tests
run in the law's own domain, so they cannot see a boundary sign error; only a module-level test of
"climbing at take → which way does 2087 move" can.

**How to apply:** when any BL-16 axis diverges right after a take, first print the first law frame's
error, rate and the actual arg (trace has `a1100..a1113`) and ask which way the arg moved vs what the law
wanted — before suspecting gains. Pitch/roll `LAW_DIR = +1` was never derived. Separately, the pedal write
has an in-flight offset (arg = 0.32 − command) handled by a learnt write bias; see [[bl16-sign-revert-guard-flowthrough-check]].
