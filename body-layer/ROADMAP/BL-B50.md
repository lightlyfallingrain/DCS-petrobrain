# BL-B50 — Group callout suppression is defeated by any two alternating lines

- [ ] **BL-B50 — `belief.callouts`' group suppression is a one-slot signature plus a speak-only
  membership-snapshot refresh, and any two alternating group lines defeat both.** #status/open
  Found during [[BL-B47]]'s fix, 2026-10-10, and **measured by the Reviewer** rather than reasoned
  about — the numbers below come from driving `render_group_disclosure` + `mark_group_spoken` in
  `CalloutScheduler.tick`'s own sequence, oscillating a contact in and out of a group on alternate
  ticks.

  | scenario | pre-`BL-B47` | post-`BL-B47` |
  |---|---|---|
  | one oscillating class-level SAM | silent | **one** line, then silent 5 ticks |
  | that SAM **+** one out-of-phase oscillating armor | one line, then 8 silent ticks | **10 lines / 10 ticks**, indefinitely |
  | two oscillators of two distinct **new** classes, no air defence | **10 lines / 10 ticks** | same |

  **The third row is why this is filed as a `callouts` defect and not as a SAM-repeat defect.** That
  configuration is fully reachable *today*, with no air defence anywhere and without `BL-B47`'s fix.
  The mechanism is general:

  - `last_spoken_signature` is a **single slot**, not a history set, so an alternating A/B/A pattern
    of lines passes the guard every time.
  - `mark_group_spoken` refreshes `last_spoken_member_contact_ids` **only when the group speaks**, so
    each speech re-arms the *other* oscillator by refreshing a snapshot that does not contain it.

  A **single** oscillator cannot churn, before or after the fix: a contact announced once as an
  arrival stays in the snapshot, so a later rejoin is not an arrival at all. The ratchet needs two
  alternating line shapes. That mitigation is real and was not stated in `BL-B47`'s implementation
  log — worth knowing before anyone tries to reproduce this with one contact and concludes it is not
  there.

  **What `BL-B47` did and did not do.** It lowered the ingredient count from *"two oscillators with
  distinct unknown classes"* to *"one oscillating air-defence contact plus any one other arriving
  class"* — a real widening of reachability, strictly inside a hole that already existed. The
  Reviewer's ruling, which this entry records rather than re-litigates: ship the fix, file the
  mechanism.

  **It interacts with [[BL-B48]], and the interaction is the practical risk.** `EAGER` infantry
  cohesion producing a group 6 km across is precisely the input that makes membership flip
  tick-to-tick, which is the ratchet's only required ingredient. **Fix either and the other stops
  mattering much** — which is an argument for not fixing this one in isolation, and for reading both
  before [[BL-12]]'s group-identity redesign starts.

  Repetition is a defect class this project has fixed twice and the pilot has reported directly, so
  a bound that holds "in principle" is not the same as safe. The fix shape is a history set rather
  than a one-slot signature, plus a membership snapshot that refreshes on observation rather than on
  speech.
