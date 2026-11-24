---
name: bl16-law-vs-command-domain-review
description: How to verify a flight_control.lua axis-sign fix (LAW_DIR/command_for) without flying it — trace internal law math first, boundary crossings second, then mutate.
metadata:
  type: feedback
---

Reviewed `a1eec022` (BL-16 LV-1 debug pass 3, `plans/flight-lift-vector/debug-2026-11-24c.md`):
collective ran to full up because `u_c` was seeded/written in command domain while every internal
law term (integrator, guards, torque feed-forward) assumed physical up-positive. The fix added
`LAW_DIR`/`law_domain` only at the two boundary crossings (`law_init_at_take`'s seed,
`command_for`'s write), leaving all internal law math untouched.

**What worked:** grepping every internal consumer of `u_c`/`u_c_rate` first (before reading the
report's own claim) showed none of that code changed in the diff — which is exactly what you'd
expect if the bug really was isolated to the boundary and not a deeper internal sign error. That
let me *rule out* a wider blast radius (shortfall chain, anti-windup, torque FF calibration) by
inspection rather than by trusting the report's "unaffected" claims about each.

**What a mutation caught that reading alone would not have proven:** flipping `LAW_DIR.collective`
back to `+1.0` and re-running `fast-tests.sh` failed `TestCollectiveLawDirection` with a concrete
wrong number (-0.57 instead of rising past -0.25) — this is what makes the regression test a real
guard rather than a tautology restating the fix. Separately, mutating out the write-bias learner's
settle-*time* gate (keeping only saturation checks) left all 1007 tests green, independently
confirming the debug report's own disclosed gap rather than just repeating its claim.

**How to apply:** when a plan claims "fixed only at the boundary, internals unaffected" for a
law/controller with persistent state, grep every consumer of the renamed/re-signed field before
accepting the claim — a clean diff (no changes to the consumers) is itself the evidence, not the
report's prose. Then mutate the actual fix (flip the new sign table) to prove the test would have
caught the regression, per [[verify-by-mutation]] habit in this role's own instructions.

See [[bl16-law-vs-command-domain]] (debugger's memory on the same bug, root cause framing) and
`plans/flight-lift-vector/review-debug-1124c.md` for the full review, including the still-open
pitch/roll `LAW_DIR = +1` risk (pre-existing, `SIGN.pitch`/`SIGN.roll` documented in
`flight_control.lua`'s own header as "probe v2's own unverified guesses, flip once M0-E reports" —
not settled by this commit and not required of it).
