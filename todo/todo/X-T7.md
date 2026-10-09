# X-T7 — Binoculars are barely used

- [~] **Binoculars are barely used.** #status/in-progress *"Mostly using naked eyesight, even when should pick
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
