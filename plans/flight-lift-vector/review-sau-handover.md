### Review Summary

Branch `feature/bl16-sau-handover`, tip `bc47fabb` (reviewed from `review/sau-handover`, cut
from that same commit; base `f0a3540f`). Single commit, small, tightly scoped: a new
effector-sequence trigger `controls-to-player` that fires on the SAU-handover edge
(`fd_mode` moving from `m1`/`m2`/`taking` into `off`, for any cause) and switches the SAU
heading/bank/pitch channels (plus the existing B/adjustable-stops channel) ON for the player,
silently — implementing the user's verbatim direction in
`plans/flight-lift-vector/explore-notes.md` ("SAU in mode 1").

Full read of the diff (10 files, +282/-3): `src/belief/flight_authority.py`
(`controls_to_player_edge`, `_HAS_CONTROLS_MODES`), its firing site in `src/body.py`, the new
sequence file `config/sequences/mi-24p/controls-to-player.md`, three new curated effectors in
`config/sequences/mi-24p/effectors.toml`, the regenerated `switch-reference.md`/`triggers.md`,
tests in `test_flight_authority.py`/`test_body.py`, and the `BL-16.md` roadmap note.

**Edge correctness** — checked against the module docstrings and the poll-loop ordering:

- Fires on every `fd_mode` cause into `off` (release, stop, reset, forced releases) — the function
  compares `fd_mode` values directly, not `mode_cause`, matching the "any cause" requirement.
  Tested in `TestControlsToPlayerEdge` across all seven `_SILENT_OFF_CAUSES`/forced causes, plus
  a real-poll-loop test (`test_a_silent_cause_release_into_off_still_fires_the_sau_handover`)
  proving it fires independently of the urgent-speech decision.
- Does **not** fire on a take edge (`off → taking`) or a park/successful-unpark edge
  (`m1 ↔ m2`) — tested directly and through the poll loop
  (`test_a_take_edge_does_not_fire_the_sau_handover`).
- Does not fire on the default no-sample state (`off → off`) — tested directly.
- Does not fire at mission start: `_check_for_new_mission` (line ~5188) runs, and therefore
  `crew_console.reset_for_new_mission()` resets `flight_authority_state` to its declared default
  (`fd_mode="off"`), **before** line 5520 captures `previous_flight_authority` for this same poll
  — so a mission that was mid-restart with Petrovich flying can only ever present `off → off` to
  the edge check that poll. No dedicated test exercises this exact sequencing, but it follows
  structurally from the existing reset/poll ordering (unchanged by this diff) and is consistent
  with the "not fired at mission start" requirement.
- Seat swap that drops the overlay: the trigger is deliberately cause-agnostic (reads `fd_mode`
  only, not what caused it), so whatever Lua-side cause produces that `fd_mode` edge is covered by
  the same equivalence class the cause-parametrized test already exercises — there is no cause
  string the function branches on that a seat-swap-induced release could fall outside of.

**Effector correctness** — cross-checked against `switch-reference.md` and the raw dump
`config/effectors-raw/mi-24p.toml` (DCS 2.9.30.28738): `p_sau_h_channel_on` →
`SAU-H-ON-PTR`/device 10/cmd 3005/arg 237, `p_sau_k_channel_on` →
`SAU-K-ON-PTR`/cmd 3001/arg 243, `p_sau_t_channel_on` → `SAU-T-ON-PTR`/cmd 3009/arg 249 — all
three match the switch-reference table exactly, and all three are confirmed (not merely assumed)
as the "ButtonHon"/"ButtonKon"/"ButtonTon" command names in the raw dump, each a dedicated
momentary ON command with its own separate OFF command (`ButtonHoff` etc., confirmed present in
the same raw-dump region). `p_sau_b_channel_on` is reused unchanged from the existing registry
entry (`SAU-B-ON-PTR`), already wired for `seat-pilot.md`.

**ON-button question (asked in the task), answered**: these are pure ON buttons, not toggles.
`config/effectors-raw/mi-24p.toml` shows each of `SAU-H-ON-PTR`/`SAU-K-ON-PTR`/`SAU-T-ON-PTR`/
`SAU-B-ON-PTR` as `values = [{ kind = "discrete", values = [0.0, 1.0], momentary = true }]` with
command names `autopilot_commands.ButtonHon`/`ButtonKon`/`ButtonTon`/`ButtonBon` — and a
*separate* `SAU-H-OFF-PTR`/`SAU-K-OFF-PTR`/`SAU-T-OFF-PTR` element with its own `ButtonHoff`/
`ButtonKoff`/`ButtonToff` command exists for each channel. Cross-checked against
`aircraft-layer/research/2026-10-31-mi24p-park-controls-ai-pilot.md` §4 ("The buttons: channels
K/H/T/B on/off (args 243/242, 237/236, 249/248, 255/254)"), which names the identical device/arg
set independently. No DCS install was reachable from this review worktree
(`DCS_INSTALL_PATH`/`DCS_SAVED_GAMES_PATH` unset), so this is the file-level confirmation the
generated dump already carries, not a fresh read of the installed tree — but it is a confirmed
positive, not an inference: the raw dump's `momentary = true` plus the distinct `*-OFF-PTR`
element is exactly the "separate ON/OFF buttons" shape, as opposed to a single toggling switch.

Given that, the engine press behaviour the implementer claims is correct by code reading, not
just assertion: `shape = "default_square_button"`/`"default_button"` is not in
`_ABSOLUTE_WRITE_SHAPES` (`{"default_2_position_tumb"}`), so `EffectorDef.absolute_write` is
`False` for all three new effectors. In `effector_engine.py`'s row-write path, the implicit
self-check reads the effector's own arg (the momentary pulse, which rests at `0.0`/"off"), so
`_matches(effector_def, self_raw, "on")` is `False` and the self-check never short-circuits as
"already matched" — the row always proceeds to write (press). This is exactly
`p_sau_b_channel_on`'s existing, already-shipped behaviour in `seat-pilot.md` (same shape, same
arg-reads-off-at-rest situation), so the new effectors introduce no new mechanical risk class,
only three more instances of a pattern already in production.

