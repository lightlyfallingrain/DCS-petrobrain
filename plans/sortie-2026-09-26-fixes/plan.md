### Goal
Fix three sortie-flown defects in `body-layer`: crossing callouts spoken for contacts Petrovich
cannot physically see (Fix A), binoculars getting permanently locked off a watched/orbited contact
after one interrupted look (Fix B), and player speech interrupting binoculars when it should not
(Fix C) — per `plans/sortie-2026-09-26-fixes/decisions.md` (the binding spec) and `diagnosis.md`
(root cause, two already-failing tests).

This plan also disposes of a fourth item raised mid-task (Decision 2a): "sector coverage" — making
sure *all* contacts in a scanned/watched sector eventually get looked at, not just re-eligibility for
one — which is ruled a separate, larger piece of work and staged out of this branch (see "Sizing
call: Decision 2a" below).

### Read against, and how superseded decisions are handled
- `plans/binocular-optic/plan.md` D4 ("a player command lowers them, unconditionally") —
  **superseded** by Decision 2: the unconditional trigger already only fires on an *understood,
  dispatched* command in most of the codebase (see Stage 4 finding below); the one place it doesn't
  is a code defect, not a reversal of D4's reasoning. D4's own reasoning ("the pilot asking for
  something is prima facie evidence...") is kept as the *default* for every command except the two
  named exceptions (unrecognised speech, `follow` already on-target). D4's text in
  `plans/binocular-optic/plan.md` is left as written; Decision 2 is what is in force per
  `decisions.md`'s own framing.
- `plans/binocular-optic/plan.md` D5 ("a failed identification retries on range, not on time") —
  **superseded** by Decision 2/2a for the *watched-or-orbited* case specifically: D5's own
  rationale ("a contact at constant range has not become more identifiable") is sound for a contact
  being closed on, and this plan does not touch that case. Range-based retry (`RETRY_RANGE_FRACTION`)
  stays; time-based re-eligibility is added *alongside* it, per Decision 2's explicit instruction,
  for the case D5 didn't cover.

### Decision 3 accommodation (briefing-derived belief is pull-only) — stated, not built
Fix A's gate lives entirely inside `ContactStore.tick`'s sixth block (below), which only ever
produces *spontaneous* events — it runs unconditionally on every poll, never in response to a player
question. `route_event`/`_render_lifecycle_text` (the shared event-to-text renderer) is not touched
and gains no visibility parameter. A future pull-only answer to "where are the trucks?" would be
answered the way `follow`/`report_all`/`describe_contact` already are today — a direct call into
`belief.tools.describe_contact` / `belief.speech.render_contact_report`, which never goes through
`Event`/`route_event`/`tick`'s pipeline at all. So gating `tick`'s spontaneous path structurally
cannot suppress a future query answer; the two are already different code paths, not one gate a
future feature would have to work around.

### Affected Modules / Files

**Fix A**
- `body-layer/src/belief/contacts.py` — `Contact` gains `unobservable_since_sim: float | None`
  (mirrors `los_masked_since_sim`); `ContactStore.tick`'s sixth block (`CONTACT_RANGE_CROSSED`)
  gains a cockpit-mask observability check at emission, computed the same way block seven already
  re-applies `los_clear`. New imports: `perception.cockpit_mask.{COCKPIT_MASKS, STATION_CO_PILOT,
  is_visible}`, `perception.geometry.body_relative_direction`.
- `body-layer/src/belief/decay.py` — new `CALLOUT_OBSERVABILITY_GRACE_S` constant, in the same
  documented-placeholder style as the module's other timing constants.
- `body-layer/tests/test_contacts.py` — the already-failing
  `test_range_crossing_does_not_fire_for_a_contact_behind_the_cockpit_mask` becomes passing; add a
  companion test for the grace window (a contact masked for less than the grace period still gets
  its crossing callout).

**Fix B**
- `body-layer/src/belief/optic_policy.py` — `OpticState` gains `pending_attempted_at_range_m: dict`
  (attempts a look has covered but not yet delivered) and `attempted_at_time_sim: dict[str, float]`
  (B2); the GLASSING branch of `decide()` splits "not steady" (interruption) from
  `look_is_finished` (natural end) so only the latter commits pending marks; `lower_binoculars`
  interrupts without committing; `is_worth_a_look` gains a `now_sim` parameter and an
  `OPTIC_RETRY_INTERVAL_S` time-based branch alongside the existing range check.
- `body-layer/tests/test_optic_policy.py` — the already-failing
  `test_a_command_interrupted_look_is_not_permanently_burned` becomes passing; add a companion test
  for time-based re-eligibility on a look that *completes naturally* but the contact never advances
  in classification level and never closes range.

**Fix C**
- `body-layer/src/belief/crew_console.py` — `_handle_utterance`'s `_note_player_command()` call
  moves from unconditional to inside the `disposition == "handled"` branch; `_handle_follow` records
  the resolved `contact_id`; `CrewConsole` gains `last_command_target_contact_id: str | None`.
- `body-layer/src/belief/optic_policy.py` — `OpticState` gains `look_contact_id: str | None`, set
  at the GLASSING-transition site alongside the other look-envelope fields, cleared by
  `_back_to_scanning`.
- `body-layer/src/logger.py` — the "any command lowers binoculars" glue block gains the
  already-on-target carve-out, reading `crew_console.last_command_target_contact_id` and
  `runner.optic_state.look_contact_id`.
- `body-layer/tests/test_crew_console.py` / `test_optic_policy.py` — new tests: an unrecognised
  free-text utterance does not increment `commands_handled`; `say_again` already doesn't (pin it as
  a regression guard); `follow` on the currently-glassed contact does not lower.

**No `audio-adapter` change.** See Stage 4's finding — the seam already carries what Fix C needs.

### Implementation Plan

**Stage 1 — Fix A: observability gate on the crossing-callout path**
Makes `test_contacts.py::test_range_crossing_does_not_fire_for_a_contact_behind_the_cockpit_mask`
pass.

Where the check goes, and why: `ContactStore.tick`'s sixth block already receives `ownship` and is
the sole producer of `CONTACT_RANGE_CROSSED`; this is the one point that is (a) exclusively the
spontaneous/volunteering path (Decision 3's constraint) and (b) already the precedent for
re-applying a perception-time gate at emission (block seven's `los_clear` reuse, with its own
"the reset is load-bearing" comment this fix mirrors exactly). `route_event` does **not** gain an
ownship/gaze parameter — it stays a pure renderer, which is what keeps it safely reusable by a
future query-answer path (Decision 3) without inheriting a rule that must never apply there.

Mechanism: reuse `perception.cockpit_mask.is_visible` against the contact's *current true* bearing
(`perception.geometry.body_relative_direction(observer, contact.last_position, ownship.heading_
true_deg, ownship.pitch_deg, ownship.bank_deg)`), the identical primitive `visibility.py` already
uses at detection time — deliberately not the gaze cone (`within_gaze`/`FOCUS_CONE_HALF_WIDTH_DEG`):
Decision 1 is explicit that a merely-out-of-current-gaze contact must still get its tracking update,
only a *physically unseeable from any gaze direction* one may not. Cockpit mask is exactly that
test; the gaze cone is not.

Grace window: `Contact.unobservable_since_sim` tracks how long the mask check has failed
*continuously*, reset to `None` the instant it passes again — same shape as
`los_masked_since_sim`/`masked_for_s`. `CONTACT_RANGE_CROSSED` may fire only while
`now_sim - unobservable_since_sim < CALLOUT_OBSERVABILITY_GRACE_S` (or the contact is currently
observable at all). This governs both the event and the `last_announced_range_km` update, matching
the existing `fresh` gate's shape immediately above it in the same block.

**`CALLOUT_OBSERVABILITY_GRACE_S` is a placeholder value, not a settled one** — proposed starting
point `10.0` (roughly `OBSERVED_WINDOW_S / 1.6`, i.e. shorter than one full scan cycle: long enough
to cover "slid behind the doorframe for a few seconds," per the user's own wording, short enough
that a sustained rear-hemisphere leg of an orbit does go quiet). This needs the user's flying-feel
judgment after a sortie, the same way `IDENTITY_HALF_LIFE_S`/`POSITION_HALF_LIFE_S` are documented as
revisitable rather than derived.

**Scope note on other callout kinds**: `CONTACT_MOTION_CHANGED` has the identical structural gap (no
visibility check anywhere in its block) but is a *broader* one — it fires for every contact, not
only watched ones, so gating it the same way would change behaviour for cases the sortie never
reported. Flagged, not fixed here, per the task's own instruction to scope to the reported defect
plus identical-and-equally-narrow cases.

**Stage 2 — Fix B1: an interrupted look does not mark the target attempted**
Makes `test_optic_policy.py::test_a_command_interrupted_look_is_not_permanently_burned` pass (this
test alone requires no time-based change — an interrupted look that never gets marked is
immediately eligible again on the very next completed scan cycle).

`OpticState` gains `pending_attempted_at_range_m: dict[str, float]`. At the SCANNING→GLASSING
transition (the site that currently builds `attempted` and stores it straight into
`attempted_at_range_m`), it is stored into `pending_attempted_at_range_m` instead;
`attempted_at_range_m` is carried through unchanged. The GLASSING branch of `decide()` splits its
current single condition:

- `not steady` (turbulence/manoeuvring interruption, or `lower_binoculars` called from outside) →
  drop the pending map, return to scanning via the existing `_back_to_scanning` (which resets
  `pending_attempted_at_range_m` to empty along with the other look-scoped fields).
- `look_is_finished(...)` true while still steady (natural end: nothing left to improve, or
  `MAX_LOOK_S` elapsed) → merge `pending_attempted_at_range_m` into `attempted_at_range_m` (and
  `attempted_at_time_sim`, Stage 3) first, *then* call `_back_to_scanning`.

`lower_binoculars` (external, command-triggered interruption) goes through `_back_to_scanning`
directly, exactly like the `not steady` case — pending marks are dropped there too, which is the
fix for the diagnosed defect.

**Stage 3 — Fix B2: time-based re-eligibility**
Makes the companion test for a *naturally completed* look on a contact that never closes range and
never advances classification pass.

`OpticState.attempted_at_time_sim: dict[str, float]`, committed at the same point as
`attempted_at_range_m` in Stage 2 (value: `now_sim` at commit). `is_worth_a_look` gains a `now_sim`
parameter (its sole caller, inside `decide()`, already has it) and an added branch: worth a look if
`now_sim - attempted_at_time_sim[contact_id] >= OPTIC_RETRY_INTERVAL_S`, alongside the existing range
check (either condition suffices).

`OPTIC_RETRY_INTERVAL_S`, declared beside `RETRY_RANGE_FRACTION` in `optic_policy.py` (an
optic-mechanism constant, not a belief-decay half-life, so it does not belong in `decay.py`):
proposed starting value `4 * SCAN_CYCLE_PERIOD_S` (~64s at the current scan plan) — long enough that
re-looks don't dominate "identification takes priority over search" every cycle, short enough that
a stalled contact gets retried well inside a typical encounter rather than after hundreds of
seconds. Also a placeholder needing the user's judgment.

**Stage 4 — Fix C: command-dependent lowering**

*Finding, stated up front because it changes the expected cost*: disposition classification
(`act`/`confirm`/`say_again`/`fallthrough`) is computed **in body-layer**
(`belief.voice_commands.classify_response`), not in `audio-adapter` — `audio-adapter` only supplies
the raw match signals (`token`, `match_ratio`, `confidence`, `verb_anchored`, `ambiguous`) that
`classify_response` consumes. **No cross-subproject interface change is needed for Fix C.** The
"was this understood" and "does this redirect attention" facts are both already available entirely
within `belief/`.

Tracing the actual current behaviour (not the assumption in the task brief) narrows the real defect:

- `handle_command` (the token-dispatch surface: F10, `act` disposition, a committed `confirm`)
  already only calls `_note_player_command()` when a real command is being dispatched — this path is
  already correct.
- `say_again` is handled entirely inside `_act_on_voice_decision`'s own branch (prints the
  "say again" line, returns) and **already never calls** `_note_player_command()`. Already correct;
  add a regression test so it stays that way.
- An initial `confirm`-band question also **already** does not lower binoculars (it only records
  `_pending_confirmation` and renders the question) — matching Decision 2's "nothing was asked for
  yet" principle for the not-yet-acted-on case. **This is the answer to the confirm-band edge case**:
  do nothing on the question; lowering happens only if/when the player affirms, which re-enters
  `handle_command` and is already correct.
- **The actual bug**: `fallthrough` routes to `handle_line` → `_handle_utterance`, which calls
  `_note_player_command()` unconditionally, *before* checking whether `parse_utterance` actually
  understood the text (`parse.disposition == "handled"`). An utterance the free-text parser also
  fails to understand (escalated to the brain layer) still burns the interrupt today. This is the
  fix: move the `_note_player_command()` call inside the `if parse.disposition == "handled":`
  branch.

`follow <target>` continuation: `OpticState` gains `look_contact_id: str | None`, set to the chosen
look's `contact_id` at the SCANNING→GLASSING transition (Stage 2/3's same site) and cleared by
`_back_to_scanning`. This names only the *primary* (chosen/centred) target of a look, not every
contact the look's field of view happens to cover — a look centred on contact A that incidentally
covers contact B still counts as "not on B" for this check, matching the user's fallback
("if...NOT looking at target, lower...re-point at the target") rather than requiring full envelope
overlap testing.

