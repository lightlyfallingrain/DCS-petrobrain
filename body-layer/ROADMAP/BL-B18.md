# BL-B18 — Overlay clips its last line at 420×200

- [x] **BL-B18 — [[BL-2.5]] overlay clips its last line at 420×200 — REJECTED 2026-09-26 (user), not fixed.** #status/done
  Closed as won't-fix rather than done: the clipping is real and the candidate fix still stands
  (re-implement dynamic sizing as its own commit, separate from any cosmetic change — the fix was
  bundled with a since-reverted restyle and went back with it). The user judged it not worth
  spending on. Reopen only if a future overlay change makes it cheap or makes the clipping worse.
