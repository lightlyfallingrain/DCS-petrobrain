### Review Summary

BL-B89 Stage 1 (sector scan: wide S-scans find points of interest, narrow visits them by priority,
a blind narrow-far sweep covers the band nothing else reaches, a mandatory naked-eye glance closes
every lap). Reviewed against `plan.md`, `explore-notes.md` (verbatim user spec), `implementation.md`'s
own deviation/discovery log, `security-plan.md`, and `body-layer/ROADMAP/BL-B89.md`.

Fast-forwarded this worktree from `e9fb4a2b` to the named tip `940397b6` (clean ancestor
fast-forward, no divergence). All mechanical checks pass from `body-layer/`:
`ruff format --check` clean, `ruff check` clean, `mypy src`/`mypy tools` both clean (strict),
`pytest tests -q` → 2587 passed, 4 xfailed (pre-existing).

The core mechanism is sound and well-tested: `choose_sighting_look`'s priority bucket matches the
explore notes exactly (verified by reading the function against the quoted spec); the sight's own
sector-wedge tables (`SIGHT_SECTOR_WEDGE_DEG`, `SIGHT_AHEAD_LEGS`) reproduce the user's worked
spans; both `_sight_in_regard_sweep` and `_sight_out_of_regard_sweep` are wired to the new
`_sight_commanded_sector` (checked by grepping the call sites, not just the file list, per the
standing "new mechanism's own call site" check — both are updated, not just one); the tuning
entries render correctly in `config/defaults.toml` (checked the rendered file, not the source
comment); removed constants (`SIGHT_SEARCH_MID_M`, `_SIGHT_WIDE_SEARCH_FAR_M`) have no lingering
code or config references, only historical comment citations.

