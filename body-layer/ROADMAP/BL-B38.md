# BL-B38 — Two loops still walk every contact ever founded

- [ ] **BL-B38 — [[BL-B23]] bounded total-ever-seen for *clustering only*; two other loops still walk
  every contact ever founded.** #status/open 2026-10-05 performance pass. `tick`'s per-contact loop and
  `ingest`'s non-short-circuiting gate scan are 6.4 ms / 0.7 ms today, so LATER — but they grow with
  [[BL-B24]]'s churn, and that churn is getting worse (554 contacts for 444 objects on a 70-minute
  sortie, 81 % of objects carrying 2+ contact ids). Worth re-measuring after [[BL-B24]], not before.
