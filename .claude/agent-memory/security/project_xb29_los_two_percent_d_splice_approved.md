---
name: xb29-los-two-percent-d-splice-approved
description: dcs-driven-los deep analysis — two-%d dostring_in splice (hour+FOV) verified safe; boundary condition for future look_around(x,y,alt) extension
metadata:
  type: project
---

X-B29 (DCS-driven batched line of sight, Stages 1-3) deviated from this project's own
"exactly one `%d`" plan-review rule by using two `%d` substitutions in one `dostring_in`
template (`SET_LOOK_TEMPLATE = "PB_LOOK_HOUR=%d\nPB_LOOK_FOV_DEG=%d\nreturn \"ok\""`,
`petrobrain-line-of-sight-hook.lua`) — user's own informed call, coalescing hour+FOV into
one bridge call per the plan's §17/Finding 5.

Verified safe in deep analysis (2026-10-05): both substitution points (`hour`, i.e. the
bearing clock-hour, and `fov_half_deg`) pass through the *identical* `_safeClampInt`
function — same NaN self-inequality guard, same `±math.huge` guard, same type check — with
no special-cased weaker path for either value. In particular `hour` does NOT use a modulo
(`% 360`) despite being a compass-like value; a modulo is exactly the operation that looks
natural for a bearing and that silently propagates NaN (`0/0 % 360` is still NaN). Confirmed
by reading the two call sites directly, not assumed from symmetry.

**Why:** the user raised exactly this question mid-review — "is bearing clamped as totally
as FOV, or did it get a weaker path because it looked bounded already?" — a reusable
adversarial question for any future multi-substitution splice in this codebase.

**How to apply / re-review trigger:** this clearance covers exactly two integer
substitutions reached by a total clamp. The user named a possible future
`look_around(x_coord, y_coord, alt)` variant and said it is not needed now. If that
variant is built, it changes the substitution count *and* the value class (floats/world
coordinates, not small bounded integers) — a different safety argument (`%f`/`%g` don't
have the same "only digits" guarantee `%d` does, and coordinates have no natural
`[min,max]` the way `hour`/`fov_half_deg` do). **Do not treat this clearance as covering
that future extension — it needs its own plan-stage security review.**

See [[project_br1_stage2_ollama_trust_boundary]] for the general pattern of checking
whether a stricter-looking gate secretly diverges from a looser one.