**Verify-by-mutation on the altitude findings (Required Fix 1's subject, below):** the plan's own
memory lesson (`project_reject_not_clamp_can_empty_every_fallback`) asks whether every producer a
reject-filter touches can go empty *at once*, and whether the fallback is actually safe, not just
present. At both measured extremes (800 m/10° nose-up; 1500 m level), at least one leg
(`wide_far`/`wide_near` respectively, and always `narrow_far_sweep`) stays non-empty — the search
never fully idles within the 50–800 m/1–2 km envelope the user defined. I drove
`test_lap_mechanism_composes_correctly_when_wide_near_is_emptied_by_attitude` and the 1–2 km
parametrized test myself (not just read them) and confirm the assertions match the code's actual
output, not an assumed one. This is a flight-check item, not a defect — see Required Fix 1's
disposition below (documentation, not behaviour).

### Required Fixes

1. **`_enter_binocular_search`'s own new docstring misstates what it achieves, and should be
   corrected before merge.** It says: *"Deliberately omits `look_azimuth_deg`/`look_elevation_deg`
   from the `replace()` below — leaving them exactly as they were is 'the sight stays at its last
   position' ... for free, simply by never touching them."* But this function's **sole call site**
   (`_decide_without_guidance`'s glance-away-resume branch, confirmed by grep — there is exactly
   one call) is reached only *after* `_start_glance_away` has already nulled both fields to `None`.
   So "leaving them exactly as they were" leaves them at `None`, not at a last position — and
   `implementation.md`'s own "Notable Discoveries" section, and the new tests, already establish
   this precisely (resume renders `(0.0, 0.0)` dead-ahead, not last position). The docstring cites
   the F4/F5 sortie-feedback acceptance criterion ("Leave 9K113 at last position") as the
   justification for a design that, by the implementer's own measurement in the same commit,
   does not deliver that criterion on this path. Fix: rewrite the docstring to state the measured
   behaviour (resumes dead-ahead on every glance-away-triggered entry, because the aim was already
   nulled upstream) instead of the aspirational one. This is a required fix because it is new
   prose, written in this stage, actively contradicting a fact the same stage's own tests prove —
   not stale carry-over prose that predates the change.

   **Not required but worth a line in the same fix:** `_back_to_home`'s own pre-existing docstring
   ("the aim is carried through, never nulled ... this *is* the sight stays at last position") has
   the identical problem for the same reason, and predates this stage — `implementation.md`
   confirms it was "not previously exercised by a test that checked the resumed aim specifically."
   Since this stage's own tests are the first to expose it, a one-line pointer from
   `_back_to_home`'s docstring to the now-measured truth (or a `BL-B89` note) would stop a future
   reader trusting it. Your call whether to fold this into the same commit or file it separately;
   either is fine, leaving it unmentioned anywhere is not, since F4/F5 (`docs/acceptance/
   2026-10-20-sortie-feedback.md`) is a *settled* acceptance item that turns out, on direct
   measurement, not to be delivered by the mechanism its own closing commit claimed closed it. This
   is a real player-facing gap (the pilot was told "last position" and the sight now provably goes
   dead-ahead on every glance-away resume) and belongs on the backlog with its own ID even though
   it predates Stage 1 and is not this stage's defect to fix.

2. **`body-layer/ROADMAP/BL-B89.md` still states a decision that was reversed in the same explore
   session and never updated.** Its procedure summary reads *"`[[BL-B86]]` is folded in."* — the
   session's *first* answer. `explore-notes.md` (same date, later in the same conversation)
   explicitly reverses this: *"`[[BL-B86]]` declined, 2026-10-25. 'if B86's only thing is the high
   alt scan then reject it.' It was, so it is declined, not folded in."* — and `BL-B86.md`'s own
   entry was correctly updated to `DECLINED`. Only `BL-B89.md`'s own summary line was missed. Per
   root `CLAUDE.md` ("supersession is marked, not deleted") and this file's own role as BL-B89's
   source of truth, update the line to reflect the final decision (declined, residue folded in only
   as far as the design naturally produces it) rather than leaving the superseded answer standing
   as the record. One-line fix.

Neither of the above blocks the mechanism itself — both are documentation/decision-record
accuracy fixes, cheap to make, and should land before this merges so the record this project relies
on (per CLAUDE.md's repeated emphasis on decision-record integrity) does not carry a known-wrong
claim forward.

### Optional Refinements

- The empty-at-extremes findings (800 m/10° nose-up empties `wide_near`; 1500 m level empties both
  wide legs) are well measured and tested, and I agree with the implementer's own disposition
  (not a defect — physical limit, degraded not stalled, recovers with attitude). Worth naming
  explicitly on the acceptance/test card so the user flies exactly those two combinations and
  confirms the degraded-but-not-idle behaviour reads correctly in the cockpit, rather than only in
  a unit test. (Optional because the plan's own "Risks & Unknowns" already flags the general
  class of this risk and asks for a sortie check.)
- `SIGHT_AHEAD_WINDOW_DWELL_S` (Deviation 1, a genuinely new tunable the plan's own "Affected
  Modules" didn't name) is reasonably argued and correctly tuned (`lo=5.0, hi=120.0,
  status="judgement"`), but is, by the implementer's own admission, "not yet flown" — a candidate
  for early retuning once the alternation is observed in the cockpit, not a fix now.

### Verdict

NEEDS REVISION — two small, cheap documentation/decision-record fixes (Required Fixes 1 and 2).
Mechanism, tests, tuning, and invariants are otherwise sound; re-review of the fix commit can be
light (confirm the two docstring/roadmap edits only — no reason to re-run the full checklist).

### Review Confidence

Full read. Read `plan.md`, `explore-notes.md`, `implementation.md`, `security-plan.md`, and
`BL-B89.md`/`BL-B86.md` in full; read the changed code (`optic_policy.py`'s search-leg/glance-away/
binocular-entry functions, `body.py`'s new `_sight_commanded_sector` and both sweep functions,
`gaze.py`'s new tables) directly rather than only the implementer's account of it; drove two of the
new altitude-edge-case tests myself to confirm the assertions match real output rather than reading
them as given; ran the full mechanical check suite (format/lint/mypy×2/pytest) directly from
`body-layer/` using the main checkout's venv (this worktree has none).
