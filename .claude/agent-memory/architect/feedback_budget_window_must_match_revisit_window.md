---
name: feedback-budget-window-must-match-revisit-window
description: A time budget reset once per cycle lets two budgets land in one revisit window (BL-B110 glass budget: 28 s became 40 s); count it over the steps a revisit actually spans. Also check whether the current default already IS the user's described behaviour before reshaping it.
metadata:
  type: feedback
---

When a plan bounds a revisit time with a per-cycle budget (binocular glass time per scan cycle),
reset at a fixed point in the cycle, **every leg except the one at the reset point sees two
budgets inside one revisit window** — the tail of cycle k's and the head of cycle k+1's. BL-B110's
"12 s per cycle" would have given a 40 s worst flank revisit, not 28 s. The fix is a rolling sum
over the last n steps (n = number of steps a revisit spans), a short tuple field, not a scalar.

**Why:** found on the third BL-B110 pass (2026-11-02) while writing the revisit table for the
user's chosen alternative (b); the second pass had written (b) as a scalar `glass_cycle_spent_s`
and nobody had checked which window it bounded.

**How to apply:** for any budget/limit meant to bound a latency, write down the latency's window
first, then make the budget's accounting window identical to it. Also: the same pass found the
user's requested order ("ahead first, alternate sides") was already today's default `SCAN_PLAN`
— the second pass had reshaped it away. Before redesigning a default to match user words, test
whether the existing default already matches them ([[feedback-scan-cycle-means-true-revisit]],
[[feedback_verify_state_not_the_account_of_it]]).
