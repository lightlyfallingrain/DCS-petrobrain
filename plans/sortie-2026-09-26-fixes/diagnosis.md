### Debug Report

Diagnosis only, per task brief — no production fix applied. Covers the two higher-priority
findings from `todo/todo.md`'s "Sortie 2026-09-26 — crew behaviour findings" (crossings outside
FOV/cockpit-mask, and rarely-used binoculars). The confirm-band and "full scan"/"scan full"
findings from that same sortie are out of scope here (the confirm-band one is a separate,
already-flagged defect; "full scan" is already closed on `main`).

Both defects reproduced with **failing tests**, added to the normal test suite:

- `body-layer/tests/test_contacts.py::test_range_crossing_does_not_fire_for_a_contact_behind_the_cockpit_mask`
- `body-layer/tests/test_optic_policy.py::test_a_command_interrupted_look_is_not_permanently_burned`

Baseline before these additions: `ruff format --check`, `ruff check`, `mypy --strict src`, and
`pytest` (1292 passed, 4 xfailed) are all clean on `main` (`5e78ea3`, merged into this worktree's
base). Both new tests fail against current code; nothing else regressed (1292 passed, 4 xfailed, 2
new failures, exactly the two defects).

## Reconciling the ASCII debug-tool snapshot against the belief-truth log

Resolved before trusting either as evidence, per the coordinator's flag. The user's
`eyesight_view.py` snapshot shows roughly eleven believed contacts at 11.0-11.6 km, but
`~/dcs-belief-truth.jsonl` has exactly one row anywhere beyond 10 km in the whole 5368-row log
(`CONTACT_12`, an S-300PS 40B6M tracking radar, `believed_range_m=10610`,
`range_cap_tripwire=True`) — apparently contradictory if both are read as "current belief state."