**Whether a repeat press while the channel is already ON is harmless is correctly flagged as
unverified**, both in the `effectors.toml` comments and the roadmap note, with an explicit
pointer to the precedent (`cplr_distr`'s own `unverified = true` open question) and to
`p_sau_b_channel_on`'s prior, unescalated use of the identical pattern. No clickable-data or
flight evidence exists either way — this review could not resolve it either (no DCS install
reachable), and treats the implementer's own flag as the correct and sufficient disposition for
a momentary engage-button whose repeat-press semantics are governed by native (non-Lua) autopilot
logic not visible in any shipped file.

**Seat-gating check**: the task asked whether anything presses from a seat where the buttons
don't exist, or could toggle something unintended. `effector_engine.py`/`effector_registry.py`
carry no seat concept at all — the "Seat" column in `switch-reference.md` documents which
cockpit the raw-dump capture was taken from, it is not a runtime gate the engine checks before
writing. Writes are plain `performClickableAction(device, cmd, value)` calls, seat-independent at
the API level, matching every other effector sequence already shipped (including
`p_sau_b_channel_on` firing unconditionally on `seat-pilot`/the player's own handover). No
seat-specific risk beyond what every existing effector sequence already carries.

**Scope fit**: the diff does exactly what the plan line asks — one new trigger, its firing edge,
a sequence file, three curated effectors, generated docs, tests, and a roadmap note — nothing
broader. Responsibility sits where the existing module map says it should (`flight_authority.py`
owns the pure edge, `body.py`'s firing site mirrors every other trigger call already there,
`effector_sequences.py`/`effectors.toml`/the `.md` sequence file are the data-driven mechanism
this project already uses for cockpit switch sequences — no new mechanism invented).

**Tests**: meaningful, not decorative. The pure-function edge gets full branch coverage
(every silent/forced cause × every has-controls mode, the non-firing directions, the no-sample
default). The integration test proves `body.py` actually wires the edge to the trigger for a
cause the urgent-speech line stays silent on — the one assertion that distinguishes this trigger
from `decide_flight_speech`'s existing logic, and the one most likely to be wrong if someone
later "simplified" the firing site to reuse `authority_decision is not None`.

**Checks run** (from inside `body-layer/`, this worktree, against the main checkout's venv):
- `ruff format --check src tests` — 230 files already formatted.
- `ruff check src tests` — all checks passed.
- `mypy src` — success, no issues found (93 source files).
- `pytest tests/test_flight_authority.py tests/test_body.py -q` — 316 passed.
- `pytest tests --collect-only -q` (smoke) — 3788 tests collected, no import errors.

### Required Fixes

None.

### Optional Refinements

- No dedicated test exercises "mission restart while Petrovich was flying" directly through the
  `controls-to-player` trigger (the "not fired at mission start" guarantee currently rests on
  reading the reset/capture ordering, not on a test that would fail if that ordering regressed).
  A one-poll integration test — start flying (`m1`), fire a mission-restart event, assert no
  `cockpit_switch` write for the SAU buttons — would turn this from "true by code reading" into
  "true by test," at low cost given the existing `_start_effector_poll_loop` harness. (Optional:
  the other mission-restart-interacting triggers in this codebase, e.g. `seat-pilot`/`seat-copilot`,
  appear to rely on the same unescalated reasoning rather than a dedicated regression test, so this
  is a pattern gap, not specific to this change.)
- The `effectors.toml` comments on the three new entries are near-duplicates of each other
  ("Same momentary shape and same unverified repeat-press question as `p_sau_h_channel_on`
  above."). This is a reasonable and legible choice for a generated-adjacent config file; a single
  shared comment block referenced by all three would read marginally cleaner but is not worth
  churning the diff for.

### Verdict
APPROVED

### Review Confidence
Full read. Device/cmd/arg correctness was cross-checked against the generated raw dump
(`config/effectors-raw/mi-24p.toml`) and an independent prior research note
(`aircraft-layer/research/2026-10-31-mi24p-park-controls-ai-pilot.md`), not against a live DCS
install — this review's worktree had no `DCS_INSTALL_PATH`/`DCS_SAVED_GAMES_PATH`
(`dcs-file-investigation` skill's own precondition), so the ON-button-vs-toggle finding is a
file-level confirmation of the already-generated data, not a fresh read of the installed tree.
The repeat-press-while-already-ON question remains genuinely unverified pending a live sortie —
correctly flagged as such by the implementer and left open here too.
