# BL-B3 — Class-level threat rollup joined 3 of ~19 rows

- [ ] **BL-B3 — `belief.threat`'s class-level rollup only actually joined 3 of ~19 SAM/AAA threat rows into
  a class bucket on the real table — found during `watch-reporting` implementation, 2026-09-24.** #status/open
  `_derive_class_envelopes` joins `body-layer/data/threat_envelopes.json`'s `threat` names through
  `perception.object_model.profile_for` by design (Decision 4c: computed, not hand-written), but
  `object_model`'s keyword table was authored against DCS unit names, not Hoggit's wiki names, and
  most rows (Kub, Tor, Tunguska, Rapier, Roland, Chaparral, Hawk, Patriot, NASAMS, S-75, S-300, …)
  do not share a matching substring with any `_KEYWORD_PROFILES` entry, so `envelope_for` at
  `CLASS` level currently only resolves for `OP_ZU23`/`OP_SPAAG`/`OP_SRSAM` (the last via S-125
  alone) — every other SAM tier's class-level warning is silently absent until either
  `object_model.py`'s keyword table gains matching entries or `TYPE`-level recognition supplies the
  specific row directly (which already works correctly for every row, independent of this gap).
  Not a defect in the join mechanism itself (a hand-authored patch here is exactly what Decision 4c
  warns against) — the fix belongs in `object_model.py`'s own keyword coverage.
