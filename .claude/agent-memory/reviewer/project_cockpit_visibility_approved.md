---
name: project_cockpit_visibility_approved
description: cockpit-visibility (body-relative occlusion mask) reviewed and approved — rotation math verified by hand, sign-convention risk confirmed fails-dangerous not fail-safe.
metadata:
  type: project
---

Reviewed `feature/cockpit-visibility` (commits 244d436/f0945c2/7f0a5bb/e411c1b/b2fb941):
replaced `visibility.py`'s elevation-blind azimuth cone with a body-relative occlusion mask
(`cockpit_mask.py` + `geometry.body_relative_direction`). Verdict: APPROVED, no required fixes.

**Why:** the load-bearing yaw→pitch→bank rotation was hand-verified algebraically against three
independent scenarios (yaw-only at heading 90°, pitch-only nose-up making a level target read
negative elevation, bank-only rolling a straight-down target into azimuth ±90°/elevation~0) rather
than trusting that the tests were merely internally self-consistent. All three checked out against
the documented convention (positive pitch=nose up, positive bank=right wing down).

**Sign-convention risk (unverified `bank_deg` sign against real DCS):** confirmed the implementer's
own disclosure was accurate — no test can catch an inverted sign (every test drives the code's own
convention both ways), and the failure mode is **fails dangerous, not fail-safe**: an inverted bank
sign silently swaps which side gains/loses visibility during a turn, it doesn't degrade to
always-open or always-closed. Already disclosed in the plan with a live-sortie calibration queued —
not a blocker, but worth checking this reasoning directly (don't just accept "flagged" as sufficient
without confirming the failure mode is actually non-obviously-detectable).

**D3 mechanism/calibration split held**: `git show <calibration-commit>` touched only the table
tuple + derivation docstring, confirmed directly, not inferred from the implementer's claim.

**Test-quality nuance worth re-checking on similar work:** four new integration tests were
documented as "boundary-clear, holds across both placeholder and derived tables" — true — but only
1 of 4 would actually have failed against the pre-change code when checked by hand (the other 3
picked azimuth values the *old* cone already rejected/accepted for its own reason, so they don't
discriminate old vs. new behavior). The real regression proof lived in a separate pure-mechanism
test (table-agnostic, same-depression-different-azimuth). Don't accept "these tests would fail
under the old code" as true just because they're new and pass — hand-check each one against the
removed logic when the claim matters.

See [[feedback_verify_mypy_cwd_claims_by_reproduction]] for the general pattern of reproducing
claims rather than trusting reports.
