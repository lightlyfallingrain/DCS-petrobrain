# BL-B2 — `OP_SRSAM`'s internal range spread

- [ ] **BL-B2 — `OP_SRSAM`'s ~4x-7x internal range spread makes its class-level danger call early and
  often badly wrong in magnitude — recorded, not fixed, `plans/watch-reporting/plan.md` Decision
  4c, 2026-09-24.** #status/open `belief.threat._CLASS_ENVELOPES`'s derived rollup for `OP_SRSAM` is driven by
  whichever member has the longest reach in the extracted table (S-125/SA-3 at 25.0 km,
  `body-layer/data/threat_envelopes.json`) while the bucket also holds SA-8/SA-9/SA-13/SA-15, some
  under 6 km — a pilot told "danger" at 25 km for what turns out to be an SA-13 is being warned
  roughly 4-7x earlier than the real threat. Tightens automatically once type-level recognition
  resolves which member it actually is; this is a property of this project's own `op_class`
  buckets grouping systems with a wide range spread, not a defect in the belief-keyed lookup
  design, and should be recorded against the buckets (a future `object_model.py`/classification
  pass) rather than patched in `threat.py`.
