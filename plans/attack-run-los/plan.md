# Attack-run LOS: "eyes on" means line of sight (F2), and "where is it?" (F3)

Source: `docs/acceptance/2026-10-24-sortie-feedback.md` F2 and F3, explored with the user the same
day. Branch: `feature/attack-run-los`.

### Goal

Fix the attack-run "eyes on"/"lost sight" register so it never claims a sighting the crewman does
not actually have (F2), and add a "where is it?" command that speaks the standard attack-run
guidance phrase on demand, based on current sight/belief (F3).

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

**The losing-sight wording now branches on the *current* `cause`**, since `"too_far"`,
`"obstructed"` and `"unknown"` are not the same claim:

| current cause, on the sighted->unsighted edge | spoken |
|---|---|
| `"too_far"` | unchanged — `render_attack_run_lost_sight`: `"<guidance> <what> <where>, last seen <age> ago."` |
| `"obstructed"` | **new** — `render_attack_run_behind_terrain(phrase)`: `"Behind the ridge, <phrase>."`, once |
| `"unknown"` | **unchanged posture, `BL-B76`'s existing direction**: no new line — falls through to ordinary bare guidance, no qualifier (fail-open stays fail-open; the flag still moves so a later genuine re-sighting still says "eyes on") |
| `"masked"` | unreachable here — `decide()`'s `cause == "masked"` branch returns before this register is ever evaluated (§11: the mask is irrelevant to this register, unchanged) |

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
   + table selection + qualifier — into a private helper `_current_alignment(...)` both `decide`
   and `query` call, rather than duplicating it). `query` never touches `state` and returns no new
   state — a pure read, so it cannot corrupt `decide`'s own `_should_emit` cadence baseline or the
   `requested_optic` ladder's hysteresis.

   **Always returns speech, never `None`** — including on a masked tick. `cause == "masked"`
   silences *passive* guidance (§2: don't talk over a pilot who hasn't asked anything); an explicit
   question gets an answer either way. On a masked tick, `query` speaks the same bare-guidance
   phrase a `cause == "unknown"` tick would (no qualifier) — azimuth/elevation are already computed
   from `contact.last_position`/`Group.heading_deg` independent of the mask, so this is still "B)
   current belief," not an invented sentence.

   Deliberately **no transition wording** (`"Eyes on"` / `"last seen ... ago"` / `"Behind the
   ridge"`) — those describe *what just changed*, and this is a point-in-time query that may land
   well after any transition. `query` renders exactly what `decide()`'s steady-state (`else`)
   branch would: bare alignment phrase, `", obstructed"` qualifier only for `tier == 2 and cause ==
   "obstructed"`, nothing for `"too_far"`/`"unknown"` (same fail-open posture F2 settles above).

4. **`CrewConsole.drain_where_is_it(attack_run_state, now_sim, ownship, *, resolving_optic=None) ->
   list[str]`** — called from `logger.py`'s poll loop, right beside the existing `drain_attack_run`
   call (same `runner.attack_run_state`/`runner.last_ownship_state`/`runner.optic` already in
   scope there), consuming `self.where_is_it_requested` the same way the three existing one-shot
   signals are consumed (read, act, set back to `False`):
   ```python
   def drain_where_is_it(
       self, attack_run_state, now_sim, ownship, *, resolving_optic=None
   ) -> list[str]:
       target_task = self._active_attack_target_task()
       if attack_run_state is None or target_task is None or target_task.contact_id is None:
           lines = [render_unable("NO_ATTACK_RUN").text]
           self._print(lines, now_sim)
           return lines
       contact = self.store.contact(target_task.contact_id)
       if contact is None:
           lines = [render_lost_contact().text]
           self._print(lines, now_sim)
           return lines
       group = self.store.group_for_contact(contact.id)
       speech = query_attack_run(
           attack_run_state, now_sim=now_sim, ownship=ownship, contact=contact,
           group=group, resolving_optic=resolving_optic,
       )
       lines = [speech.text]
       self._print(lines, now_sim)
       return lines
   ```
   `attack_run_state is None` (no engaged run) and "no target selected" both answer
   `render_unable("NO_ATTACK_RUN")` — add `"NO_ATTACK_RUN": "Unable, no attack run."` to
   `speech.py`'s `_UNABLE_TEMPLATES`. This is the "say again" vs "unable" distinction already in
   force elsewhere in this file: the command was heard and understood, the action just isn't
   available right now.
5. **Not gated by `_LOOK_COMMAND_TOKENS`/on-ground** — consistent with `engage`/`disengage`, which
   carry no on-ground gate either; an attack run cannot exist while on the ground in practice (no
   engage without airborne perception), so this mirrors existing precedent rather than inventing a
   new gate.
