# Attack-run LOS: "eyes on" means line of sight (F2), and "where is it?" (F3)

Source: `docs/acceptance/2026-10-24-sortie-feedback.md` F2 and F3, explored with the user the same
day. Branch: `feature/attack-run-los`.

### Goal

Fix the attack-run "eyes on"/"lost sight" register so it never claims a sighting the crewman does
not actually have (F2), and add a "where is it?" command that speaks the standard attack-run
guidance phrase on demand, based on current sight/belief (F3).

### Decided, 2026-10-24 — three amendments from the user

Source: `docs/acceptance/2026-10-24-sortie-feedback.md`, F3's "Plan decisions, 2026-10-24" section,
verbatim. Each supersedes a specific piece of the design below; the superseded text is corrected in
place rather than left to contradict these, per `docs/PROCESS.md`'s "Superseding a decision" — this
plan is pre-implementation, so there is no merged behaviour to amend around, only this document.

1. **"Where is it?" outside an attack run.** The draft below answered `"Unable, no attack run."`
   whenever no run was *engaged*. User: *"if target is set, then answer. If no target (and therefore
   no attack run either) then say "No target""*. Resolved under "F3 design", point 4
   (`drain_where_is_it`) and the affected-files/tests/acceptance sections below — "target is set"
   means `_active_attack_target_task()` returns a task with a `contact_id`, independent of whether
   `runner.attack_run_state` (the *engaged* run's own phase) is `None`.
2. **Behind the ridge, held until he sees it again.** User: *"agreed"*, to the main loop's own
   proposal that a fresh terrain-blocked verdict keep the target "behind the ridge" until a genuine
   live look, rather than decaying to silent `"unknown"` once the verdict ages out. Resolved under
   "F2 design" with a new `AttackRunState.terrain_blocked_held` field, below.
3. **Command surface: voice only.** User: *"voice only"*. Supersedes point 6 under "F3 design"
   (which read "Voice phrase + typed console only, no new F10 item") and closes the "Decisions
   Requiring User Input" item below outright — not just the F10 half of it.

### Root cause of F2, from code (no detection trace available — diagnosed from code, confirmed
against the 2s/1.5s freshness windows, not assumed)

`belief/attack_run.py::decide()` tracks `AttackRunState.last_spoken_unresolved`, currently defined
as `cause == "too_far"` (`now_unresolved`, line ~857). The "regaining sight" announcement
(`"Eyes on, ..."`) fires on the `True -> False` edge of this flag — i.e. whenever the cause stops
being `"too_far"`, **regardless of whether tier 1 (a genuine live look) is what produced that**.

`_no_look_cause`'s `"obstructed"` arm only fires while `contact.live_los_clear is False` **and**
fresh (`<= ATTACK_TARGET_LOS_MAX_AGE_S`, 1.5 s default). Once a blocked verdict goes stale — which
it does after ~1.5 s, and `BL-B76` already documents that a *rejected* (terrain-blocked) candidate
never updates `Contact.live_los_clear` at all, so staleness is the common case for a long
occlusion — the cause falls through to `"unknown"` (fail-open, BL-B76's own 2026-10-16 direction:
*"log it and then ignore in cockpit behaviour"*). `"unknown"` is **not** `"too_far"`, so
`now_unresolved` reads `False`, and if the state was `True` a moment earlier (the target had gone
too-far at some point in the preceding episode), the edge fires `regaining_sight` and speaks
`"Eyes on, ..."` — with no fresh look at all.

This matches the user's own account exactly: *"had visual, lost when I turned away and flew behind
ridge, a minute or so"* — well past both freshness windows (2.0 s / 1.5 s), so by the time the
cockpit mask cleared, the only cause left to report was `"unknown"`, read by the old logic as
"resolved."

**This confirms and narrows `BL-B76`'s open step 3** ("decide whether the attack run should read
the live gate outcome rather than the stored contact") — the gap isn't only in `", obstructed"`'s
reachability, it is in the loss/regain register treating *any* non-`"too_far"` cause as "sighted."
`BL-B76`'s entry will be amended (see "Amending open plans" below) to point at this plan rather than
reopen separately.

