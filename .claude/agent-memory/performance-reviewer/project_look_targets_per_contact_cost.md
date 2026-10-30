---
name: project-look-targets-per-contact-cost
description: Measured 2026-10-30 — body._look_targets costs ~4.5 us/contact/poll (look_target_for), +~1 us with the atgm-run-sight-tracking altitude replace; ~1.1 ms at 200 contacts. Use as the baseline before flagging new per-contact work there.
metadata:
  type: project
---

`body._look_targets` (every poll, every contact in ContactStore) measured on branch
`fix/atgm-run-sight-tracking` @ 5794a105, Mac, body-layer venv: 0.90 ms at 200 contacts before,
1.10 ms after `_look_target_position` added a `remembered_target_alt_m` + `dataclasses.replace`
per contact (~1.0 us/contact, linear across n = 10/50/200).

**Why:** ContactStore is never pruned ([[project-contact-store-never-pruned]]), so this loop's n
grows with sortie length; a measured per-contact figure stops future reviews guessing.

**How to apply:** new per-contact work in `_look_targets` that stays around 1 us is noise; work
approaching `look_target_for`'s own ~4.5 us doubles the loop and deserves a measurement at the
real store size. Harness pattern that worked: monkeypatch the helper back to the old behaviour for
the A/B, and assert the A/B outputs differ before timing.