6. **Voice phrase + typed console only, no new F10 item**, by default — the F10 menu is explicitly
   the retiring transport (root `CLAUDE.md`: *"voice is primary... F10 menu 'may go stale'"*) and
   this is a one-shot flat command with no slots, so the marginal cost of an F10 item is small but
   the user said "nothing else needed." Flagged under Decisions below rather than assumed silently,
   since it is a real (if cheap) fork.
7. **Redraw the voice-command map** (`.claude/skills/command-map`) once the new phrase/token lands
   — explicit step, not a side effect to remember later.

### Co-moving Fields

Step 6a's trigger (a phase/mode state machine with >1 co-moving field, at least one externally
written) does **not** fire here. `AttackRunState`'s fields are all written by `decide()` alone, not
split between an external writer and internal logic the way `phase`/`home_phase` were; `_no_look_
cause` → `now_unresolved` is a redefinition of one field's *meaning*, not the introduction of a
second field tracking the same thing. `where_is_it_requested` is a single new one-shot flag, the
same shape as the three it sits beside, not a second co-moving phase field. Grepped every
`AttackRunState(` construction site (`logger.py:3878`, `attack_run.py:769`, plus tests) — both
production sites already covered above; neither needs a change for this plan.

### Affected Modules / Files

- `body-layer/src/belief/attack_run.py` — redefine `now_unresolved`/`last_spoken_unresolved`
  (`tier != 1`, not `cause == "too_far"`); branch the losing-sight render on `cause`; factor
  `_current_alignment` out of `decide()` and add `query()` reusing it; update the docstrings named
  above.
- `body-layer/src/belief/speech.py` — new `render_attack_run_behind_terrain`; update
  `render_attack_run_lost_sight`/`render_attack_run_regained_sight` docstrings; add
  `"NO_ATTACK_RUN"` to `_UNABLE_TEMPLATES`.
- `body-layer/src/belief/crew_console.py` — `where_is_it_requested` field + its reset;
  `_handle_where_is_it`; `"where_is_it"` in `DISPATCHED_COMMAND_TOKENS` and
  `NO_RETURN_VALUE_COMMAND_TOKENS`; `drain_where_is_it`.
- `body-layer/src/logger.py` — call `crew_console.drain_where_is_it(...)` from the poll loop,
  beside the existing `drain_attack_run` call, consuming/clearing `where_is_it_requested`.
- `audio-adapter/src/vocabulary.py` (or wherever the command phrase table lives) — recognise
  "where is it" (and reasonable variants — "where is the target", "where is it now") as the
  `where_is_it` token. **Not yet inspected by this plan** — Implementer should read that file's
  existing phrase-table shape before adding the entry; out of scope for this plan to pre-design.
- `.claude/skills/command-map` — redraw after the vocabulary change.
- `body-layer/ROADMAP/BL-B76.md` — amend (see below): this plan answers BL-B76's open step 3.

### Implementation Plan