`CrewConsole` gains `last_command_target_contact_id: str | None`, set by `_handle_follow` right
where it resolves its target, and reset to `None` at the top of every dispatch so a stale value from
an earlier `follow` can't leak into an unrelated later command's evaluation. `logger.py`'s existing
"any command lowers binoculars" glue block (which already reads `commands_handled` before/after
polling) adds one check: if the just-dispatched command's target equals the current look's
`look_contact_id` while still `GLASSING`, skip `lower_binoculars` for this poll. Every other
dispatched command keeps today's unconditional-lower behaviour (D4's default, kept as the fallback
per Decision 2).

The "re-judge, don't assume" half of `follow`'s spec needs no new code: once binoculars are lowered
and the target is set to `watch`, the existing `SCANNING`→`choose_look`/`is_worth_a_look` cycle
already re-evaluates from scratch every completed scan — there is no "assume raised" path to remove.

### Sizing call: Decision 2a (sector coverage)
**Staged out of this branch, as its own follow-on plan** (proposed:
`plans/optic-sector-coverage/plan.md`), not implemented here. Reasoning:

Decision 2a's requirement — every contact in an attended/scanned sector eventually gets looked at,
not just re-eligibility for whichever one the loop happens to land on — is a change to **which**
target `choose_look` selects among several worth-a-look candidates (a least-known-first or
round-robin fairness rule), not a change to **whether** a given contact may be looked at again
(which is all Stages 2/3 touch). That is a different mechanism, with real behavioural tradeoffs the
user should see before it's built, not after:

