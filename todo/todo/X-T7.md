# X-T7 — Binoculars are barely used

- [x] **Binoculars are barely used.** #status/done *"Mostly using naked eyesight, even when should pick
  binoculars (automatically) to classify and identify contacts. Not even for watched. I did see the
  blue binocular cone in the debug tool a couple of times, but generally it was not used."* The
  binocular optic merged 2026-09-24 (`c398675`) and this is its first flown verdict: **fail**. The
  optic exists and is occasionally selected, so this is a policy/trigger defect rather than a
  missing capability. **Fix merged (`fix/sortie-2026-09-26`, Fix B1/B2) — an interrupted look no
  longer burns the retry budget, and time-based re-eligibility unlocks a watched/orbited contact
  held at constant range. DoD PASSED on fixtures/console; awaiting the sortie**, same
  live-acceptance-debt entry as above. **Sector coverage (all contacts in a scanned sector
  eventually get looked at, Decision 2a) is explicitly not part of this fix** — staged out as its
  own follow-on needing an `/explore` pass, see `body-layer/BACKLOG.md` ([[BL-B20]]).

  **CLOSED 2026-10-16 by the user's own observation from flying** — his words:
  *"X-T7 can be closed, binoculars are used now, I can see that in the debug visualization."*

  So the Fix B1/B2 pair is **flown and confirmed**: the blue binocular cone he could previously see
  only *"a couple of times"* is now routine. The instrument that settled it is the eyesight-view
  debug tool, not the speech stream — which is the point of having built it: an optic selection has
  no spoken observable of its own, so without the visualization this verdict could only have been
  inferred from classification rates.

  **What this closure does not cover**, kept explicit so the clearance is not read wider than it is:

  - **`[[BL-W6]]`'s other two observables** — cockpit-mask/occlusion callout suppression (its part 1)
    and the unrecognised-utterance / `follow`-on-glassed-target behaviour (its part 3) — are
    separate in-cockpit effects of the same merge and are **not** confirmed by this. That entry keeps
    `#needs-flight` for them; only its binocular half is cleared.
  - **`[[BL-B20]]` sector coverage stays open and was never part of this.** *"All ten units to my
    left get identified"* is still expected to fail and must not be read as a regression —
    `[[BL-W6]]`'s own entry says so, and it wants its own `/explore`.
  - The two constants this behaviour rests on, `CALLOUT_OBSERVABILITY_GRACE_S` (10.0 s) and
    `OPTIC_RETRY_INTERVAL_S` (~64 s), were shipped as **starting values pending exactly this
    sortie's feedback**. The user's verdict is that the behaviour now happens, which does not say
    the cadence is right; retuning them remains available and is now cheap, since behaviour
    constants moved into `body-layer/config/defaults.toml` under `[[X-T26]]`.