1. **F2, minimal fix first.** Redefine `now_unresolved` to `tier != 1` in `decide()`. Run the
   existing `test_attack_run.py` suite — this alone should not break any passing test (every
   existing test that exercises `regaining_sight`/`losing_sight` does so via genuine tier-1/tier-2
   transitions, per the module's own cause-taxonomy test coverage note), but confirm rather than
   assume.
2. **F2, cause-keyed wording.** Add `render_attack_run_behind_terrain`; branch the losing-sight
   render three ways (`too_far`/`obstructed`/`unknown`) as specified above.
3. **F2 tests** (`test_attack_run.py`), each failing under a named mutation (matching this module's
   existing mutation-tested style):
   - Sighted (tier 1) -> masked -> cause falls to `"unknown"` on unmask (simulate via stale
     `last_seen_sim`) -> **no** "Eyes on" fires; ordinary bare guidance instead. (The exact F2
     reproduction — this is the test that would have caught the reported bug.)
   - Sighted (tier 1) -> masked -> cause is `"obstructed"` (fresh `live_los_clear=False`) on
     unmask -> `"Behind the ridge, <phrase>."` fires once; steady renders drop it.
   - Sighted (tier 1) -> cause `"too_far"` on next tick, tier still 2 -> existing full
     remembered-sighting claim unchanged (regression guard: F2's fix must not touch the `too_far`
     wording).
   - Tier 1 persists while `cause == "too_far"` (optic-ladder case, `BL-B71`) -> no transition at
     all (steady sighted throughout) -- confirms `tier`-keying, not `cause`-keying, decides this.
   - Mutation: reverting `tier != 1` to `cause == "too_far"` must fail at least the first new test.
4. **F3, the query path.** Factor `_current_alignment` out of `decide()`; add `query()`; add
   `render_attack_run_behind_terrain`-adjacent plumbing is already covered above — add
   `_UNABLE_TEMPLATES["NO_ATTACK_RUN"]`.
5. **F3, the command surface.** `where_is_it_requested` field + reset, `_handle_where_is_it`,
   token-set membership, `drain_where_is_it`, the `logger.py` poll-loop call site.
6. **F3 tests**:
   - `test_attack_run.py`: `query()` returns the steady-state phrase for each of the four causes
     (bare for `too_far`/`unknown`/`masked`, `", obstructed"`-qualified for `obstructed`), and
     never mutates the `AttackRunState` passed in (identity/equality check against the input).
   - `test_crew_console.py`: `where_is_it` with no engaged run -> `render_unable("NO_ATTACK_RUN")`;
     with an engaged run -> `where_is_it_requested` set, empty immediate return.
   - `test_logger.py`: the poll-loop wiring — `where_is_it_requested=True` with
     `runner.attack_run_state` set produces exactly one spoken line via `drain_where_is_it`, and
     the flag clears afterward so it does not re-fire on the next poll.
7. **Vocabulary + command-map.** Add the phrase to audio-adapter's command matcher; run
   `.claude/skills/command-map` to redraw the published map.
8. **Full verification.** `ruff format`/`ruff check`, `cd body-layer && .venv/bin/mypy src`,
   `pytest body-layer/tests -q`; same for `audio-adapter` if its vocabulary file changed.
9. **Acceptance flight.** Needs a mountainous theatre (same requirement BL-B76 step 2 already
   named — flat desert barely exercises terrain LOS). Card:
   - Select and engage a target, get a genuine tier-1 "eyes on" or ordinary guidance tick.
   - Fly behind a ridge/hill long enough (>1.5–2 s) that the mask clears before terrain LOS does —
     expect **no** "Eyes on" on unmask; expect **"Behind the ridge, <o'clock>."** once if a fresh
     terrain-blocked verdict exists, otherwise silence/ordinary guidance (the `"unknown"` fail-open
     case) — note which one actually fires, since the live rate of `"obstructed"` vs `"unknown"`
     for this exact scenario is still an open measurement (`BL-B76` step 2).
   - Say "where is it?" at least once while masked/obstructed and once while genuinely sighted;
     confirm it answers with the standard guidance phrase both times and never says "Eyes on"/
     "Behind the ridge" on demand (those stay transition-only).
   - Say "where is it?" with no attack run engaged; expect "Unable, no attack run."

### Risks & Unknowns

- **The live rate of `"obstructed"` vs `"unknown"` for a genuinely terrain-blocked target is still
  unmeasured** (`BL-B76` step 2, not yet flown mountainous as of this plan). If `"obstructed"`
  almost never fires in practice (verdict goes stale before the mask clears, same as this exact F2
  case), the new "Behind the ridge" line may rarely be heard, and most long occlusions will
  continue to fall into the silent `"unknown"` fail-open path. That is a known, accepted gap per
  BL-B76's existing direction, not a defect this plan introduces — but it means F2's fix may read,
  on the next sortie, as "no more false 'eyes on', but also no 'behind the ridge' either." Worth
  saying up front so that is not mistaken for a new bug.
- **`resolving_optic` is not threaded through `where_is_it`'s one-shot signal beyond what `logger.py`
  already has in scope at the `drain_attack_run` call site** (`runner.optic`) — minor precision
  risk only (affects `_no_look_cause`'s range gate), same input `drain_attack_run` itself uses, so
  no new inconsistency is introduced.
- **Audio-adapter's exact phrase-matching mechanics are out of this plan's scope** — the
  Implementer should read `audio-adapter/src/command_matcher.py`/`vocabulary.py` before adding the
  phrase; this plan does not pre-design the fuzzy-match entry.

### Decisions Requiring User Input

- **F3's command surface: voice + typed console only, or also a static F10 item?** Default taken
  above is voice/console-only (no F10 item), per "nothing else needed" and the F10 menu's retiring
  status. A static F10 item (not a dynamic list — same cheap shape as "Cancel Task") would cost
  little if wanted; say so if preferred.

### Amending open plans

**`body-layer/ROADMAP/BL-B76.md` Decision/step 3** ("decide whether the attack run should read the
live gate outcome rather than the stored contact") is answered by this plan's F2 fix, but narrower
than that step framed it: the fix does not change *where* the cause is read from (still
`Contact.live_los_clear` via `_no_look_cause`, unchanged) — it changes what the loss/regain
*register* keys on (`tier`, not `cause`). BL-B76 should be amended in place (not closed) once this
plan merges: add a dated note pointing at `plans/attack-run-los/plan.md` as resolving the register
half of step 3, and leave step 2's live-rate measurement (mountainous sortie) open, since this
plan's own acceptance flight (above) is the first opportunity to take that measurement but does not
guarantee it lands.