`_tier1_alignment` (tier 1's own gate) is **not** the bug: it already requires a fresh
(`<= ATTACK_RUN_RELATIVE_MAX_AGE_S`, 2.0 s) `Percept.relative_direction`, which is only ever
populated by `naked_eye_source.py`, whose emitting observation already passed
`check_visibility`'s live-DCS terrain-LOS gate (`visibility.py` gate 4, fail-closed). So a tier-1
look is already a genuine sighting. The defect is specifically that the loss/regain *register*
keys on `cause`, a narrower and staler signal, instead of on `tier`.

### F2 design

**Redefine `now_unresolved`/`last_spoken_unresolved` from `cause == "too_far"` to `tier != 1`.**
One-line change to the condition; the `regaining_sight`/`losing_sight` edge-detection shape is
unchanged. This directly implements the user's own words:

> *"if there is no LOS, there is no eyes on. That's the whole meaning of eyes on, that he *sees*
> it."*

`tier == 1` already **is** "has LOS and a fresh look" by construction (see above), including the
documented case where tier 1 persists under a `cause == "too_far"` naked-eye range reading once the
optic ladder (`BL-B71`) has granted a narrower optic — that case is a genuine sighting too, and must
still say "eyes on", which `tier`-keying gets right and `cause`-keying does not.

**The losing-sight wording now branches on the *current* `cause`** — or, after Decision 2 below, the
*effective* cause — since `"too_far"`, `"obstructed"` and `"unknown"` are not the same claim:

| effective cause, on the sighted->unsighted edge | spoken |
|---|---|
| `"too_far"` | unchanged — `render_attack_run_lost_sight`: `"<guidance> <what> <where>, last seen <age> ago."` |
| `"obstructed"` | **new** — `render_attack_run_behind_terrain(phrase)`: `"Behind the ridge, <phrase>."`, once |
| `"unknown"` (and never held, Decision 2) | no new line — falls through to ordinary bare guidance, no qualifier (fail-open stays fail-open; the flag still moves so a later genuine re-sighting still says "eyes on") |
| `"masked"` | unreachable here — `decide()`'s `cause == "masked"` branch returns before this register is ever evaluated (§11: the mask is irrelevant to this register, unchanged) |

### Decision 2 (user, 2026-10-24) — "behind the ridge" is held, not re-decayed

**The gap this closes.** As designed above, the `"unknown"` row is a fail-open: the instant the
fresh LOS-blocked verdict ages past `ATTACK_TARGET_LOS_MAX_AGE_S` (1.5 s), `_no_look_cause` falls
through to `"unknown"` and every trace of "it's behind terrain" is lost — the steady-state qualifier
drops silently back to bare guidance, exactly the staleness mechanism the Root Cause section
diagnoses for F2 itself, just one step removed. The user's own proposal, agreed verbatim: once a
fresh `"obstructed"` verdict has been seen for the target, hold that belief until a genuine tier-1
look proves otherwise — not until the verdict's own freshness window expires.

**Where it lives — `AttackRunState`, not `Contact` or `PositionBelief`.** This is the
ownership-relative channel's own invariant (`body-layer/CLAUDE.md`, "The ownship-relative channel
has exactly two consumers, and neither is a position"): what `attack_run.py` derives from a live
look or its absence reaches exactly two places (the alignment words, and the 9K113 sight goal), and
never writes back into `Contact`/belief position. A "held, terrain-blocked" flag is exactly that
kind of derived, run-local judgment — it belongs beside `last_spoken_unresolved` and
`requested_optic` on `AttackRunState`, not on `Contact`, which must stay a record of what was
actually observed.

**New field**, `AttackRunState.terrain_blocked_held: bool = False` — `decide()`'s own responsibility,
updated on every non-masked tick alongside `requested_optic`:

- `tier == 1` (a genuine live look, this tick) → `terrain_blocked_held = False`, unconditionally. A
  live look is the one thing the user's own words name as ending the hold (*"until a genuine live
  look"*) — it does not matter what `cause` would otherwise say, because tier 1 never reads `cause`
  for wording at all.
- `tier == 2 and cause == "obstructed"` → `terrain_blocked_held = True`. A fresh verdict confirms
  the belief and refreshes the hold.
- Otherwise (`tier == 2`, `cause` is `"too_far"` or `"unknown"`) → unchanged. `"too_far"` is a
  distinct, range-based reason that neither confirms nor contradicts a terrain-blocked belief, so it
  must not clear the hold just because it is the louder reason this tick (`_no_look_cause` checks
  range before LOS, so `"too_far"` can mask a target that is *also* behind terrain — the hold must
  survive that silently, ready to resume once back in range).

**The effective cause** `decide()` and `query()` (F3, below) both use for wording from here on:

```python
effective_cause = (
    "obstructed" if cause == "unknown" and state.terrain_blocked_held else cause
)
```

— substituted for `cause` everywhere F2's design above reads it for *wording* (the losing-sight
table's row selection, and the steady-state qualifier: `tier == 2 and effective_cause ==
"obstructed"` → `", obstructed"`). `cause` itself, unmodified, is still what sets/clears
`terrain_blocked_held` in the bullets above — the override is read-only input to rendering, never
fed back into the flag's own update rule (that would let a held `"obstructed"` perpetuate itself
once `cause` reads `"unknown"`, since `effective_cause` would then read `"obstructed"` too, and the
second bullet above would hold it forever instead of only refreshing it from a genuine fresh
verdict).

**"Behind the ridge, <o'clock>." still speaks exactly once** (F2's own design, unchanged by this
decision) — on the losing-sight edge, using `effective_cause` for the table lookup instead of raw
`cause`. If the edge tick's own `cause` is `"unknown"` and the hold was never set (no blocked
verdict was ever seen for this contact), `effective_cause` stays `"unknown"` too and the edge stays
silent — *"I still get info on where it's believed to be"* (F2's option C) only holds for terrain
Petrovich has actually registered as terrain; a target that simply fades from presence range with
no LOS information at all gets no new claim invented for it.

**Clears on:** a live look (`tier == 1`, above); a target change (`decide()`'s existing
`state.last_contact_id != contact.id` reset constructs a fresh `AttackRunState`, defaulting
`terrain_blocked_held` to `False` for free); run end (`disengage` discards `runner.attack_run_state`
to `None` entirely — `logger.py:3881`, unchanged by this plan); and a mission reset (`BL-15`'s full
state wipe, unchanged). No new clearing logic is needed anywhere but `decide()`'s own per-tick
update rule above — every other "clears on" case is an existing wholesale-discard of
`AttackRunState` that already zeroes a fresh instance's default.

**Interaction with `BL-B76`.** This decision changes nothing about *where* the cause is read from —
still `Contact.live_los_clear` via `_no_look_cause`, still gated exactly as `BL-B76` describes. It
only changes how long a *successfully observed* `"obstructed"` verdict's consequence is remembered
once seen. The "Amending open plans" section below is updated to say so explicitly.

**Risk, revised.** The plan's own Risk below ("the live rate of `obstructed` vs `unknown` ... is
still unmeasured") is **partially mitigated, not closed**: the staleness-decay failure mode this
decision targets — a genuinely blocked verdict observed once, then lost the instant
`ATTACK_TARGET_LOS_MAX_AGE_S` elapses, which is the *exact* mechanism the F2 bug report itself
exhibits one level up — can no longer happen once a verdict is seen even once. What this decision
cannot fix is `BL-B76`'s own open question: whether `Contact.live_los_clear` ever actually reads
`False` in live DCS play at all (per that entry, it is currently reachable only from a test fixture,
since a terrain-blocked candidate is rejected at admission and never updates the stored contact).
If it never fires live, `terrain_blocked_held` has nothing to latch onto and the `"unknown"`
fail-open path still dominates exactly as before — `BL-B76` step 2's mountainous-sortie measurement
is still the thing that answers that, and this decision does not make it less necessary.

**Wording, user direction verbatim, 2026-10-24** (mid-plan correction, addressed before this plan
closed): *"ridge/hill/any terrrain -> 'ridge'."* So the line is **always** `"Behind the ridge,
<o'clock>."` for any terrain-blocked LOS — no terrain-type classification, no world-model terrain
query, regardless of what is actually occluding (ridge, hill, high ground generally). This is not
a decision left open; it is settled and is not to be revisited without new user direction.

**New render function**, `belief/speech.py`:

```python
def render_attack_run_behind_terrain(phrase: str) -> OutgoingSpeech:
    """F2 (2026-10-24 sortie feedback), option C -- "Behind the ridge, <phrase>." on the
    sighted -> `cause == "obstructed"` edge, symmetric with `render_attack_run_regained_sight`.
    "Ridge" is a fixed word for any terrain-blocked LOS, not a terrain-type classification
    (user direction, verbatim, 2026-10-24: "ridge/hill/any terrrain -> 'ridge'")."""
    return OutgoingSpeech(text=f"Behind the ridge, {phrase}.", template="attack_run")
```

**Docstrings to update** (every one currently describes the old `cause`-keyed semantics as if it
were correct): `AttackRunState.last_spoken_unresolved`'s own docstring (~line 237), `NoLookCause`'s
docstring (~line 544, the `"too_far"` bullet's "remembered-sighting transition register" claim),
`decide()`'s own docstring (point 3, ~lines 715-726, and the `now_unresolved`/`regaining_sight`/
`losing_sight` block ~839-859), `render_attack_run_lost_sight`/`render_attack_run_regained_sight`'s
own docstrings (currently say "tier-2 too-far -> tier-1 transition", must say "not-sighted ->
sighted").

### F3 design — "where is it?"

> *"Add command 'where is it?' that gives me an update during an attack run based on A) seeing the
> target B) current belief — use the standard attack run guidance phrase, just trigger it on that
> command. Nothing else needed."*

**Architectural constraint that shapes this**: `CrewConsole` never holds `AttackRunState`, live
`OwnshipState`, or the optic that resolved this poll's percepts — those live on
`logger.ConsolePerceptionRunner` (`runner.attack_run_state`/`runner.last_ownship_state`/
`runner.optic`), by design (`_handle_disengage`'s own docstring: *"the run's own phase lives on the
caller, not here"*). So `_handle_where_is_it` cannot compute or speak the answer synchronously —
the same reason `_handle_engage`/`_handle_disengage` only ever set a one-shot signal for
runner-level effects, except here the signal gates the *entire* readback, not a side effect.

**Reuse the established one-shot-signal pattern** (`attack_run_transition`/`observ_transition`/
`weapon_safety_transition`), not the `_speak_or_defer`/positional-readback pattern — that pattern
defers only for channel-busy timing, and every existing user of it (`select_target`, `report`, ...)
already has everything it needs from `self.store`/`self.enrichment` at render time. This command's
primary input (`AttackRunState`, the optic that resolved this poll) is architecturally unreachable
from `CrewConsole` at all, which is the deciding difference, not merely a preference.

1. **`CrewConsole.where_is_it_requested: bool = False`** — new field, reset at the top of
   `handle_command` alongside `attack_run_transition`/`observ_transition`/
   `weapon_safety_transition` (same block, same reasoning: a stale request from an earlier dispatch
   this poll loop has not yet consumed must not leak into an unrelated later command).
2. **New token `"where_is_it"`**, dispatched to `_handle_where_is_it()`:
   ```python
   def _handle_where_is_it(self) -> list[str]:
       self.where_is_it_requested = True
       return []
   ```
   Add `"where_is_it"` to `DISPATCHED_COMMAND_TOKENS` and to `NO_RETURN_VALUE_COMMAND_TOKENS` (the
   real readback is spoken later, by `drain_where_is_it`, via `self._print` directly — the same
   shape `drain_config_error`/`drain_attack_run` already use to speak from inside a method the
   `logger.py` poll loop calls with runner-level data, not from `handle_command`'s own return).
3. **`attack_run.query(state, *, now_sim, ownship, contact, group=None, resolving_optic=None) ->
   OutgoingSpeech`** — a new pure function, **factored to share `decide()`'s cause/tier/alignment
   computation** (pull the shared block — `_no_look_cause` + `_tier1_alignment`/`_tier2_alignment`
   + table selection + qualifier, **including the `effective_cause` substitution Decision 2 adds**
   — into a private helper `_current_alignment(...)` both `decide` and `query` call, rather than
   duplicating it). `query` never *writes* `state` and returns no new state — a pure read of
   `state.last_known_target_alt_m` (tier 2's remembered altitude) and `state.terrain_blocked_held`
   (Decision 2), so it cannot corrupt `decide`'s own `_should_emit` cadence baseline, the
   `requested_optic` ladder's hysteresis, or the held-terrain flag's own update rule.

   **Decision 1 (user, 2026-10-24) makes `state` answerable without an engaged run.** `query` is
   called whenever the standing target task exists, whether or not `runner.attack_run_state` is
   `None` (see point 4 below) — so it must work with *either* the live, per-contact `AttackRunState`
   an engaged run is carrying, *or* a throwaway `AttackRunState(last_contact_id=contact.id)` the
   caller constructs on the spot when no run is engaged. **The inputs `query` needs, stated
   explicitly** (this is the computability check step 1 of this process asks for): `now_sim`,
   `ownship` (`runner.last_ownship_state` — available regardless of run state, it is ownship
   telemetry), `contact` (resolved from `self.store` via the target task's `contact_id` — available
   regardless of run state, it is belief, not run memory), optionally `group`
   (`self.store.group_for_contact`, tier 2's projection input) and `resolving_optic`
   (`runner.optic`). None of these five come from `AttackRunState` itself — only
   `last_known_target_alt_m` and `terrain_blocked_held` do, and both default to `None`/`False` on a
   throwaway instance, which is exactly correct: no run means no accumulated per-contact memory,
   the same "first tick after `engage`" fail-open posture `_tier2_alignment`'s own elevation-axis
   comment already documents. **Answering never engages or alters the run**: `query`'s own result
   is never assigned to `runner.attack_run_state`, and a throwaway `AttackRunState` constructed for
   an unengaged answer is discarded immediately after the call, never stored anywhere.

   **Always returns speech, never `None`** — including on a masked tick. `cause == "masked"`
   silences *passive* guidance (§2: don't talk over a pilot who hasn't asked anything); an explicit
   question gets an answer either way. On a masked tick, `query` speaks the same bare-guidance
   phrase a `cause == "unknown"` tick would (no qualifier) — azimuth/elevation are already computed
   from `contact.last_position`/`Group.heading_deg` independent of the mask, so this is still "B)
   current belief," not an invented sentence.

   Deliberately **no transition wording** (`"Eyes on"` / `"last seen ... ago"` / `"Behind the
   ridge"`) — those describe *what just changed*, and this is a point-in-time query that may land
   well after any transition. `query` renders exactly what `decide()`'s steady-state (`else`)
   branch would: bare alignment phrase, `", obstructed"` qualifier for `tier == 2 and
   effective_cause == "obstructed"` (Decision 2's held flag included), nothing for
   `"too_far"`/`"unknown"` (same fail-open posture F2 settles above).

4. **`CrewConsole.drain_where_is_it(attack_run_state, now_sim, ownship, *, resolving_optic=None) ->
   list[str]`** — called from `logger.py`'s poll loop, right beside the existing `drain_attack_run`
   call (same `runner.attack_run_state`/`runner.last_ownship_state`/`runner.optic` already in
   scope there), consuming `self.where_is_it_requested` the same way the three existing one-shot
   signals are consumed (read, act, set back to `False`). **Revised for Decision 1**: the gate is
   "is a target selected," not "is a run engaged" — `attack_run_state is None` (disengaged, or never
   engaged) no longer refuses on its own:
   ```python
   def drain_where_is_it(
       self, attack_run_state, now_sim, ownship, *, resolving_optic=None
   ) -> list[str]:
       target_task = self._active_attack_target_task()
       if target_task is None or target_task.contact_id is None:
           lines = [render_no_target().text]
           self._print(lines, now_sim)
           return lines
       contact = self.store.contact(target_task.contact_id)
       if contact is None:
           lines = [render_lost_contact().text]
           self._print(lines, now_sim)
           return lines
       group = self.store.group_for_contact(contact.id)
       # Decision 1: answer whether or not a run is engaged. An engaged run's own
       # per-contact memory (held-terrain flag, remembered tier-2 altitude) is reused
       # when present; an unengaged query gets a throwaway, memoryless state -- the
       # same fail-open posture a brand-new `engage` would start from.
       state = (
           attack_run_state
           if attack_run_state is not None
           else AttackRunState(last_contact_id=contact.id)
       )
       speech = query_attack_run(
           state, now_sim=now_sim, ownship=ownship, contact=contact,
           group=group, resolving_optic=resolving_optic,
       )
       lines = [speech.text]
       self._print(lines, now_sim)
       return lines
   ```
   **"No target" (user's exact wording) replaces `"Unable, no attack run."` outright** — this is
   not the existing "say again"/"unable" distinction (the command was heard and understood; there
   is simply nothing to report on), so it gets its own render function rather than a new
   `_UNABLE_TEMPLATES` entry: `speech.py` gains `render_no_target() -> OutgoingSpeech`, returning
   `OutgoingSpeech(text="No target.", template="readback")`. The `"NO_ATTACK_RUN"`/`"Unable, no
   attack run."` template this plan originally proposed is **dropped entirely** — nothing else in
   this plan referenced it.
5. **Not gated by `_LOOK_COMMAND_TOKENS`/on-ground** — consistent with `engage`/`disengage`, which
   carry no on-ground gate either; an attack run cannot exist while on the ground in practice (no
   engage without airborne perception), so this mirrors existing precedent rather than inventing a
   new gate.
6. **Decision 3 (user, 2026-10-24): voice only.** User: *"voice only"*. This supersedes the
   default originally stated here ("Voice phrase + typed console only, no new F10 item"): no F10
   item (unchanged — already the default), **and no typed-console path either**. Concretely: the
   `"where_is_it"` token is recognised **only** via `audio-adapter`'s command matcher reaching
   `CrewConsole.handle_transcript` (the dedicated voice-command entry point, `plans/
   inbound-speech/plan.md` Stage 2) — not via `handle_line`'s typed-REPL surface (`_run_crew_text_
   repl`/`--crew-text`'s stdin loop), which parses free text through the narrower `_handle_utterance`/
   `parse_utterance` contact-reference grammar (`set_attention`/`describe_contact` only) and the
   separate `_match_radio_check_or_greeting` special case — neither of which this plan touches or
   extends to recognise "where is it" as literal typed text. `DISPATCHED_COMMAND_TOKENS`/
   `NO_RETURN_VALUE_COMMAND_TOKENS` membership (point 2 above) is still required — those sets also
   gate the brain-reply confirm-band path (`validate_brain_reply`), which this plan does not
   exclude, since the user's "voice only" answered the command-*surface* question (how the pilot
   issues it), not whether a confirm-band "yes" can commit it once voice itself has proposed it.
   `!voice where is it` in the dev REPL remains available as a test harness for the voice path
   itself (it simulates `handle_transcript`, not a second surface) — unaffected either way.
7. **Redraw the voice-command map** (`.claude/skills/command-map`) once the new phrase/token lands
   — explicit step, not a side effect to remember later.

### Co-moving Fields

Step 6a's trigger (a phase/mode state machine with >1 co-moving field, at least one externally
written) does **not** fire here. `AttackRunState`'s fields are all written by `decide()` alone, not
split between an external writer and internal logic the way `phase`/`home_phase` were; `_no_look_
cause` → `now_unresolved` is a redefinition of one field's *meaning*, not the introduction of a
second field tracking the same thing. `where_is_it_requested` is a single new one-shot flag, the
same shape as the three it sits beside, not a second co-moving phase field. **Decision 2's new
`terrain_blocked_held` field is also internal-only** — written exclusively by `decide()`'s own
per-tick update rule, read (never written) by `query()` — so it does not change this conclusion
either. Grepped every `AttackRunState(` construction site (`logger.py:3878`, `attack_run.py:769`,
plus tests, **plus `drain_where_is_it`'s own new throwaway-state construction, Decision 1**) — all
three default `terrain_blocked_held` to `False` for free (a plain dataclass field default, same as
every other field here), so no construction site needs an explicit update for this plan.

### Affected Modules / Files

- `body-layer/src/belief/attack_run.py` — redefine `now_unresolved`/`last_spoken_unresolved`
  (`tier != 1`, not `cause == "too_far"`); add `AttackRunState.terrain_blocked_held: bool = False`
  and its per-tick update rule (Decision 2); branch the losing-sight render and the steady-state
  qualifier on `effective_cause`, not raw `cause`; factor `_current_alignment` out of `decide()`
  and add `query()` reusing it (now including the `effective_cause` substitution); update the
  docstrings named above.
- `body-layer/src/belief/speech.py` — new `render_attack_run_behind_terrain`; new
  `render_no_target() -> OutgoingSpeech` (`"No target."`, Decision 1 — **not** a
  `_UNABLE_TEMPLATES` entry); update `render_attack_run_lost_sight`/`render_attack_run_regained_
  sight` docstrings. The `"NO_ATTACK_RUN"` template this plan originally proposed is dropped.
- `body-layer/src/belief/crew_console.py` — `where_is_it_requested` field + its reset;
  `_handle_where_is_it`; `"where_is_it"` in `DISPATCHED_COMMAND_TOKENS` and
  `NO_RETURN_VALUE_COMMAND_TOKENS`; `drain_where_is_it` (Decision 1's "target set, not run engaged"
  gate, and the throwaway-`AttackRunState` construction for the unengaged case).
- `body-layer/src/logger.py` — call `crew_console.drain_where_is_it(...)` from the poll loop,
  beside the existing `drain_attack_run` call, consuming/clearing `where_is_it_requested`.
- `audio-adapter/src/vocabulary.py` (or wherever the command phrase table lives) — recognise
  "where is it" (and reasonable variants — "where is the target", "where is it now") as the
  `where_is_it` token, reached **only** through the voice-transcript path (Decision 3 — no
  typed-console special-casing in `crew_console.py`'s `handle_line`/`_handle_utterance`/
  `_match_radio_check_or_greeting`, none of which this plan touches). **Not yet inspected by this
  plan** — Implementer should read that file's existing phrase-table shape before adding the entry;
  out of scope for this plan to pre-design.
- `.claude/skills/command-map` — redraw after the vocabulary change.
- `body-layer/ROADMAP/BL-B76.md` — amend (see below): this plan answers BL-B76's open step 3, and
  Decision 2 adds a further note on what the held flag does and does not mitigate.

### Implementation Plan

1. **F2, minimal fix first.** Redefine `now_unresolved` to `tier != 1` in `decide()`. Run the
   existing `test_attack_run.py` suite — this alone should not break any passing test (every
   existing test that exercises `regaining_sight`/`losing_sight` does so via genuine tier-1/tier-2
   transitions, per the module's own cause-taxonomy test coverage note), but confirm rather than
   assume.
2. **F2, cause-keyed wording.** Add `render_attack_run_behind_terrain`; branch the losing-sight
   render three ways (`too_far`/`obstructed`/`unknown`) as specified above.
3. **Decision 2, the held flag.** Add `AttackRunState.terrain_blocked_held`; the per-tick update
   rule (`tier == 1` clears, `tier == 2 and cause == "obstructed"` sets, otherwise unchanged); the
   `effective_cause` substitution used by the losing-sight table lookup and the steady-state
   qualifier. Done alongside step 2 (both touch the same cause-dispatch code), not as a separate
   pass — splitting them would mean writing the qualifier logic once on raw `cause` and then
   immediately rewriting it onto `effective_cause`.
4. **F2/Decision 2 tests** (`test_attack_run.py`), each failing under a named mutation (matching
   this module's existing mutation-tested style):
   - Sighted (tier 1) -> masked -> cause falls to `"unknown"` on unmask (simulate via stale
     `last_seen_sim`) -> **no** "Eyes on" fires; ordinary bare guidance instead. (The exact F2
     reproduction — this is the test that would have caught the reported bug.)
   - Sighted (tier 1) -> masked -> cause is `"obstructed"` (fresh `live_los_clear=False`) on
     unmask -> `"Behind the ridge, <phrase>."` fires once; steady renders drop it;
     `terrain_blocked_held` is `True` afterward.
   - Sighted (tier 1) -> cause `"too_far"` on next tick, tier still 2 -> existing full
     remembered-sighting claim unchanged (regression guard: F2's fix must not touch the `too_far`
     wording).
   - Tier 1 persists while `cause == "too_far"` (optic-ladder case, `BL-B71`) -> no transition at
     all (steady sighted throughout) -- confirms `tier`-keying, not `cause`-keying, decides this.
   - **Decision 2's own case**: `"obstructed"` observed once (held set `True`) -> next several
     ticks' `cause` reads `"unknown"` (verdict aged past `ATTACK_TARGET_LOS_MAX_AGE_S`) -> steady
     render still carries `", obstructed"`, not bare guidance -- the exact staleness-decay failure
     this decision targets. Mutation: dropping the `effective_cause` substitution (reverting to raw
     `cause` in the qualifier/table lookup) must fail this test.
   - **Held clears on a live look**: continuing the above, a tier-1 tick arrives (fresh relative
     observation) -> `terrain_blocked_held` is `False` immediately after, and a *subsequent*
     `"unknown"` tick (after losing tier 1 again, with no fresh `"obstructed"` verdict since) gets
     bare guidance, not `", obstructed"` -- proves the hold does not survive a live look.
   - **Held clears on target change**: `state.last_contact_id != contact.id` resets to a fresh
     `AttackRunState` -> `terrain_blocked_held` is `False` for the new contact even though it was
     `True` for the old one.
   - Mutation: reverting `tier != 1` to `cause == "too_far"` must fail at least the first new test.
5. **F3, the query path.** Factor `_current_alignment` out of `decide()`; add `query()`, including
   the `effective_cause` substitution from step 3.
6. **F3, the command surface.** `where_is_it_requested` field + reset, `_handle_where_is_it`,
   token-set membership, `drain_where_is_it` (Decision 1's gate: target set, not run engaged; the
   throwaway-`AttackRunState` construction for the unengaged branch), `render_no_target` in
   `speech.py`.
7. **F3 tests**:
   - `test_attack_run.py`: `query()` returns the steady-state phrase for each of the four effective
     causes (bare for `too_far`/`unknown`/`masked`, `", obstructed"`-qualified for `obstructed` and
     for `"unknown"`-while-held per Decision 2), and never mutates the `AttackRunState` passed in
     (identity/equality check against the input).
   - `test_crew_console.py`: `where_is_it` with no target selected -> `render_no_target()`
     (`"No target."`); with a target selected but **no engaged run** -> answers the guidance phrase
     from a throwaway state (Decision 1's own reproduction — this is the test that would have
     caught "Unable, no attack run." firing when the user asked for an answer); with an engaged run
     -> `where_is_it_requested` set, empty immediate return, and the subsequent `drain_where_is_it`
     call reuses the *live* `AttackRunState` (not a throwaway) — assert by giving it a non-default
     `terrain_blocked_held=True` and confirming the qualifier reflects it, which a throwaway
     construction would not.
   - `test_logger.py`: the poll-loop wiring — `where_is_it_requested=True` with
     `runner.attack_run_state` set produces exactly one spoken line via `drain_where_is_it`, and
     the flag clears afterward so it does not re-fire on the next poll; repeat with
     `runner.attack_run_state is None` (Decision 1) and confirm it still speaks, not "No target.",
     as long as a target is selected.
8. **Vocabulary + command-map.** Add the phrase to audio-adapter's command matcher, reached only
   via `handle_transcript` (Decision 3 — no change to `handle_line`/`_handle_utterance`); run
   `.claude/skills/command-map` to redraw the published map.
9. **Full verification.** `ruff format`/`ruff check`, `cd body-layer && .venv/bin/mypy src`,
   `pytest body-layer/tests -q`; same for `audio-adapter` if its vocabulary file changed.
10. **Acceptance flight.** Needs a mountainous theatre (same requirement BL-B76 step 2 already
   named — flat desert barely exercises terrain LOS). Card:
   - Select and engage a target, get a genuine tier-1 "eyes on" or ordinary guidance tick.
   - Fly behind a ridge/hill long enough (>1.5–2 s) that the mask clears before terrain LOS does —
     expect **no** "Eyes on" on unmask; expect **"Behind the ridge, <o'clock>."** once if a fresh
     terrain-blocked verdict exists, otherwise silence/ordinary guidance (the `"unknown"` fail-open
     case) — note which one actually fires, since the live rate of `"obstructed"` vs `"unknown"`
     for this exact scenario is still an open measurement (`BL-B76` step 2). **If "Behind the
     ridge" does fire**, stay behind the ridge well past 1.5–2 s and confirm the guidance keeps the
     obstructed qualifier rather than going bare — the live test of Decision 2's held flag.
   - Say "where is it?" at least once while masked/obstructed and once while genuinely sighted;
     confirm it answers with the standard guidance phrase both times and never says "Eyes on"/
     "Behind the ridge" on demand (those stay transition-only).
   - Disengage (`"disengage"`/`"stop attack"`) with the target still selected, then say "where is
     it?" — expect the standard guidance phrase, not "No target." and not a refusal (Decision 1).
   - Drop the target entirely (`"drop target"`), then say "where is it?" — expect "No target."

### Risks & Unknowns

- **The live rate of `"obstructed"` vs `"unknown"` for a genuinely terrain-blocked target is still
  unmeasured** (`BL-B76` step 2, not yet flown mountainous as of this plan). **Decision 2 narrows
  but does not close this risk.** It fixes the exact staleness-decay mechanism the F2 bug itself
  exhibits one level up — a verdict observed once, then lost the instant its freshness window
  elapses — so once `"obstructed"` fires even a single time for a given occlusion, the belief now
  survives for as long as the occlusion itself lasts. What it cannot fix is whether `"obstructed"`
  ever fires at all: per `BL-B76`, a terrain-blocked candidate is rejected at admission and never
  updates the stored contact, so in live play as of that entry `Contact.live_los_clear` is only
  ever `False` in a test fixture. If that holds on the next sortie too, "Behind the ridge" is still
  rarely or never heard, and most long occlusions still fall into the silent `"unknown"` fail-open
  path — not because the hold failed, but because it never had anything to latch onto. Worth saying
  up front so that is not mistaken for a new bug, and so a quiet acceptance flight is read as
  "BL-B76 step 2's question, still open" rather than "Decision 2 didn't work."
- **`resolving_optic` is not threaded through `where_is_it`'s one-shot signal beyond what `logger.py`
  already has in scope at the `drain_attack_run` call site** (`runner.optic`) — minor precision
  risk only (affects `_no_look_cause`'s range gate), same input `drain_attack_run` itself uses, so
  no new inconsistency is introduced.
- **Audio-adapter's exact phrase-matching mechanics are out of this plan's scope** — the
  Implementer should read `audio-adapter/src/command_matcher.py`/`vocabulary.py` before adding the
  phrase; this plan does not pre-design the fuzzy-match entry.

### Decisions Requiring User Input

None outstanding. The one open fork this plan originally carried (F3's command surface: voice +
typed console, or also a static F10 item?) is closed by Decision 3 above — *"voice only"* — which
answered more than was asked (no typed-console either, not only no F10).

### Amending open plans

**`body-layer/ROADMAP/BL-B76.md` Decision/step 3** ("decide whether the attack run should read the
live gate outcome rather than the stored contact") is answered by this plan's F2 fix, but narrower
than that step framed it: the fix does not change *where* the cause is read from (still
`Contact.live_los_clear` via `_no_look_cause`, unchanged) — it changes what the loss/regain
*register* keys on (`tier`, not `cause`). **Decision 2 adds a second, related note**: it extends how
long an *observed* `"obstructed"` verdict's consequence is remembered, but does not touch where the
verdict comes from either, and does not change BL-B76's own open question of whether that verdict
is ever reachable in live play at all (step 2's unmeasured rate; see the Risks section above, as
revised). BL-B76 should be amended in place (not closed) once this plan merges: add a dated note
pointing at `plans/attack-run-los/plan.md` as resolving the register half of step 3 and adding the
held-flag mitigation, and leave step 2's live-rate measurement (mountainous sortie) open, since this
plan's own acceptance flight (above) is the first opportunity to take that measurement but does not
guarantee it lands.
