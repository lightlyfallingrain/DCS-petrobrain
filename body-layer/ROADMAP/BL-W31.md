# BL-W31 — Repetition is better but not gone

- [ ] **Repetition is better but not gone — reopened 2026-09-23 from the sortie.** #status/open Aggregation
  works on same-type, same-range, adjacent-clock contacts, and the transcript shows it firing. What
  it does not catch is the run it left behind:

  ```
  ground, 12 o'clock, 2.5 kilometres.
  ground, 12 o'clock, 4.5 kilometres.
  ground, 12 o'clock, 3 kilometres.
  ground, 12 o'clock, 4 kilometres.
  ground, 12 o'clock, 4 kilometres.
  ```

  Five presence-level calls in one sector within one scan, differing only in range, two of them
  identical. They are not aggregated because the range differs, and the range is precisely the part
  that carries no information at presence level — *"ground, 12 o'clock"* five times is one fact.
  Two candidate rules, not yet chosen: widen aggregation to a range *band* at presence level only,
  or suppress re-reporting a contact already called within some window. The second is probably the
  real one, since the identical repeat suggests the same contact was called twice.

