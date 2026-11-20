### Review Summary

Reviewed `feature/bl16-desired-state` at tip `60053e7f3f22926afb00a34509b5d18e94a9b40b` (checked out
onto `review/desired-s12` from that exact sha, verified via `git rev-parse HEAD`) against
`plans/flight-desired-state/plan.md` Stages 1-2, `implementation.md`, `alignment.md`,
`explore-notes.md`, and the test card. Full read of the plan, implementation notes, and every
touched production file in both subprojects; full read of `flight_desired.lua`,
`flight_authority.py`, and the relevant sections of `flight_control.lua`/`crew_console.py`/
`body.py`; spot-checked the three test-fixture-rethreading files and `check_rules.py` (the plan's
own "test blast radius" note was verified by reading the actual diff, not just the implementer's
account of it). Mutation-style verification, not just reading: Required Fix 1 and Required Fix 2
were each confirmed by driving the real Lua module through a Lua interpreter (`luajit`) with a
hand-written scenario, not inferred from the source alone.

All mechanical checks pass: `ruff format --check`, `ruff check`, `mypy --strict` (both
subprojects, run from inside each subproject per their own `CLAUDE.md`), `luac5.1 -p` on every
touched Lua file, the GETGLOBAL sweep (clean — only stdlib/DCS APIs and the legitimate
cross-module globals `flight_desired`/`flight_control`/`ai_pilot_wheel`), aircraft-layer's full
test suite (1099 passed), and body-layer's full test suite (3738 passed, 4 xfailed, 0 failed).

Two required fixes found by exercising the code, both in the aircraft-layer Lua, both real
defects against the plan's own stated behaviour — not style or scope issues. Everything else
checked (mode authority single-source-of-truth, the mode-2 seam, voice-take IAS/AGL re-check,
shadow desired-state writes, the test blast radius, the card) holds up.

### Required Fixes

