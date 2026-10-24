# BL-B97 — Attack-run LOS: "eyes on" means line of sight, and "where is it?"

- [x] **Two sortie-reported defects in the attack-run loss/regain register, from the 2026-10-24
  sortie: "eyes on" fired for a target still behind a mountain (F2), and a new voice command,
  "where is it?", to get a guidance update on demand (F3).** #status/done #needs-flight Captured
  verbatim in `docs/acceptance/2026-10-24-sortie-feedback.md` F2/F3, explored with the user the
  same day, planned in `plans/attack-run-los/plan.md`, implemented per
  `plans/attack-run-los/implementation.md`, reviewed APPROVED (no required fixes) in
  `plans/attack-run-los/review.md`. **Security plan review, performance review and security deep
  analysis all waived by the user for this change** (2026-10-24: "skip the security in the attack
  run plan, go to implement"; "skip perf and security on these fixes"), recorded per the
  dispatching instruction rather than a separate agent run.

  **F2 root cause and fix.** `belief/attack_run.py`'s loss/regain register
  (`AttackRunState.last_spoken_unresolved`) was keyed on `cause == "too_far"`, so a stale
  `"obstructed"` (terrain-blocked) verdict that aged past `ATTACK_TARGET_LOS_MAX_AGE_S` (1.5 s)
  fell through to `"unknown"` and read as "regained sight" — speaking `"Eyes on, ..."` with no
  fresh look at all. Matches the sortie report exactly (*"had visual, lost when I turned away and
  flew behind ridge, a minute or so"*). Re-keyed on `tier != 1`: `"Eyes on"` now fires only on a
  genuine fresh tier-1 (naked-eye, LOS-gated) look. The losing-sight wording now branches on
  effective cause: `"too_far"` keeps the existing guidance-plus-age phrasing, `"obstructed"` speaks
  a new `"Behind the ridge, <phrase>."` once (option C of three mocked wordings; user: *"I still
  get info on where it's believed to be"*; "ridge" is used for any terrain, by user direction),
  and `"unknown"` falls through to bare guidance with no qualifier.

  **Decision 2 (user, agreed verbatim): "behind the ridge" is held, not re-decayed.** A new
  `AttackRunState.terrain_blocked_held` flag keeps a genuine fresh `"obstructed"` verdict's
  consequence alive across that verdict's own freshness-window staleness, until a real tier-1 look
  supersedes it — otherwise the same staleness mechanism F2 fixes for the sighted/unsighted edge
  would silently re-occur one step removed, for the qualifier itself. This narrows but does not
  close `[[BL-B76]]`'s own open question (whether `Contact.live_los_clear` ever actually reads
  `False` live, rather than merely being rejected at admission) — `BL-B76`'s step 2 mountainous-
  sortie measurement is unchanged and still the thing that answers that.

  **F3: "where is it?"**, voice-only (user: *"voice only"*, no F10 equivalent) — new
  `crew_console.drain_where_is_it` speaks the current attack-run guidance phrase on demand, from
  the live engaged-run `AttackRunState` when one exists, or from a throwaway state built fresh
  when a target is selected but no run is engaged. Outside either case (no target selected, so no
  run is possible) it answers `"No target."` (user decision, superseding the plan's draft `"Unable,
  no attack run."`). New pure `belief.attack_run.query()` function computes this without mutating
  `state`, reusing the same `_current_alignment`/effective-cause logic F2 introduced.

  **Checks** (run directly by DoD, not just reported): body-layer — ruff format/check, `mypy src`
  (74 files, strict), `pytest` 2663 passed/4 xfailed (was 2650/4 before). audio-adapter — ruff
  format/check, `mypy src` (16 files), `pytest` 349 passed/2 skipped. Both match the implementer's
  own report. Five pre-existing `test_attack_run.py` tests needed updating (not just extending)
  because their old assertions pinned the exact pre-fix behaviour being corrected — see
  `implementation.md`'s "Existing tests updated" for which and why. Two independent mutation
  reversions (the `tier != 1` keying, the `effective_cause` substitution) each broke tests as
  expected, confirmed directly rather than trusting the implementer's report.

  **Command map** was left stale by design (`where_is_it` added to `audio-adapter`'s vocabulary) —
  the implementer correctly deferred `/command-map` to the main loop per the dispatching
  instruction, not a defect in this entry.

  **Acceptance boundary, stated plainly.** Everything above is verified against the existing unit
  suite and two independent mutation reproductions — that proves the code implements the decided
  behaviour, not that the behaviour reads right from the cockpit. Two things a fixture structurally
  cannot reach: whether "Behind the ridge, <o'clock>" lands at a moment that actually helps during
  a live attack run, rather than merely being correct on paper; and whether "where is it?" during
  a real run ever hits a race the unit tests' synthetic ticks cannot reproduce (e.g. a poll where
  the engaged run's own state is mutated the same tick the query reads it — `query()`'s purity
  guard rules this out by construction, but a live poll loop is the only place that construction
  is actually exercised against DCS's own timing). **Not yet flown.** Flight check card:
  https://claude.ai/artifact/BxG7nojsxP5tBA1YCk4Mob, and
  `docs/acceptance/2026-10-24-sortie-feedback.md` (F2/F3) for the same check in prose.

  Source of truth is `docs/acceptance/2026-10-24-sortie-feedback.md` F2/F3 — the user's own words
  there outrank this entry. Related: `[[BL-B70]]` (the register this entry re-keys), `[[BL-B76]]`
  (the open question Decision 2 narrows but does not close), `[[BL-14]]` (attack-run target
  selection and run guidance, the milestone this register belongs to).