- What bounds the "everyone gets a look" obligation so a 30-unit sector doesn't starve every other
  behaviour (search, react-to-threat, other watched contacts).
- What "genuinely cannot be resolved" means as a give-up condition, and what happens to such a
  contact afterward (stop retrying entirely? retry at a much longer interval? say so out loud?).
- How this interacts with `choose_look`'s existing watched-contact preference and its "most targets
  in one look" coverage rule.

These are exactly the class of question `AGENTS.md`'s "Explore Before Deciding" calls out — lived
judgment about what feels right in the cockpit, not derivable from the sortie log alone. Folding it
into this branch would also make Stages 2/3 harder to review in isolation, since a selection-fairness
change and a per-contact eligibility fix would land as one diff. Time-based re-eligibility (Stage 3)
is not a stand-in for coverage and should not be tuned as though it were — a sector's tenth contact
still only gets picked when `choose_look` chooses it, and today's coverage rule (most targets in one
look, then watched preference, then nearest) is untouched by Stages 2/3.

### Risks & Unknowns
- `CALLOUT_OBSERVABILITY_GRACE_S` and `OPTIC_RETRY_INTERVAL_S` are both placeholder values pending a
  flown sortie's feedback, per the sections above — do not treat either as tuned.
- Stage 1's gate uses the co-pilot cockpit mask only (the one populated station, per
  `cockpit_mask.py`'s own docstring) — correct for the only station this project currently models,
  but worth naming since a second station later would need the same gate re-applied per-station.
