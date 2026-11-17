---
name: bl17-d6-rollback-does-not-cover-queued-effector-writes
description: BL-17 D6's dispatch-error rollback does not clear a same-dispatch effector.write already queued on CrewConsole.pending_effector_writes -- flagged by the implementer, required by the 2026-11-17 re-review, not yet built as of eba9cb5c
metadata:
  type: project
---

`plans/speech-rules/plan.md` D6 states an unconditional contract: a Lua error at dispatch time
clears every one-shot transition field set during that dispatch, "so the action does not happen
without the pilot hearing about it." D20's own text carves out one case where D6 rollback
deliberately does *not* apply -- an ad hoc effector write that fails *later*, on a subsequent
poll, after the dispatch already returned "queued" cleanly (the engine's own multi-poll
execution, inherited posture, flagged as U24).

**Why this matters:** those are two different failure windows, and the carve-out only covers the
second one. A rule handler can call `effector.write` (queues cleanly onto
`CrewConsole.pending_effector_writes`) and then, still inside the *same* Lua dispatch, hit a
runtime error later in its own handler body. `_dispatch_rule` catches that, speaks "Action file
error," and calls `_reset_one_shot_command_state()` -- but `pending_effector_writes` is
deliberately not in that reset's field list (correctly, because an *earlier* dispatch's
undrained entry must survive an unrelated later command), so the entry *this* dispatch just
queued survives the rollback too. The switch still moves (and the `says` confirmation still
speaks) after Petrovich has just told the pilot the action did not happen -- a stated-contract
violation, not a cosmetic gap. The implementer caught and documented this precisely (`[[BL-17]]`
Stage 3d review fixes, `implementation.md`) but left it unbuilt since no shipped rule calls
`effector.write` yet and the review did not ask for it.

**How to apply:** the 2026-11-17 re-review (`plans/speech-rules/review-stage3d.md`, "Required Fix
4") required this closed before merge, on the same reasoning Required Fix 1 in the same review
round used to override "no shipped rule reaches this yet" -- `effector.write` is a documented,
callable Lua action from the moment the commit merges, not gated behind a stage number. See
[[rollback-on-lockfree-queue-must-use-identity-not-length]] for why the fix shape must be
identity-based (a per-dispatch token stamped on each queued entry), not a length-snapshot
truncate, given `pending_effector_writes` is appended to from either thread without a lock. If a
later reader finds this already built, check it against that identity requirement specifically --
a naive-but-plausible-looking truncate fix could pass every single-threaded test and still be
wrong.