1. **Decision 24's self-release reconciliation was deleted along with its speech, and nothing
   replaced the state-sync half — `FlightControlState.phase` now sticks at `"ACTIVE"` forever
   after a forced mode-1 self-release (envelope/NaN/dead), and a later "I have controls" wrongly
   reports `acted=True`.**

   The pre-Stage-2 `decide_flight_control` (base `e4792254`, lines 667-678) had a branch: `phase
   == "ACTIVE" and lua_mode == "off" and lua_release_reason in ("envelope","nan","dead")` →
   `phase = "PILOT"` plus the urgent line. Stage 2 deletes this branch (correctly moving the
   *speech* to `decide_flight_speech`, which reads `flight_authority_state` and speaks "You have
   controls!" on the `fd_mode` edge) but drops the *state* side-effect with it. Nothing else sets
   `phase` back to `"PILOT"` when Lua self-releases out of mode 1.

   `release_controls` (`belief/flight_control.py`) decides `acted` from `state.phase in
   ("TAKING","ACTIVE") or state.lua_mode in ("active","taking")` — an OR, so a stale `phase ==
   "ACTIVE"` alone is sufficient regardless of what `lua_mode` actually is. `test_releases_from_
   active` (line 285, unchanged by this diff) pins exactly this: `FlightControlState(phase=
   "ACTIVE")` → `acted=True`, with no `lua_mode` given (defaults to `"off"`). That test was
   previously only reachable in a one-poll race window, because the deleted branch reconciled
   `phase` on the very same poll Lua reported `lua_mode=="off"` with an envelope/nan/dead reason.
   With that branch gone, the window is now open-ended: any time after an envelope/NaN/dead
   self-release, a later "I have controls" utterance makes Petrovich speak "I have controls." and
   send a (harmless, Lua-side no-op) release — a wrong callout for an action that never happened,
   confirmed by the project's own "no callout fires when the pilot would not expect it" rule
   (reviewer checklist item 1; root `CLAUDE.md` "Player-facing correctness is yours alone").

   This does not affect `has_controls`/`flight_mode()` (both now read `flight_authority_state`
   exclusively, correctly), so it is not a control-authority bug — only a spoken-callout
   correctness bug. Fix: restore a reconciliation (in `decide_flight_control` or a new one-line
   check) that moves `phase` back to `"PILOT"` (and clears `pending_take_says`/`took_at_sim`) on
   this same `lua_mode`/`lua_release_reason` signal, without re-adding the now-duplicate speech
   (`decide_flight_speech` already owns that). A single test with `phase="ACTIVE"`,
   `lua_mode="off"`, `lua_release_reason` one of `envelope`/`nan`/`dead` → `release_controls`
   (or the reconciliation itself) leaves `phase=="PILOT"` would close this.

2. **The off→armed self-arm in `flight_control.lua` is level-triggered, not edge-triggered — it
   silently re-arms after a reset while still parked, defeating Q6.**

   The plan is explicit: "After `reset(epoch)` while parked, `armed` is cleared **and nothing
   re-arms it until the next park edge**. That is Q6" (section 2). The implemented branch
   (`run_flight_control`, `is_parked == true and fc_mode == "off"`) has no edge tracking at all —
   it fires every frame that condition holds, so the instant a fresh `flight_lease` arrives (which
   happens automatically, since `_apply_flight_control` sends the lease unconditionally every
   poll body-layer runs), Lua re-arms itself with **no unpark/re-park having occurred**.

   Confirmed empirically by driving `flight_control.lua` through `luajit` with the real module
   (not a paraphrase): self-arm from a park (`fc_mode` → `"armed"`) → `flight_control.reset(2)`
   while still parked (`fc_mode` → `"off"`, `fc_arm_last_t` cleared) → a fresh `flight_lease`
   arrives one second later, **still parked, no unpark edge** → `fc_mode` → `"armed"` again on the
   very next `run_flight_control` tick → the next unpark then succeeds and takes the controls
   (`fc_mode` → `"active"`, `fc_take_origin` → `"unpark"`). The exact sequence Q6 says must not
   happen: "the player gets the stick" after a body-layer restart while parked, is instead handed
   straight back to Petrovich the moment body-layer catches up with its lease — which, since the
   lease is sent every poll, is normally within about a second, well before most players would
   unpark.

   This is exactly the card's row 12 scenario, and the card's own wording ("check whether the
   mode-authority mirror reports this as `unpark_unarmed` or stays silent; say which you saw")
   reads as uncertainty about which behaviour would show up live — the live test would have
   surfaced this, but it is cheap to fix and test now rather than finding out on the card. Fix:
   track the park rising edge explicitly (a `was_parked` local, or equivalent) and gate the
   off→armed self-arm on that edge being the same frame, not on the level condition alone; or,
   if the lease is meant to arm continuously (which is the general "every park gives him the
   overlay" rule, and is probably right for the *ordinary* off→m2 case this clause also exists
   for), special-case `fd_reset_epoch`/an equivalent "reset happened, no edge seen since" flag so
   the exception Q6 asks for actually holds. A unit test driving exactly the sequence above
   (self-arm → reset while parked → fresh lease while still parked → confirm `fc_mode` stays
   `"off"` until an actual unpark/re-park) would close this and should be added regardless of
   which fix is chosen.

### Optional Refinements

- `CrewState.held_heading`/`held_altitude`/`held_speed` no longer fall back to the measured value
  when the `flight_authority_state` mirror's own field is `nil` (the old `axes.held_heading if
  not None else axes.measured_heading` merge, present before this diff, is gone — confirmed via
  `git diff`). The plan's own section 2 table lists this fallback under `CrewState.held_*`'s
  row without tying it to a specific stage. In practice this is masked by `rules/gates.py`'s
  existing "hold until known" mechanism (a command during the brief `off→taking` window HOLDs and
  retries rather than misfiring), and `flight_desired.lua`'s own `reseed_from_measured` populates
  the mirror within one tick of reaching `m1`, so the window is narrow. Not a correctness bug, but
  worth a one-line note in the plan or a follow-up commit if Stage 3 doesn't already subsume it —
  the implementer's own "Notable Discoveries" section flagged the phase-staleness deviation but
  not this one. (Optional.)
- `tools/check_rules.py`'s new `_authority_for` passes `ParkedFlightState.held_altitude_ref`
  ("B"/"R", the overlay's own letter) straight into `FlightAuthorityState.alt_ref` (which the
  schema and `flight_desired.lua` define as `"agl"`/`"baro"`), with no conversion. This is a
  dev-only dry-run harness, not production code, and nothing in the scenarios this tool drives
  appears to branch on `alt_ref`'s exact string, so it's cosmetic — but it's a silent type-shaped
  mismatch in a file whose whole job is faithfully mirroring production state. Worth a one-line
  fix (`"baro" if held_altitude_ref == "B" else "agl"`) next time that file is touched. (Optional.)

### Verdict

NEEDS REVISION

Both required fixes are narrowly scoped, Lua/Python-local, and each has a concrete test case
specified above — this should be a short Implementer round, not a redesign. Nothing else in
Stages 1-2 blocks the test card: the mode authority is correctly single-sourced in Lua, the
mode-2 seam is nil-guarded correctly, the voice-take IAS/AGL re-check matches U9/Q2's "unable
never writes state" posture, the shadow desired-state writes and `fd_*` wire encoding are
correct (ints as ints, heading-reference tagging as specified), the 75-fixture test-blast-radius
rethreading is faithful to the actual mirror semantics (spot-checked, not just read from the
implementer's account), and every mechanical check (format/lint/mypy/tests/Lua syntax/GETGLOBAL)
is clean.

**Do not fly the card until Required Fix 2 is addressed** — it directly contradicts row 9/row 12's
expected behaviour (unpark-too-soon-after-restart should refuse; this review shows it can
silently stop refusing once the lease catches up, well before "too soon" in practice) and would
make the card's own observations ambiguous rather than diagnostic.

### Review Confidence

Full read. Both required fixes were verified by execution (a real Lua interpreter against the
unmodified module), not inferred from reading alone. The body-layer full suite and
aircraft-layer's full suite were both run to completion in this review (not just re-stated from
`implementation.md`), and both passed clean — which is expected, since neither required fix has
a pinning test yet (that is itself part of each fix).
