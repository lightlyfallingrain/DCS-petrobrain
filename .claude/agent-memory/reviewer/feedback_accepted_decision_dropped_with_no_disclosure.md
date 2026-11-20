---
name: accepted-decision-dropped-with-no-disclosure
description: an implementation.md "Deviations" list is only the Implementer's own account of what it chose to skip -- it can simply not mention an accepted decision (U-numbered or not) that the plan states twice as in-scope for this stage, and the ledger script's "never named" output for that ID is the only mechanical signal. Grep for the decision's own mechanism (a clamp call site, a wire field) rather than trusting the prose summary.
metadata:
  type: feedback
---

Found reviewing BL-16 Stage 3 (`plans/flight-desired-state/review-s3.md`, 2026-11-20).

`plans/flight-desired-state/plan.md` states **twice** that U2 ("a carried value the new mode
cannot fly exactly is announced once, not urgent") is Stage 3 work: section 3's own text ("First
needed in Stage 3 (carry starts there for m2->m1)") and the Stage 3 bullet list itself ("U2's
carried-value line on unpark"). `implementation.md`'s Stage 3 section has a "Deviations and
judgment calls" list with six numbered items -- none of them is U2. Reading that list alone, and
the rest of the prose, gives no signal that anything is missing: the deviations named are all
things the Implementer chose to disclose, not an exhaustive account of everything the plan asked
for.

`accepted-items-ledger.sh plans/flight-desired-state` printed: `accepted U2 is never named in
implementation.md -- built, or deferred to a named stage? Say which there.` That one line was the
only mechanical signal this was missing -- and it is easy to read past, because the script also
flagged U3/U4 the same way, and those *were* adequately covered elsewhere (U3 repeatedly, U4 in an
already-approved earlier stage). The temptation is to treat a ledger "never named" hit as probably
noise once two of three turn out fine.

**What actually confirmed the gap**: not re-reading the prose harder, but grepping for the
mechanism U2 would need to exist -- `clamp_speed`/`clamp_altitude` call sites
(`crew_console.py`), and `fc_limits.min_ias_kmh`/`max_ias_kmh`/`floor_agl_m` reads in
`flight_control.lua`. Both clamps are called only from the `axes_*` action bodies (a *new*
mode-1 command body-layer itself constructs) -- never at the m2->m1 edge handler or in
`build_take_seed`'s unpark-carry branch, and the Lua-side limits are read only by the envelope
self-release check, never as a goal clamp. That is a negative result a prose read cannot give:
"this mechanism's only call sites are elsewhere" is checkable by `grep`, not by re-reading
`implementation.md` a second time.

The second confirming signal: the plan's own Stage 3 **card** text lists `"Speed 0" in m2 then
unpark (U2's one line, "Speed 8 0.")` as a thing to check -- the actual shipped card
(`docs/acceptance/2026-11-20-bl16-desired-state-s3-card.md`) omits that scenario entirely. A
card that quietly drops a plan-named scenario is itself a tell, independent of the ledger.

**How to apply:** when `accepted-items-ledger.sh` reports an ID as "never named," do not resolve
it by re-reading `implementation.md`'s prose more carefully -- that prose is the Implementer's own
account and can simply omit a thing with no flag. Instead (a) find the decision's own stated
mechanism in the plan text (a clamp, a wire field, a spoken line) and grep for its call sites in
the actual diff; (b) diff the plan's own card-scenario list against the shipped card file for that
stage -- a scenario the plan named for this stage but the card never asks the tester to check is
the same gap showing up a second way. Both are independent of trusting the deviations list, which
is exactly the artifact that silently dropped this one.