- Stage 4's `look_contact_id` naming the *chosen* target only (not full envelope membership) means a
  `follow` naming a contact that is incidentally in view but not centred will re-point even though it
  was technically already visible in the binocular FOV — a deliberate simplification (see Stage 4),
  flagged in case a sortie shows it feels wrong in practice.
- `CONTACT_MOTION_CHANGED` carries the identical observability gap (Stage 1's scope note) and is not
  fixed here; a future sortie could reproduce the same "spoke about something behind the aircraft"
  symptom through that event kind instead of `CONTACT_RANGE_CROSSED`.

### Decisions Requiring User Input
- **Confirm the two placeholder constants' starting values** (`CALLOUT_OBSERVABILITY_GRACE_S = 10.0`,
  `OPTIC_RETRY_INTERVAL_S = 4 * SCAN_CYCLE_PERIOD_S ≈ 64s`) are reasonable to fly with, or state a
  preferred starting point — both are cheap to change later and don't block implementation.
- **Confirm the Decision 2a sizing call**: sector coverage as a separate follow-on plan (not this
  branch), rather than a third stage here. If the user wants it folded in now anyway, that changes
  this plan's stage count and likely warrants an Explore pass first (per `AGENTS.md`) given the
  starvation-bound and give-up-condition questions above are genuinely open.
- **`CONTACT_MOTION_CHANGED`'s identical gap** (Stage 1's scope note): confirm it's fine to leave
  unfixed for now, or say if it should be pulled into this branch alongside `CONTACT_RANGE_CROSSED`.

### Second-order effect
Stage 1 makes the volunteering/answering split (Decision 3) a real seam in the code (spontaneous
events flow only through `tick`/`Event`/`route_event`; queries flow only through
`describe_contact`/`render_contact_report`) rather than an implicit convention — this is what a
future Mission-Interpreter-fed pull-only answering feature will build on directly, and narrows that
future work to "add a query path using the existing describe/render machinery" rather than
"disentangle spontaneous and answered speech first."