**They are not measuring the same thing, and both are correct on their own terms.**
`belief_truth_log.py::write_poll` (`src/belief_truth_log.py` lines 316-359) writes one row **only**
for a `perception.detection_trace.DetectionTrace` entry that is (a) `GateOutcome.ADMITTED` **this
poll** and (b) resolves to a `Contact` via the observation-id join — i.e. one row per naked-eye
re-detection that actually clears the visibility gate that poll, joined to whatever contact it
updated. It is not, and was never meant to be (its own module docstring: built specifically to
catch a *fresh, gate-clearing* naked-eye admission going somewhere physically impossible, "the
absurd, not tuning a detector"), a full per-poll dump of `ContactStore`. `eyesight_view.py`'s
believed markers, by contrast, come straight from live `store.contacts` (`believed_markers_from_
contacts`) every frame, regardless of which channel last touched them or whether the naked-eye
gate admitted anything this particular poll.

So a contact that is *not* being freshly re-admitted by the naked-eye channel on a given poll —
because it is beyond `perception.visibility.NAKED_EYE_RANGE_CAP_M` (10,000 m, matching
`CONTACT_12`'s one logged row almost exactly), outside the gaze cone, or masked — produces **no**
belief-truth row that poll, even though it is still sitting in `store.contacts` and still drawn by
the eyesight view. `CONTACT_12` itself is very likely the same S-300 site the snapshot's -055
deg/11.5 km cluster shows: caught once, right at the 10 km edge, by the naked-eye channel (hence
the one logged row and its tripwire), then tracked on (by the scope/hybrid channel, which has no
`DetectionTrace` instrumentation at all — `perception/detection_trace.py`'s own docstring: "only
the naked-eye channel is traced") well beyond that range, invisible to this particular log from
then on. Also note the snapshot's own `radius=5.0km` is `eyesight_view.py`'s **display canvas
scale** (`DEFAULT_RADIUS_M`, a rendering choice, "corrected... 2026-09-25" per that module's own
docstring specifically to stop it being read as a detection limit) — it is unrelated to both the
10 km naked-eye cap and the 1,750 m binocular classification window discussed under Defect 2 below.

**Conclusion: no contradiction in the underlying belief state, only in log completeness.** The
belief-truth log is a narrow, intentionally-scoped tripwire on naked-eye re-admissions, not a
belief audit; the eyesight view is the complete live picture. Both remain usable as evidence below,
with that scope now stated rather than assumed: belief-truth-log figures in Defect 2 describe
naked-eye-tracked contacts specifically (the correct scope for a naked-eye/binocular policy
question), and the snapshot is used directly, not against the log, for the two points below.

**The snapshot is itself further, concrete corroboration of Defect 1.** Its footer: gaze
`9_oclock`, centre `-90 deg +/-15 deg` (i.e. -75..-105 deg), `optic=unaided`; the listed believed
contacts sit at -051..-057 deg — 20-35 degrees outside the current gaze cone. If any of these were
watched, the `CONTACT_RANGE_CROSSED` mechanism diagnosed below would announce them exactly as
reported, with zero check that they sit well outside where Petrovich is currently looking. This is
not proof a callout fired for these particular contacts (the snapshot alone doesn't say whether any
were watched), but it is a real, live example of exactly the belief-state shape the mechanism
requires, arising routinely rather than as a contrived edge case.

**The same cluster is not separate evidence of a Defect 2 bug.** At 11+ km these contacts are far
beyond `improvement_window_m`'s own presence->class upper bound (1,750 m glassed, `optic_policy.py`)
— the calibrated distance past which *no* optic, aided or not, can resolve class per this project's
own screenshot-derived model. Their staying `believed U` (unknown) under an unaided optic at this
range is the intended behaviour of that calibration, not a symptom of the interrupted-look defect
found below (which is specifically about contacts that *do* enter the window and still don't get
glassed).

---

## Defect 1 — crossing callouts fire for contacts he cannot see

### Observed Issue
Sortie report: *"Crossings say which way -> yes, but also says it for contacts outside FOV also
contacts masked by cockpit."* `CONTACT_RANGE_CROSSED` (the "Getting closer, .../Moving away, ..."
callout for a watched contact passing a whole-kilometre boundary) is spoken regardless of whether
Petrovich is currently looking at, or could physically see, the contact.

### Hypothesis
`belief.contacts.ContactStore.tick`'s sixth block (the block that emits `CONTACT_RANGE_CROSSED`,
`contacts.py` lines ~1058-1140) gates emission on exactly three things: current attention
(`watch`/`priority`), a deadband/sigma check on the position estimate, and time-decayed
**freshness** (`certainty_of(contact, now_sim) in ("observed", "tracked")`, i.e. "seen by any
channel within the last ~30-120s"). It never checks the contact's *current* bearing against
gaze, the naked-eye field of view, or the cockpit occlusion mask. Nor does `belief.speech.
route_event` (the function that actually renders and speaks the event) — it has no `ownship` or
gaze parameter at all, so it structurally cannot perform that check even if it wanted to.

This is a genuine no-omniscience violation, not a wording issue: the callout is driven purely by
"ownship's current position vs. the contact's last *believed* position," decayed over time, with
zero re-check that Petrovich could actually be looking at that bearing right now.

**Both reported symptoms are one mechanism, not two.** "Outside FOV" and "cockpit-masked" are
both instances of "the current bearing to a believed-but-stale contact was never checked against
anything" — there is exactly one gap, not a FOV gate with a hole and a separate mask gate with a
hole. Confirming this against the codebase's own vocabulary: the naked-eye channel's gaze cone
(`perception/gaze.py`) and the cockpit occlusion mask (`perception/cockpit_mask.py`,
`rear_cutoff_deg=130.0` plus a per-azimuth depression table) are both consulted only inside
`perception/visibility.py::check_visibility`, which runs **once, at detection time**, deciding
whether a percept is admitted into the belief store that poll. Neither is ever consulted again
once a `Contact` exists — `belief/contacts.py`'s `tick()` has no import of either module for this
block. (It does import `los_clear` for a *different* block — see "Is this the same bug?" below.)

### Is this the same class of bug as the already-fixed watch-reporting masking bookkeeping issue?
**No — related subject, different (and larger) gap.** `AGENTS.md`'s recorded example concerns the
*seventh* block (`CONTACT_ENGAGEMENT_CHANGED`, threat-envelope tracking), which **does** call
`los_clear` (terrain line-of-sight, not the cockpit mask) as part of computing whether a watched
contact is currently masked from a weapon-envelope perspective. The bug there was a bookkeeping
defect in an *existing* check: skipping the LOS call on a range/altitude short-circuit also skipped
resetting `los_masked_since_sim`, so a contact re-entering range read as instantly masked. That fix
(now in place) is about correcting a check that exists.

The range-crossing block (sixth) that the user is reporting on **has no visibility check of any
kind to have a bookkeeping bug in** — not terrain LOS, not cockpit mask, not FOV. It is a strictly
larger gap: absence of a gate, not a defect inside one. `CONTACT_MOTION_CHANGED` (also in
`callouts.py`'s `_WATCHED_ONLY_KINDS`) shares the identical absence and would very likely show the
same symptom under test, though the sortie report didn't name it specifically.

### A prior debug pass already found this exact mechanism, and a partial fix already shipped
`plans/callout-outside-gaze/debug.md` (dated before this sortie) diagnosed the identical root
cause from an earlier flight ("ground 10 o'clock, 2 km" spoken during a `scan right` command) and
explicitly recommended **against** gating on gaze — reasoning that gating would suppress a
legitimate "closing on something you told me to watch" report the instant the player looks away,
which is exactly what watch-reporting exists to do. Its recommendation was a **wording** fix
instead: give the event a distinguishing lead so it never reads as a fresh sighting. That shipped
as `belief/speech.py`'s "Getting closer, "/"Moving away, " lead (Decision 3 REVISED, 2026-09-25,
`tests/test_speech.py::test_route_event_contact_range_crossed_says_which_way_it_crossed`) — this
is exactly the "yes" half of the user's 2026-09-26 report ("Crossings say which way -> yes").

**That fix did not, and structurally could not, address the "outside FOV / cockpit-masked" half**,
because it only changes the words spoken, not whether the underlying fact (his current physical
line of sight to that bearing) is checked at all. The prior debug report's own escalation
("reversing a user-specified format needs the user's sign-off") was scoped narrowly to the wording
question; it did not consider — because it wasn't the question being asked at the time — whether
the callout should be *suppressed or reworded further* when the contact is provably unseeable right
now (versus merely "he looked away a moment ago," which the wording fix does correctly cover).

### Evidence
1. **Code reading**: `contacts.py` lines 1058-1140 (block six) and `belief/speech.py`'s
   `_render_lifecycle_text`/`route_event` (no ownship/gaze parameter anywhere in the signature) —
   confirmed above.
2. **Sortie belief-truth log** (`~/dcs-belief-truth.jsonl`, the real 2026-09-26 flight, 259 `kind:
   "speech"` rows carrying `gaze_label`/`optic_name` alongside each spoken line — a per-callout
   snapshot of what Petrovich was actually looking at when he spoke). Of 9 `CONTACT_RANGE_CROSSED`
   lines ("Getting closer, .../Moving away, ..."), several show the reported contact's clock
   position sharply disagreeing with `gaze_label` at the moment of speech, e.g.:
   - `t_sim=354.448, gaze_label="12_oclock"`: `"Moving away, armor, 6 o'clock, 1 kilometre."` — 6
     o'clock is 180° relative to heading, i.e. dead astern, well past `cockpit_mask.py`'s
     `rear_cutoff_deg=130.0` — this contact was **structurally invisible**, not merely off to the
     side.
   - `t_sim=422.75, gaze_label="2_oclock"`: `"Moving away, ground, 6 o'clock, 2.5 kilometres."` —
     same rear-hemisphere case.
   - `t_sim=116.88, gaze_label="10_oclock"`: `"Moving away, ground, 5 o'clock, 1 kilometre."`
   - `t_sim=236.234, gaze_label="2_oclock"`: `"Getting closer, ground, 10 o'clock, 0.5
     kilometres."`
   - `t_sim=328.184, gaze_label="9_oclock"`: `"Getting closer, armor, 12 o'clock, 0.5
     kilometres."`
   These are direct, real confirmation of both reported symptoms — several are plain out-of-FOV
   (gaze on the opposite side), and the two 6-o'clock cases are specifically cockpit-masked
   (beyond `rear_cutoff_deg`).
3. **New failing test**, `test_contacts.py::test_range_crossing_does_not_fire_for_a_contact_
   behind_the_cockpit_mask`: reproduces the 6-o'clock case synthetically — a watched, stationary
   contact placed at 180° relative to ownship heading (never turning to face it), closing in
   range across a whole-kilometre boundary. `CONTACT_RANGE_CROSSED` still fires. Confirmed failing
   by running it: `assert not True` (the event is present).

### Fix Applied
None — diagnosis only, per task brief. This is flagged in the brief as touching behaviour the
user has strong opinions about (the prior debug pass's own wording fix was itself a user
sign-off), so the fix should go through the user before implementation, same as that prior pass's
own recommendation.

**What a fix needs to reconcile, for whoever picks this up:** the prior debug report's own
warning still holds — a *bare* gate on "is this bearing currently in the gaze cone" would
regress the legitimate "still tracking something you told me to watch, even though you looked
away" report that watch-reporting exists to provide, and that the "Getting closer/Moving away"
wording already handles honestly for the *ordinary* stale-but-recently-seen case. The gap this
diagnosis found is narrower than "never speak about anything outside current gaze" — it is
specifically the **cockpit-masked case**, where the contact is not merely "off to the side of
where he's looking" but *physically unseeable from any gaze direction right now* (rear
hemisphere, or beyond the per-azimuth depression limit). That distinction — recently-tracked-but-
looking-elsewhere (fine, already handled by wording) vs. currently-behind-the-airframe (a real
knowledge violation) — is the one a fix needs to draw, and only the cockpit mask (not the
narrower FOV/gaze-cone check) can draw it without reopening the prior regression. Recommend
putting this choice to the user explicitly rather than assuming which of the two the "outside
FOV" half of the report meant.

Any fix will need `ownship` (already threaded into `tick()`'s sixth block) plus
`perception.cockpit_mask.is_visible`/`COCKPIT_MASKS[STATION_CO_PILOT]` computed against the
contact's current true bearing relative to ownship heading — the same primitive
`perception/visibility.py` already uses at detection time, applied a second time at emission
(mirroring how block seven already re-applies `los_clear` at emission for engagement).

### Verification
`body-layer/tests/test_contacts.py::test_range_crossing_does_not_fire_for_a_contact_behind_the_
cockpit_mask` added and confirmed failing (`AssertionError: assert not True`). Full suite: 1292
passed, 4 xfailed, 1 new failure (this test) — no other test affected. `ruff format --check`,
`ruff check`, `mypy --strict src` all clean.

---

## Defect 2 — binoculars barely used, not even for watched contacts

### Observed Issue
Sortie report: *"Mostly using naked eyesight, even when should pick binoculars (automatically) to
classify and identify contacts. Not even for watched. I did see the blue binocular cone in the
debug tool a couple of times, but generally it was not used."* The optic (merged 2026-09-24,
`c398675`) exists and is occasionally selected (confirmed: 39 of 259 spoken lines in the
belief-truth log used `optic_name: "binocular"`, ~15%), so this is a trigger/policy defect, not a
missing capability.

### Method note on data available
No live DCS log (`win-mac-sync/from-windows/dcs.crew-behaviour-sortie.log`) carries anything about
optics — confirmed zero matches for "binocular"/"optic" in that file; it only shows the
aircraft-layer bridge feeding ~2-55 units/tick. The two Mac-side logs
(`~/dcs-belief-truth.jsonl`, `~/dcs-speech.jsonl`) from the same sortie do carry what's needed:
`dcs-belief-truth.jsonl` mixes 5368 per-object ground-truth-vs-belief rows (21 keys) with 259
per-spoken-line rows (7 keys: `kind, t_sim, text, urgent, gaze_label, gaze_center_deg,
optic_name`) — the latter is exactly the optic-selection record this defect needed and is used
throughout this section.

### Hypothesis
The optic-selection policy (`belief/optic_policy.py::decide`) marks every contact a look covers
as "attempted, at this range" **the instant the look starts** (`is_worth_a_look`'s own docstring:
"a look marks every contact it covers as attempted the moment it starts... so if the stop
condition asked 'is this still worth a look', every look would end on the poll after it began").
That rule is correct and deliberately tested for a look that runs to its own natural end
(`look_is_finished`: recognition succeeded, or nothing left to learn, or `MAX_LOOK_S` expired).

**It is not correct for a look that ends early for an unrelated reason** — specifically,
`lower_binoculars(state, now_sim)` (called from `CrewConsole` "on any command from the player...
not per command type", per that function's own docstring) ends whatever the binoculars were doing
immediately, with no distinction from a naturally-concluded look. The target it was aimed at still
gets marked attempted, at whatever range the look happened to be interrupted at — even though it
received less than a full look's worth of dwell and therefore did not actually get the "benefit"
the marking rule's own justification assumes.

Once marked, `is_worth_a_look` requires the contact to close to `RETRY_RANGE_FRACTION` (0.8, i.e.
20% closer) before it is reconsidered — with **no time-based re-eligibility at all**. A watched
contact under sustained observation rather than being closed on (a stand-off, an orbit, a hover)
can sit at essentially the same range for the rest of the encounter. One player command landing
during the very first look on such a contact can permanently foreclose ever raising binoculars on
it again, for the rest of the sortie, regardless of how many further completed scan cycles pass.

This sortie was heavy with player commands: `~/dcs-speech.jsonl` shows 128 recognised utterances
over ~1528 simulated seconds (91 acted), roughly one every 12-17 seconds on average — squarely
inside the range where a command landing mid-look is a routine, not a rare, event.

### Is this what the plan specified, or a code defect?
**A code defect, not a plan reversal.** `plans/binocular-optic/plan.md` and the phase-cycle
docstring in `optic_policy.py` both describe the attempted-marking rule as applying to a look that
*ran* — the "they all get its benefit" framing presupposes the look delivered its benefit. Nothing
in the plan says an early-terminated look should count the same as a completed one; this looks
like an interaction the phase-cycle design (Stage 2) and the "any command lowers binoculars" rule
(a later, separate decision) never got cross-checked against each other. `is_worth_a_look`'s
retry rule has always applied to *completed* looks in every existing test (`test_optic_policy.py`
never exercises `lower_binoculars` mid-`GLASSING` against the retry gate) — this is a genuine gap,
not a reversal of a settled decision.

### What the belief-truth log adds beyond the code reading
Correlating the 21-key rows against `improvement_window_m`'s own presence->class band (500-1750m
for a typical vehicle) shows the window was reached, and reached repeatedly, for most contacts —
this rules out "the window is too narrow to ever be hit" as the (or at least the whole)
explanation:

- 44 of 52 contacts in the sortie had at least one belief row with `believed_classification_level
  == "PRESENCE"` and `believed_range_m` inside (500, 1750] meters.
- Several sat there for a long time and never advanced past `PRESENCE` at all: `CONTACT_33` (15
  rows across 377s), `CONTACT_5` (10 rows, 246s), `CONTACT_23` (39 rows, 828s), `CONTACT_31` (2
  rows, 191s), `CONTACT_48` (2 rows).
- `CONTACT_17` sat in-window across 1119s and only ever reached `CLASS`, never `TYPE`.

Hundreds to over a thousand seconds of dwell time inside the window, with dozens of theoretically
eligible ~16s scan cycles passing, and no advancement — that is much better explained by "the
first look got interrupted and the contact never closed 20% afterward" than by "the window was
rarely entered." (11 of 52 contacts overall never left `PRESENCE`; only 19 of 52 ever reached
`TYPE` — consistent with, though not on its own proof of, the same mechanism.)

The `optic_name` distribution itself (220 unaided / 39 binocular, ~15%) also fits: not "never
used" but "used on first opportunity, then rarely again for the encounters that didn't get closed
on quickly" — including at least one watched contact (`"Watching ground, 10 o'clock, 1
kilometre."` at `t_sim=788.941` was spoken with `optic_name: "binocular"`), so "not even for
watched" is not absolute, but is consistent with "watched contacts get one shot like everything
else, no better."

### Evidence
1. **Code reading**: `is_worth_a_look`/`can_still_improve`/`attempted_at_range_m` in
   `optic_policy.py`, and `lower_binoculars`'s unconditional-on-any-command docstring in
   `crew_console.py` — confirmed above.
2. **Belief-truth log correlation** (`~/dcs-belief-truth.jsonl`): dwell-in-window figures above,
   computed directly from the 21-key rows.
3. **Speech log** (`~/dcs-speech.jsonl`): 128 utterances / ~1528s sortie, command cadence
   consistent with frequent look interruption.
4. **New failing test**, `test_optic_policy.py::test_a_command_interrupted_look_is_not_
   permanently_burned`: a pure reproduction against `decide`/`lower_binoculars` alone (no store,
   no log) — a contact enters `GLASSING` at 1700m (inside the presence->class window), a command
   lowers binoculars one second later, and the contact's range is then held constant across 39
   further completed scan cycles (~624s of simulated time). Binoculars never come back up.
   Confirmed failing by running it.

### Fix Applied
None — diagnosis only, per task brief. The task brief specifically calls out that this finding
touches behaviour the user has strong opinions about (the phase-cycle design itself, "at least one
naked eye scan before next binocular usage," and "new command lowers binoculars" were both direct
user decisions) — a fix should not silently change either of those rules to solve this.

**What a fix needs to reconcile:** the "any command lowers binoculars" rule is deliberate and
should stay (the player asking for something is itself evidence Petrovich's own agenda matters
less right now). The narrower fix is distinguishing *why* a look ended before marking a target
attempted — a look that reached its own stop condition (`look_is_finished`, including the
`MAX_LOOK_S` cap) legitimately burns the attempt; a look cut short by `lower_binoculars` or a
lost-steadiness dropout did not deliver its benefit and arguably should not. This would need
`decide`/`lower_binoculars` to thread through *how* the look ended (or, simpler, have
`lower_binoculars` decline to advance `attempted_at_range_m` for whatever look it is interrupting)
— a real design decision about what "attempted" should mean, not a one-line patch, and one the
user should see argued both ways before it's picked, since "at least one scan phase between uses"
already exists specifically to bound how *often* binoculars can be tried, and loosening the retry
rule changes that cadence too.

### Verification
`body-layer/tests/test_optic_policy.py::test_a_command_interrupted_look_is_not_permanently_burned`
added and confirmed failing (`AssertionError: an interrupted (not naturally concluded) look should
not permanently exhaust the retry budget...`). Full suite: 1292 passed, 4 xfailed, 1 new failure
(this test) — no other test affected. `ruff format --check`, `ruff check`, `mypy --strict src` all
clean.
