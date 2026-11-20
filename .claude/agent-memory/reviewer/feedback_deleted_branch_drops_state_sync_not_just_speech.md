---
name: deleted-branch-drops-state-sync-not-just-speech
description: When a plan deletes a decide_* branch and says "the speech moved elsewhere," check whether that branch also did a state-sync no one replaced
type: feedback
---

BL-16 desired-state Stages 1-2 (`plans/flight-desired-state/plan.md`, review-s12.md, 2026-11-20):
Stage 2 deleted `decide_flight_control`'s self-release branch (envelope/NaN/dead while flying mode
1), correctly moving its *speech* ("You have controls!") to `decide_flight_speech`, which reads the
new `flight_authority_state` mirror. But the deleted branch also reconciled `FlightControlState.
phase` back to `"PILOT"` on that same signal — and nothing replaced that half. `phase` now sticks
at `"ACTIVE"` forever after a forced self-release, and `release_controls`'s existing `phase in
("TAKING","ACTIVE") or lua_mode in (...)` OR-check then fires on stale `phase` alone, producing a
wrong "I have controls." callout for a release that never happened. Caught by reading the *old*
function (`git show <base-sha>:path`) side by side with the new one and asking "what else did this
branch do besides speak" — not by reading the new code and the plan's prose alone, which both only
mention the speech moving.

**Why:** a branch that's described as "produces speech" in a plan or implementation note is not
guaranteed to be *only* that — multi-effect branches (state write + speech) are common in this
codebase's `decide_*` functions, and deleting one because its speech moved elsewhere silently drops
every other effect it had. The existing test suite did not catch this because the test pinning the
old behaviour (`test_releases_from_active`) only exercises the state transition in isolation
(`phase="ACTIVE"` with default `lua_mode`), which was already passing — it just stopped being an
*unreachable* edge case once the reconciling branch that kept `phase` from going stale was removed.

**How to apply:** whenever a plan or implementation note says "branch X deleted, its speech moved
to Y," diff the deleted branch against the function that's left and ask: did X do anything besides
decide what to say? If it also wrote to a mirror/state field, check whether that write still
happens somewhere. A clean test suite is not evidence here — the bug widens an existing code path's
reachability rather than breaking a new one, so nothing new fails; verify by constructing the
specific sequence (ideally executing it, not just reading) rather than trusting "tests still pass."

Related: [[flight-control-lua-self-arm-level-triggered]] (same review, a second case of a plan's
explicit edge-triggered requirement being implemented as level-triggered).
