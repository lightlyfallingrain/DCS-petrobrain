# BL-W26 — Cockpit visibility limits for the naked-eye channel

- [x] **Cockpit visibility limits for the naked-eye channel (no BL- number — a perception
  correctness fix, not a milestone; done, merged 2026-09-17, merge `bd4a4dc`,
  `feature/cockpit-visibility`).** #status/done `perception/visibility.py`'s naked-eye gate was a bare azimuth
  cone with **no elevation term at all** — a contact 90 m below and 60° off the nose passed as
  easily as one on the horizon. At 100 m AGL a contact 200 m out sits ~27° below, so this was the
  normal case, not an edge case: Petrovich saw through the fuselage and floor and reported contacts
  he could not possibly see. A standing no-omniscience violation, predating the milestone that
  surfaced it (the first live F10 sortie).

  Replaced by a body-relative occlusion mask (`perception/cockpit_mask.py`): max depression per
  azimuth band, evaluated in the airframe frame via `geometry.body_relative_direction`, so it
  follows pitch and bank rather than heading alone — a banking helicopter is exactly when a
  heading-only cone is most wrong. No aircraft-layer change was needed; `pitch_rad`/`bank_rad` were
  already on the wire and simply never consumed by `OwnshipState`. Per-station (D6, only the
  co-pilot populated), symmetric (D5, the real cockpit is slightly asymmetric but the user judged
  the difference insignificant).

  **Angles are the user's own measurement from the DCS co-pilot seat**, boresight-relative: 22° down
  flat across az 0–60, 10° at az 90, tapering to 0 at the az 130 rear cutoff. That replaced a
  screenshot-derived first pass it showed wrong in *both* directions — nose far too permissive
  (45° vs 22°), rear cutoff far too tight (100° vs 130°). Because D3 mandated splitting mechanism
  from calibration, that correction was a table swap with the mechanism untouched and not
  re-reviewed: the split paid for itself within a day.

  Petrovich is now strictly blinder by design, most noticeably close-in abeam and directly below.
  The mock flight chain drops 57 → 53 observations for exactly that reason (a target 200 m below
  passes under the nose once horizontal range closes inside ~495 m). 527 → 544 tests.

  **Risk closed 2026-09-17:** the bank sign convention was the riskiest open assumption here —
  inverted, it would have failed *dangerous* rather than fail-safe, silently swapping which side
  Petrovich gains visibility on in a turn, with no unit test able to catch it (they all check the
  code's own convention against itself). The user confirmed against DCS: **right bank positive,
  left negative** — the standard convention the implementation assumed. Verified the code behaves
  accordingly, not merely that it matches a docstring: a right-abeam contact 18.4° below is blocked
  level, rises to 11.6° *above* boresight under +30° bank, and buries further under −30°. Pitch confirmed
  the same day ("down is negative, up positive"), also matching — and consistent with that parked
  sample reading +2.76°. Both signs are now observed rather than assumed.

  Follow-up (`fix/pin-bank-sign-convention`): the gate-level bank test used a contact *directly
  below*, which rotates to azimuth ±90 under either sign — and `is_visible` folds azimuth through
  `abs()` — so it passed identically inverted. Added an asymmetric right-abeam case that fails
  under a sign flip (mutation-verified). The rotation-level geometry test already pinned the sign.
  See `plans/cockpit-visibility/` (plan, review, dod-check, implementation).

