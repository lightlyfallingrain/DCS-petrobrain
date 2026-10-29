# BL-14 — Attack run: target selection, step-adjust, alignment guidance, end conditions

> **Amended 2026-10-14, second Architect pass.** Six further user decisions landed after the first
> pass reported (`docs/acceptance/2026-10-14-attack-run-guidance-direction.md` §15–§18). The
> consequential one is **§18**: guidance consumes a *new* perception datum — an ownship-relative
> observation — rather than the world-anchored `PositionBelief` this plan was written against. That
> moved the stage boundaries, so Stages 2–7 are renumbered. §17 **supersedes Decision 4's remedy**
> (no world-model elevation query, no cache, no `BL-B49` enrichment risk) while leaving its finding
> standing, and settles the elevation open decision against the discrimination test. §15 and §16
> settle what were open decisions 2 and 3. Superseded text is kept in place with a forward pointer,
> per `docs/PROCESS.md` "Superseding a decision" — it is why the revisions make sense.

> **Amended 2026-10-14, third Architect pass (small).** §19–§21 of the same direction document
> settle the two items the second pass had left open as Decisions A and B, plus a scoping note.
> **§19** settles A, but not as recommended: tier 2 speaks a qualifier (`"right, obstructed"`) in
> its own words rather than a withheld row inside tier 1's vocabulary, and the sticky lined-up band
> the recommendation asked for is struck as no longer needed — see Decision 17 REVISED, which also
> makes Stage 6 cockpit-observable rather than log-only. **§20** settles B as planned, confirming
> `RELATIVE_DIRECTION_SIGMA_DEG = 0.0` — see Decision 16 item 5. **§21** adds three reasons the
> re-rotation design (Decision 16) is right beyond the 9.2°/s figure already in this plan. The
> third reached a different subproject and was itself reshaped by a second round of direction the
> same day: not a general telemetry/world-objects rate split, but a selective fast lane carrying
> only ownship telemetry and the currently-selected target, scoped to a run and framed as a
> reusable seam for the deferred 9K113 missile-guidance work too. Filed as a correction on
> `aircraft-layer/ROADMAP/AC-B3.md` and a rewritten `body-layer/ROADMAP/BL-B63.md` — filed, not
> built, no stage boundary in this plan moves, and the stale pre-`BL-11` performance figures that
> had briefly argued the fast lane was impossible are corrected in place rather than carried
> forward.

### Goal

Give the pilot a commanded attack-run mode in which Petrovich holds one selected unit, lets the
pilot correct the selection by stepping angularly around the current line of sight, and speaks
qualitative azimuth/vertical **alignment** corrections — silent while the nose is on the target —
ending only on the pilot's command.

---

## 0. Which document wins, and what today's direction reverses

`docs/acceptance/2026-10-14-attack-run-guidance-direction.md` is the specification. It is **later
than and reverses** parts of three earlier documents that are otherwise still in force. Stating the
reversals explicitly, because each one would otherwise be re-derived from a document that still
reads as current:

| earlier document | what still stands | what today's direction **reverses** |
|---|---|---|
| `docs/concept/Attacking target.md` (2026-10-11) | the whole command **grammar**: `select target`, `step [n] left/right/near/far`, `drop target`, `engage`, `disengage`, the end conditions | the **guidance register**. "N degrees down", the range countdown, signed degrees, `"missed, aim higher"`, `"target smoking / on fire / destroyed"`, and the automatic stop on destruction are all out (§1, §12, §13) |
| `plans/brain-layer/explore-notes.md` §"Attack run (2026-09-24)" | the **two-loop split** — the brain resolves the target once, everything after is deterministic geometry and never a model; and the advisory-channel carve-out (advisory is allowed *because* the pilot requested this manoeuvre) | the **callout table** in that section, entirely |
| `docs/acceptance/2026-10-13-group-model-and-attention-tiers.md` Part 1 | the attention tiers as a concept; the ATGM/9K113-channel split; "being wrong depends on LOS" | *"step right walks the world, not the belief store"*. Today: **it walks the belief store** (§3), so `BL-14` is **not** gated on the unbuilt attention-driven per-unit resolution mechanism for its stepping half |

Also load-bearing, and **not yet built**:
`docs/acceptance/2026-10-13-position-uncertainty-direction.md` (movement-keyed uncertainty) is
captured direction awaiting its own entry. §7 of today's direction — *"last known if stopped,
projected if moving"* — therefore has no existing machinery to lean on. See Decision 10.

**What the direction document's own later sections reverse *inside this plan*** (added in the
2026-10-14 amendment pass, so a reader of one section does not act on a superseded one):

| direction § | what it changes here |
|---|---|
| **§18** | Guidance derives from a **new ownship-relative observation**, not from `Contact.last_position`. New Decisions **16** and **17**; new Stage 2; the cluster-bias risk is re-footed as a *reporting* risk |
| **§17** | Decision **4 REVISED** — the target's own altitude arrives with the unit, so **no world-model elevation query, no cache, no `BL-B49` enrichment-path risk**. Both axes are **one** derivation (Decision **3a**). Open decision 1 is **closed against** the discrimination test. "Fine-grained by parameter alone" becomes a structural rule (Decision **11 REVISED**) |
| **§16** | Open decision 3 is **settled: yes, no exemption.** Decision 8 stands as written |
| **§15** | Open decision 2 is **settled: yes, the run claims the gaze.** Decision 9's "gated on the user's answer" is gone, and the gaze claim moves **into** the wiring stage rather than trailing it |

---

### Affected Modules / Files

**New**

- `body-layer/src/belief/attack_run.py` — the run's frozen state (`AttackRunState`), the per-tick
  alignment derivation, the angular ordering used by `step`, and a pure `decide()`. Pure functions
  plus one frozen dataclass; no I/O beyond the world-model connection handed in.
  *Why its own module:* it is the first **advisory** output class and the first speech driven by a
  standing mode rather than an `Event`/`Group`. Putting it in `callouts.py` would couple it to the
  push-path arbitration Decision 1 deliberately avoids; putting it in `crew_console.py` (already
  2845 lines) buries geometry inside a player-surface module.
- `body-layer/tests/test_attack_run.py`

`src/perception/hybrid_source.py` is **not** changed: it has no geometric gate and no LOS verdict to
source the bound from, so it never sets `relative_direction` — exactly the rule it already follows
for `live_los_clear`.

**Changed — body-layer**

- `src/perception/geometry.py` — add `signed_angular_delta_deg(from_deg, to_deg) -> float` in
  `(-180, 180]`, beside its existing unsigned sibling `angular_delta_deg`; add
  `alignment_direction(...)`, a named wrapper over `body_relative_direction` (Decision 3).
- `src/perception/clustering.py` — `Cluster` gains `centroid_alt_m` (mean of its members' own
  `ClusterCandidate.alt_m`, which already carries real per-unit altitude and is already read by
  `_separable`/`_extent_count`). Today `Cluster` drops it and `naked_eye_source` substitutes
  `ownship_state.alt_m`; that substitution is the *flat* convention Decision 4's finding is about.
  (Decision 16, Stage 2.)
- `src/perception/estimation.py` — `RELATIVE_DIRECTION_SIGMA_DEG: Final[float] = 0.0` and a
  `perturbed_relative_direction(...)` that applies it with the existing
  `_deterministic_unit_gaussian_pair` idiom. **At `0.0` it is an identity function** — present so
  §18's "exact while the look holds" is a *parameter*, not a structural property (Decision 11
  REVISED).
- `src/perception/source.py` — a frozen `RelativeDirection` dataclass and an
  `Observation.relative_direction: RelativeDirection | None` field (Decision 16).
- `src/perception/naked_eye_source.py` — populate it for an admitted cluster when
  `live_los_clear is True`, from truth-to-truth geometry; `None` otherwise.
- `src/belief/percept.py` — carry `relative_direction` through `percept_of`, with its own
  justification paragraph in the module docstring (Decision 16's boundary argument).
- `src/belief/speech.py` — a new `render_alignment_*` / `render_attack_run_*` renderer family.
- `src/belief/tasks.py` — `TaskKind` gains `"attack_target"` (one `Literal` member; `TaskStore.tick`
  needs **no** change — it already skips any task with `area is None`).
- `src/belief/crew_console.py` — new tokens and handlers (`_handle_select_target`, `_handle_step`,
  `_handle_engage`, `_handle_disengage`, `_handle_drop_target`), `drain_attack_run`, membership in
  `DISPATCHED_COMMAND_TOKENS`, a `_describe_token_for_confirm` branch, and a
  `_describe_task_for_speech` branch for the new kind (it returns `None` for an unknown kind, so the
  cancel readback would silently drop it otherwise).
- `src/belief/voice_commands.py` — `disengage` / `drop_target` into `CANCEL_TOKENS` (raises the act
  floor from `ACT_FLOOR` 0.60 to `ACT_FLOOR_CANCEL` 0.80 — they destroy standing state).
- `src/belief/callouts.py` — one narrow gate: suppress `_WATCHED_ONLY_KINDS` for the contact that is
  the current attack-run target (Decision 5).
- `src/logger.py` — `crew_console.drain_attack_run(...)` in the `--crew-text` poll loop immediately
  **before** `drain_events`; `AttackRunState` carried on `ConsolePerceptionRunner` beside
  `optic_state`; (Stage 6 only) a branch in `_active_gaze`.
- `src/belief/tools.py` — `attack_target_task(...)`, mirroring `watch_contact_task` (tools.py:1057).
- `docs/STRUCTURE.md`, `body-layer/ROADMAP/BL-14.md`.

**Changed — audio-adapter** (a second subproject: its own `ruff`/`mypy --strict`/`pytest` must run)

- `src/vocabulary.py` — new tokens in `VOICE_ONLY_TOKENS`, phrasings in `PHRASES` (an import-time
  `assert set(PHRASES) == set(TOKENS)` fails if either is missed), a `parse_step_direction` /
  `STEP_DIRECTION_WORDS` table and a step-count parser.
- `src/command_matcher.py` — `_parse_select_slots` / `_parse_step_slots` branches **in front of**
  the generic phrase table in `match_transcript` (branch order is pinned by a test).

**Not changed:** `brain-layer/src/prompts.py` and `belief/brain_reply.py`'s
`OFFERED_CONFIRM_VOCABULARY` — these tokens carry slots, and the confirm vocabulary is the no-slot
subset. `aircraft-layer` is untouched: **these commands are voice-only by construction**, because
`logger._poll_f10_commands` calls `handle_command(token, now_sim)` with no slots.

---

### Decisions

**1. The advisory channel lives beside `CalloutScheduler`, on the existing immediate path.**

There are already two producers into `CrewConsole._print`, the single output funnel: the **push**
lane (`drain_events` → `scheduler.tick`) and the **immediate reply** lane (every `_handle_*` →
`_print`). Alignment guidance is a third producer on the reply lane, not a new `Event` kind.

- It must not enter `tick`. `tick`'s every mechanism is tuned for *volume reduction on spontaneous
  reports* and each would damage guidance: `CALLOUT_MAX_AGE_S` (10 s) drops a candidate outright,
  `WATCH_REPORT_MIN_GAP_S` (8 s) is "lost, not deferred", the one-line-per-tick cap, group-keeper
  suppression, signature dedup, and the observability gate.
- `callouts.py`'s own module docstring already forbids the merge: *"This gate is for the push path
  only… do not 'complete' this gate by wiring it to the pull path."* Guidance is pull-path output.
- **§7 then costs nothing.** "Losing sight does not interrupt the run and is not announced" is
  satisfied *by construction* — the observability gate lives only on the push path, so a pull-path
  utterance never consults it. No new exemption is needed, and
  `_OBSERVABILITY_EXEMPT_KINDS` is not touched.
- **Occupancy is still shared, and that is the one thing guidance must respect.** `drain_attack_run`
  reads `scheduler.busy_until_sim` and does not speak while the channel is busy; `_print` then
  charges the channel through the existing `note_reply` (extend via `max`, never preempt — a
  detection the pilot has not heard is not thrown away to say "a bit left"). Because
  `drain_attack_run` runs **before** `drain_events` in the poll loop, a guidance line wins the tick
  and the scheduler's candidates are **deferred, not dropped** — the belief store is the backlog.
- A deferred guidance line is never stale: the error is re-derived at emission, and the change
  baseline is the last *spoken* value (Decision 7).

**2. The run is a `PendingIntent` of a new kind, not a new state machine — the *phase* is a frozen
state on the runner.** Two existing abstractions, used for what each is for:

- **Intent** → `TaskKind` gains `"attack_target"`, created with `area=None`,
  `deadline_sim=math.inf`, `contact_id=<selected target>` — the exact shape `watch_contact` already
  uses for a standing mode with no completion predicate. This buys three spec requirements free:
  `TaskStore.tick` skips it so it ends only on explicit cancel; `tools.cancel_task` already resets
  `task.contact_id`'s attention to `"normal"`; and *"normal cancel/stop path also deselects"* is
  already true because `cancel_task` with `kinds=None` cancels every active task.
- **Phase** → `AttackRunState` (frozen, replaced not mutated, carried on
  `ConsolePerceptionRunner` beside `optic_state`), modelled on `OpticState`/`decide()`: a pure
  function of its inputs, so replay determinism holds.
- `drop target` cancels the task (and with it any run). `disengage` clears `AttackRunState` only and
  **keeps the selection** — the 2026-09-24 note's *"stop the run, keep the watch"*, and consistent
  with the spec listing `drop target` and `disengage` as separate commands.

**3. The geometry already exists, and the right frame is the *bank-stabilised* one.**

`perception.geometry.body_relative_direction(observer, target, heading_true_deg=, pitch_deg=,
bank_deg=)` returns **both** axes already: signed `azimuth_deg` in `(-180, 180]` (0 = down the nose,
positive = right) and signed `elevation_deg` (positive = above boresight), with attitude removed in
three steps. No new data channel, no new trig.

**But it must be called with `bank_deg=0.0`.** Rolling in at 45° of bank, the full airframe frame
mixes the two axes: at 90° of bank a target dead ahead and low reads as a pure *azimuth* error, and
Petrovich would say *"come left"* when the pilot needs to pull. With bank removed, `azimuth_deg` is
a **heading** error ("come left" = turn) and `elevation_deg` is a **pitch** error ("higher" = pull),
which are the pilot's two controls. Steps 1 and 2 of the existing derivation are exactly that, so
`bank_deg=0.0` is the whole implementation — wrapped once as
`geometry.alignment_direction(...)` so the zero is explained in one place and does not read as a
bug at each call site.

**3a. Both axes are one derivation, and the frame the decomposition happens in is the
heading-and-pitch frame with bank removed** (§17, added in the amendment pass).

§17 specifies the mechanism rather than a second model: *"ownship → target LOS vector and ownship
boresight (unit) vector… azimuth guidance is the lateral angle between [them]… vertical guidance is
the [vertical] angle"*. `body_relative_direction` **already is** that decomposition —
`azimuth_deg = atan2(right, forward)` is the lateral component and
`elevation_deg = atan2(up, hypot(forward, right))` the vertical one, read off the same rotated
triple. So there is **one** function, no second vertical model, and no new trig. The amendment adds
nothing here but the name.

**What needs saying explicitly, because "lateral" and "vertical" are meaningless without a
reference:** the decomposition is done in the frame that remains after removing **yaw and pitch but
not bank** (steps 1–2 of the existing derivation; step 3 is skipped by passing `bank_deg=0.0`). That
is the frame in which the two components map one-to-one onto the pilot's two controls — azimuth is a
*heading* error he fixes with pedal/bank, elevation a *pitch* error he fixes by pulling. In the full
rolled airframe frame they are mixed, which is Decision 3's whole argument: at 90° of bank a target
dead ahead and low reads as pure azimuth and Petrovich would say *"come left"* when the pilot needs
to pull. §17's "boresight vector" is the nose, which is bank-invariant; only the *decomposition
axes* care about bank, and this is the choice of axes.

Consequence worth stating: because bank is removed, **bank rate does not stale the derivation at
all** — which matters for Decision 16's staleness budget, since roll rate is the fastest attitude
rate in a roll-in.

**4 REVISED (2026-10-14, §17). The finding stands; the remedy is removed. The target's own altitude
arrives with the unit, so there is no world-model elevation query at all.**

> *"No world elevation necessary since unit data has elevation."*

Verified rather than taken on trust: `aircraft-layer/src/schema/world_objects.py` carries a per-object
`altitude_m` (MSL metres, `alt_m` on the wire), and `OwnshipState.alt_m`'s own docstring says MSL *"is
the right frame for comparing ownship against a contact's own altitude"*. Both sides are already in
the same frame. So:

- **`geometry.elevation_at` is not called, there is no quantised-position cache, and the
  `BL-B49` enrichment-path risk does not apply.** One in-loop world-model dependency, one cache and
  one performance risk all leave the plan.
- The altitude reaches the vertical axis through Decision 16's relative-observation channel, which
  is where the per-unit altitude already exists (`ClusterCandidate.alt_m`). `Cluster` currently
  discards it and `naked_eye_source._build_observation` substitutes `ownship_state.alt_m` — that
  substitution *is* the flat convention the finding below is about, and Stage 2 stops it being the
  only thing available.
- **`Contact.last_alt_m` is still the ownship's altitude, and the hazard note below is kept
  deliberately.** Nothing in this plan now reads it for a vertical angle, but the field is still
  named as if it were the target's, and anyone re-deriving this will walk into it. It is also the
  reason Decision 17's tier 2 cannot simply read belief for the vertical: it has to remember the
  relative height from the last look instead.
- A second thing the superseded remedy got wrong, worth recording: `belief/enrichment.py` already
  holds exactly that mechanism — `WorldEnrichmentCache` / `_terrain_aware_world_position` caches a
  terrain-aware target position on a quantised key, and `relative_geometry` already computes
  `relative_alt_m` from it, uncached, *"because ownship moves every poll"*. The remedy was
  reinventing a cache that exists, in a module that must not grow a second one.

The failure the original remedy avoided still has to be answered, and now is, differently: a missing
elevation can no longer happen (there is no grid lookup), so the vertical half's fail-open rule
applies to a different absence — **no relative observation**, which is Decision 17's tier 2.

---

> **Superseded by Decision 4 REVISED above (§17, 2026-10-14).** The finding — that
> `Contact.last_alt_m` is the *ownship's* altitude at the last look — stands and is kept. Its
> remedy, a `geometry.elevation_at` terrain lookup cached on the quantised position, is dropped: the
> unit's own altitude arrives from the aircraft layer, so no world-model elevation query is needed.
> Kept in place because the reasoning below is what makes the revision legible, and because the
> `last_alt_m` trap it documents is still live for anyone else.

**4. The vertical axis needs a terrain elevation lookup, because `Contact.last_alt_m` is the
*ownship's* altitude.**

Measured by reading, not assumed: `Contact.last_alt_m` is set from `implied_position(percept)`
(contacts.py:594), whose altitude is `percept.ownship_at_observation.alt_m` — the flat projection's
"target at observer's own altitude" convention, and the field docstring says it is **not fused**. So
`contact.last_position` carries the aircraft's own altitude at the last look. A boresight elevation
computed from it reports how much the aircraft has climbed or descended since, not where the target
is. **The vertical word would be noise.**

The target's ground elevation comes from `perception.geometry.elevation_at(conn, theatre, x, z)`
(terrain MSL at a point, `None` when unavailable) against `contact.position.x/z`, with
`EnrichmentContext.conn`/`.theatre` already on `CrewConsole.enrichment`. Cache it on the quantised
`(x, z)` the way `WorldEnrichmentCache` already does — it changes only when the target moves.
**Never route this through `describe_contact` or `_report_scope`** (`BL-B49`: 63.25 ms/contact of
enrichment computed and discarded; `BL-14`'s own roadmap entry names callout rate as the
performance risk).

`elevation_at` returning `None` (no grid coverage), and the known coarse-grid error that can place a
unit "underground", are why the vertical half **fails open**: the vertical word is omitted and the
elevation gate counts as satisfied, so a missing grid cannot keep Petrovich from saying *"lined up"*.

**5. A selected target is attention `"priority"`, and its own routine callouts are suppressed for
the duration.**

`Attention = Literal["ignore","normal","watch","priority"]` is declared and `"priority"` is read
everywhere as `("watch","priority")`, but **nothing in the player-facing path sets it** — a clean
slot. Setting it gets, for free: the binocular policy prioritising looks at the target
(`logger._look_targets`' `watched=`), top ordering in `callout_priority`'s `-attention_rank`, and
the eyesight view's orange. Group members get the existing one-time static tag via
`_mark_watched_with_group` (user, 2026-10-05: *"Tag once, static."*).

**The hazard this creates, and the gate that closes it.** `contacts.py:1500` reads
`is_watched = current_attention in ("watch","priority")`, which enrols the target in the
watched-only callout kinds — including `CONTACT_RANGE_CROSSED`. Raising attention on an attack-run
target would therefore make Petrovich speak *"getting closer"* about it during the run: **the range
countdown §1 struck, reintroduced through the back door.** So `CalloutScheduler.tick` skips
`_WATCHED_ONLY_KINDS` for the contact id that is the current attack-run target. Justified, not
convenient: the alignment channel is already saying everything there is to say about that one
contact, and §4's silence-means-aligned reading is destroyed by any other line about it.

Routine reporting about **everything else** continues unchanged. An attack run must not blind the
intercom to a SAM that has just come up.

**6. Stepping: signed angular order around the current line of sight, recomputed every press, and it
stops at the end rather than wrapping.**

Per press: take the bearing from ownship's **present** position to the current target as the
reference, then for every candidate compute `signed_angular_delta_deg(reference, bearing_to
_candidate)`. `step right` takes the smallest strictly-positive value, `step left` the
smallest-magnitude negative one; `step N <dir>` takes the Nth. `near`/`far` use the same machinery
keyed on `range_m` instead of angle. Nothing is sorted at selection time — which is the whole point
of §3: *"it changes as/if we circle the contacts. Or the contacts move."*

- **Candidate set** = `store.group_for_contact(target_id)`'s `member_contact_ids` resolved through
  `store.contact(...)`, filtered by the `<what>` descriptor remembered from the selecting command
  (via the shared `descriptor_verdict`, dropping only `"wrong"`). Use `member_contact_ids` directly,
  **not** `group_view.collapse(...)` — `collapse`'s `units_hi` can legitimately be `math.inf` and
  nothing here needs the tree.
- **Ungrouped target** → the candidate set is the target alone → `render_unable("no other units in
  the group")`.
- **End of the ordering: stop, and say so** (`render_unable("that's the last one")`). Wrapping would
  silently re-target a unit the pilot has just stepped past, and a surprise jump across the whole
  group in the seconds before release is the worst available outcome. Stable and predictable beats
  clever.
- **The undercount is honest and visible.** `BL-12` measured 4 contact records against 6 real units;
  a unit the pilot can see may have no record and so be unreachable by `step`. Today's direction
  accepted exactly this when it routed stepping through the belief store, and the pilot's recourse
  is another `step` or a fresh `select target`. Do not add a world-truth path to close it.

**7. Cadence is change-driven, with the baseline at the last *spoken* callout.**

`AttackRunState` carries `last_spoken_azimuth_deg`, `last_spoken_elevation_deg` and
`last_spoken_text`. Emit when **either**:

- the rendered guidance string would differ from `last_spoken_text` (reusing the
  `_last_spoken_signature` idiom already in `callouts.py`), **or**
- `|current − last_spoken|` on either axis exceeds `ATTACK_RUN_CHANGE_THRESHOLD_DEG`.

Comparing against the last **spoken** value rather than the previous sample is §10's own named guard
against slow drift accumulating under a per-sample threshold. A steady run is silent by
construction, not by a suppression rule over a timer — there is no timer.

*Consequence worth seeing before the sortie, not designed around:* a pilot who hears *"come left"*
and does not turn hears nothing further, because nothing has changed. That is correct under design
A and is the opposite of the 23-callouts-in-45-s problem, but whether prolonged silence while badly
misaligned reads as "aligned" is a sortie question (see §"What a sortie must decide").

**7a. Decision 7 REVISED (2026-10-15 sortie, §1) — the `either` becomes a veto, and the angular
clause is deleted.** The decision above stands as the record of what was built; **do not implement
from it.** The sortie measured **47 of 125** attack-run utterances byte-identical to the one before
(38%), and the cause is the second bullet firing while the first is unchanged: the threshold is 3.0°
while the vocabulary's own quantisation is 10° (elevation gate, direction §11's *"wide on purpose"*),
30° (o'clock sector) and 7.5°/5.0° (azimuth rows), so **a 3° threshold on a 10° word gate cannot do
anything except re-speak unchanged text.** Emit **iff** the rendered string differs;
`last_spoken_azimuth_deg`/`last_spoken_elevation_deg` lose their only reader and go with it. This is
§10's drift risk being *answered* by a sortie rather than reversed — the guard fired 47 times and
never once carried information. Replacement: `plans/attack-run-sortie-fixes/plan.md`, `[[BL-B70]]`.

**8. `silence` mid-run mutes guidance — no exemption.** `self.silenced` gates exactly one thing,
`_print`'s `speech_client.push_speech`, and does so for `bypass_gate=True` urgent lines too, by the
user's own explicit choice. Guidance should not be the first exception, and the overlap window is
almost empty anyway: **any recognised command clears silence**, and `engage` is a command, so a run
cannot begin while muted. The only remaining case is the pilot deliberately saying `silence` during
a run, where honouring it is the right answer. Text and overlay keep showing the guidance either
way. (Flagged below as a one-line confirmation, not a blocker.)

> **Settled by the user, §16, 2026-10-14** — *"`silence` stays absolute… Guidance is not exempt."*
> This was open decision 3; the recommendation was accepted unchanged, so the text above stands as
> written and the open decision is removed.

**9 REVISED (§15, 2026-10-14). The run claims the gaze, and the claim is part of wiring the loop —
not a trailing stage.**

> *"an attack run fixes the look on the target. The cost is accepted: no scanning elsewhere for the
> run's duration."*

This was open decision 2; the recommendation was accepted, and the `_SECTOR_LEGS["left"]` case
below is what settled it. Two consequences for the plan beyond striking the question:

- **It moves earlier.** Decision 16's relative observation exists *only while the target is being
  looked at*, so a guidance loop wired without the gaze claim would run in its degraded tier most of
  the time under a commanded scan — and in the `scan left` case, always. The gaze claim is therefore
  a precondition of the loop being worth flying, and it merges into the wiring stage (now Stage 5)
  instead of trailing as Stage 6.
- **Routine reporting about everything else continues unchanged**, which §15 restates explicitly.
  An attack run must not blind the intercom to a SAM.

> **Superseded by Decision 9 REVISED above.** The analysis below is unchanged and still load-bearing
> — only its conclusion ("Stage 6, gated on the user's answer") is replaced by "settled yes, folded
> into the wiring stage".

**9. Gaze: coexist for Stages 1–5; claiming the gaze is Stage 6 and is the user's call.**

The precedent the brief names is explicit in the code: `_active_gaze` reads **only**
`kind == "scan_area"` tasks, and a `watch_contact` task's `area` is `None` by construction, so
*watch has no gaze effect at all* — scan and watch coexist deliberately. The attack-run task
(`area=None`) inherits that, so Stages 1–5 steal nothing.

What that costs, quantified: under `FREE_SCAN_PLAN` the table is `(12, 11, 10, 9, 12, 1, 2, 3)` at
`FOCUS_DWELL_S = 2.0`, so 12 o'clock is looked at for 2 s in every 8 s and the target's believed
position is at most ~8 s stale — ~64 m for 8 m/s armour, ~3.7° at 1 km, the same order as the
proposed lined-up band. Tolerable.

**The bad case is a standing commanded scan.** `_SECTOR_LEGS["left"] = (11, 10, 9)` contains no 12,
so `scan left` followed by `engage` means the target ahead is **never** looked at and guidance runs
silently on an ageing belief. Stage 6 is the fix, and the mechanism is already seamed:
`ScanPlan.__post_init__` deliberately permits `fixed_look` alongside a commanded sector precisely so
a phase can stare while remembering what was commanded underneath — the binocular glass phase
already uses it via `ScanPlan.fixed_look_at`. An attack-run branch checked *before* the `scan_area`
loop in `_active_gaze` is a few lines. It is flagged rather than assumed because it trades away
scanning — and therefore threat warning — for the run's duration.

**10. "Projected if moving" is a read-time derivation for guidance only, never written into belief.**

Nothing in body-layer dead-reckons: `Contact` has no velocity or heading, and elapsed time only
*inflates* `PositionEstimate`'s covariance (`Covariance2D.inflated`) — the mean is moved only by a
genuine fuse. `BL-14` would be the first thing to move a believed mean with time.

*Renumbered by the 2026-10-14 amendment, and narrowed: this is now a **tier 2 only** concern
(Decision 17). Tier 1 is a live look and never needs projection, which makes the work smaller and
removes its only interaction with the guidance a pilot will usually hear.*

- Stages 1–6 hold **last known**, unconditionally *(was "Stages 1–4")*. §7's own fallback, and
  correct for the stationary majority the position-uncertainty direction is about.
- Stage 7 adds projection *(was "Stage 5")*, from the only inputs that exist: direction from `Group.heading_deg` (the
  sole direction-of-travel estimate in belief, group-level, held only while
  `movement_state == "moving"`, with `heading_confidence`), speed from
  `plausible_speed_mps(op_class, installation_component=)`, gated on
  `contact.motion.state == "moving"`. `motion is None` means *never observed for movement* and must
  be treated as "hold", never as "stopped" and never as "moving".
- **The projected position is passed to the alignment derivation as an argument and is never
  assigned to `Contact.position`.** Writing it back would corrupt the association gate and
  `group_matches`' displacement bound, which both read the same estimate.

**11 REVISED (§17/§18, 2026-10-14). Four parameters now, and the *structure* is the requirement —
resolution must be reachable by changing a value.**

> *"design approach so that fine grained elevation guidance is possible with just changing
> parameters."*

That is a constraint on the design, not a value. Concretely, three rules, each of which can be
checked by reading the diff:

1. **The word thresholds are one ordered data table per axis**, `tuple[tuple[float, str], ...]`
   descending, read by one renderer. Going from a coarse nudge to fine-grained guidance is adding
   rows or lowering numbers — never a new branch, never a second renderer. The gate is simply the
   table's last (smallest) threshold, so it is not a separate concept either.
2. **The derivation is one function** (Decision 3a) and it is resolution-agnostic: it returns signed
   degrees on both axes and knows nothing about words or bands.
3. **Nothing in the renderer may branch on "the vertical axis is coarse."** A test asserts the two
   axes go through the same table-lookup helper, so a future fine-grained elevation needs no renderer
   change at all.

The same shape applies to §18's noise term, which is why it is a parameter rather than an absent
feature:

| parameter | proposed | why this value, and its bounds |
|---|---|---|
| `ATTACK_RUN_LINED_UP_AZIMUTH_DEG` | `5.0` | unchanged — see the table below |
| `ATTACK_RUN_ELEVATION_GATE_DEG` | `10.0` | unchanged in value; the *tension* noted below is now a recorded consequence rather than an open fork, since §17 declined the discrimination test and §11 says a flight decides the number |
| `ATTACK_RUN_CHANGE_THRESHOLD_DEG` | `3.0` | unchanged — see the table below |
| `estimation.RELATIVE_DIRECTION_SIGMA_DEG` | `0.0` | §18's *"guide to it exactly because we look at it"*, read as v1 treating the relative direction as exact while the look holds. At `0.0` the perturbation is an identity function, so the channel is **parametrically** exact rather than structurally exact — a future value needs no rewrite. **Settled by §20, 2026-10-14** (was flagged as an assumption awaiting confirmation; see Decision 16 item 5 and Decisions Requiring User Input) |

One thing the revision deliberately does **not** do: lower `ATTACK_RUN_CHANGE_THRESHOLD_DEG` even
though its stated justification (*"do not re-speak until the error has moved by more than belief's
own noise"*) no longer applies to tier 1, whose noise is now zero. The threshold's real job under
design A is **channel economy**, not noise rejection, and 3.0° is a cadence guess the sortie decides.
Said here so nobody re-derives it from `BEARING_SIGMA_DEG` and "fixes" it to 0.

> **The table below is superseded for `RELATIVE_DIRECTION_SIGMA_DEG`'s absence only** — the three
> rows' own values and reasoning stand, except that
> `ATTACK_RUN_LINED_UP_AZIMUTH_DEG`'s justification ("above `BEARING_SIGMA_DEG`, so belief noise
> alone cannot chatter the band") now describes **tier 2 only**. Tier 1 has no bearing noise at all,
> so the band's real driver there is the crosswind offset §5 names, exactly as that section said.

**11. Three constants, one place each, stated as assumptions.** Declared in `attack_run.py` with the
posture `GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS` already sets — a stated guess with its bounds
named, not a measurement, tuned from flying.

| constant | proposed | why this number, and its bounds |
|---|---|---|
| `ATTACK_RUN_LINED_UP_AZIMUTH_DEG` | `5.0` | Above `estimation.BEARING_SIGMA_DEG` (3.0), the naked-eye channel's own bearing sigma, so belief noise alone cannot chatter the band. Below half a clock hour (15°), so the band sits strictly inside the 12 o'clock sector §6 switches on. The crosswind offset §5 names is the real driver and is unmeasured. |
| `ATTACK_RUN_ELEVATION_GATE_DEG` | `10.0` | §11: deliberately wide, so a lofted nose stays inside it. **See the open decision below — this value and the discrimination purpose §11 states are in tension.** |
| `ATTACK_RUN_CHANGE_THRESHOLD_DEG` | `3.0` | `BEARING_SIGMA_DEG` again: do not re-speak until the error has moved by more than belief's own noise. |

The *large*-vs-*small* split inside the sector (`"come left"` vs `"a bit left"`) is **derived, not a
fourth constant**: `"a bit"` from the lined-up band out to half the sector (7.5°), `"come"` beyond
it. Say so in the code, so nobody mints a constant for it later.

**12. No damage reporting, and therefore no automatic stop — a stated gap against the spec.**
`docs/concept/Attacking target.md` says *"If target is destroyed (on fire is enough), attack run
stops automatically"*. That cannot be built here: §13 keeps `BL-14` inside body-layer with no new
aircraft-layer channel, and the damage channel (`getLife()`, `S_EVENT_HIT`) is probe-answered but
unbuilt. In `BL-14` a run ends **only** on `disengage` / `stop attack` / `abort`, `drop target`, or
the existing cancel path. Petrovich never says *"hit"*, *"on fire"* or *"destroyed"*. Chosen
deliberately; first thing to revisit when a damage channel exists.

**13. Two end conditions the direction does not cover, because they are not "losing sight".**
§7 is about a target behind a ridge. A target whose **contact record ceases to exist** is different,
and has two real mechanisms: `LOST_THRESHOLD_S` (120 s since last observed) retires it, and a
merge can abandon its id outright with no successor recorded anywhere
(`debugger/project_continuity_merge_direction_abandons_contacts`). In both cases guidance has
nothing to guide on, so the run **ends and says so once** — `render_lost_contact` already exists.
Silently continuing against a vanished target is the one thing that would make silence lie.

**14. `select target` implements the spec's own tie-break; it does not reuse
`_resolve_follow_target`.** That resolver's own docstring forbids it: *"a stopgap… delete the
resolver and these constants with it; do not tune them as if they modelled anything real."* Its
weighted score plus `FOLLOW_SEPARATION` ambiguity refusal is a different rule from the spec's
**watched beats unwatched, then closest**. Build selection from the two shared primitives instead —
`descriptor_verdict` (the three-way predicate `report` and `follow` already share) and
`_nearest_contact_id`'s filter-then-compare shape — and implement the spec's tie-break directly.
Refusing as ambiguous would also be wrong here: `step` **is** the spec's correction mechanism, so
picking one and letting the pilot step is strictly better than a "say again".

**15. The weapon token parses and nothing reads it** (§14). `engage <what> <where> [guns|rockets|
missiles]` accepts it into the slots dict; no body-layer code branches on it. One test pins that it
is accepted and ignored, so the grammar does not change when something does consume it.

**REVISED — `[[BL-B67]]` Stage 1 (2026-10-29).** This decision is superseded: `_handle_engage` now
reads `slots["weapon"]`, sets `attack_run_weapon` beside `attack_run_transition`, and `"missiles"`
gates the ATGM run (`body-layer/src/belief/crew_console.py`, `body-layer/src/body.py`). Any other
value, including a bare `engage`, still runs the unchanged BL-14 guns/rockets path — the "parses and
is ignored" behaviour this decision describes holds only for those values now, not for `"missiles"`.

**16. The ownship-relative observation: a new perception datum, produced in `perception/`, bounded
by the look, and read by exactly one consumer.** (§18, added in the amendment pass. This is the
consequential change and it moves the stage boundaries.)

**Where it lives, and why not anywhere else.** Three homes were considered:

- *A field on `Observation`/`Percept`* — **chosen.** It is produced where the geometry and the unit
  identity already are (inside the detection gate, alongside `live_los_clear` and the velocity
  join), and it crosses the belief boundary the way every other perceived datum does, through
  `percept_of`. `ContactStore` already keeps the latest percept per contact, so no new store.
- *A separate `PerceptionSource` method, `relative_direction_for(contact_id)`* — rejected. Sources
  key by DCS `object_id`, which by invariant never leaves `perception/`; the `object_id → contact`
  mapping does not exist on the source side, so the method could not be called.
- *Derived in the attack-run runner from the aircraft feed directly* — rejected. It would give
  `belief/` a second, unmediated path to DCS truth with no gate in front of it, which is precisely
  the boundary `percept.py` exists to make structural rather than remembered.

**What it carries, and why these fields rather than the finished angles.** A `RelativeDirection` is
an ownship-relative offset plus the geometry needed to re-derive against *current* attitude:

```
RelativeDirection(forward_m, right_m, up_m)   # ownship-frame offset at the observing poll,
                                              # yaw removed, pitch and bank NOT removed
```

**It is not the finished azimuth/elevation, and that is a measured decision, not taste.** The crew
poll loop runs at `_DEFAULT_POLL_INTERVAL_S = 1.0 s` (`logger.py:1123`). In a 45° bank level turn at
220 km/h (61.1 m/s) the heading rate is `g·tan45/V = 0.161 rad/s = 9.2°/s`, so an azimuth frozen at
the observing poll is **up to ~9° stale one poll later — nearly twice the proposed 5° lined-up
band.** Carrying the offset and re-rotating it against the current heading/pitch each poll removes
that term entirely. What remains is ownship *translation* (≤61 m/s × 1 s, ~1.7° at 1 km worst case,
and ~0° when flying at the target) and target motion (8 m/s armour ⇒ ~0.5° at 1 km). Both are an
order below the band.

**Why a finished angle cannot be carried — three further reasons (§21, amendment pass), and the
third corrects a filed assumption in a different subproject.** The 9.2°/s figure above answers "is
re-rotation necessary"; the user's three points reframe what it means:

1. **Speech latency bounds the useful precision.** A callout is already a couple of seconds old by
   the time it is heard, so freshness past that point buys nothing — worth holding next to Decision
   7's cadence rule, the other place "how fresh is fresh enough" gets decided.
2. **The register and the dynamics co-vary, so the design self-balances.** Angular rate peaks
   during turn-in — the o'clock phase, where the words are 30° buckets and 9° of staleness is
   immaterial. Once the target is in the 12 o'clock sector the movements are gentle, which is
   exactly where the words become fine. **Stated explicitly so the 9.2°/s figure above is not read
   as a blocker**: it is the reason re-rotation is correct engineering, not evidence this loop is
   marginal.
3. **A selective fast lane — ownship telemetry and the currently selected target only, not bulk
   world objects — is a real future seam, scoped to whatever has one.** *(Reshaped by a second
   round of user direction, same day, after the first reading of this point had the split
   backwards.)* The user's own words: *"for body layer poll rate, we should have a selective more
   frequent poll: ownship telemetry and current target data. Not all world objects, just ownship
   and current target. Could be that 5 Hz. We'll need both anyway for 9K113 missile guidance to be
   precise."* This is **not** "telemetry fast, world objects slow" (the first reading, now
   corrected) — it is a narrow two-thing fast lane that exists only while something is selected,
   not a general rate split.

   **Dependency direction, checked, and the opposite of the first reading.** Aircraft-layer already
   exports at 5 Hz (`EXPORT_INTERVAL_S = 0.2`, `aircraft-layer/dcs-export/Export.lua:143`), and
   `aircraft-layer/ROADMAP/AC-B3.md` ("Split the export throttle") is about *slowing* bulk
   world-object export to save FPS cost, not speeding anything up. So a body-side selective fast
   poll gets 5 Hz target data **today, with no aircraft-layer change**. `AC-B3` only becomes a
   *prerequisite* for this seam if it lands and slows bulk world objects for FPS reasons — at which
   point the selected target would need its own fast publication carved back out on the aircraft
   side. `AC-B3`'s own entry now carries a correction note stating this dependency the right way
   round, filed by this amendment pass.

   **The constraint that actually matters: the fast lane cannot be the existing poll loop running
   5× faster, and the figures that would have argued otherwise are stale.** `BL-B26`'s originally
   filed 1,579 ms worst tick and `group_salient_ids`'s originally filed ~300 ms/poll were both
   measured **before** `BL-11` landed (2026-10-06): `group_salient_ids` is now **1.1 ms median, 5.5
   ms max** (`BL-11` Stage 2, `BL-B30`), and the realised poll-work median is **12.6 ms**, down from
   330 ms (`BL-11`'s live-acceptance-debt entry). Checked rather than carried forward from the
   user's own framing, because those specific numbers no longer support "a 5 Hz full tick is
   impossible" as written — at 12.6 ms median there is headroom inside a 200 ms budget.
   **The architectural point survives the correction anyway, on different grounds**: `BL-11`'s own
   figure is a *median* against one bench scale, enrichment-cache misses still cost ~42 ms each
   (2.3 % of calls, `BL-11` Stage 3b), and nothing bounds the worst case the way the median is
   bounded — so running the *whole* perception tick (clustering, group reconciliation, enrichment,
   callout scheduling) five times more often multiplies a cost that is not guaranteed flat, for
   work most of which (every contact that is not the selected target) a fast lane has no reason to
   touch at all. A narrow path is the right design independent of whether today's worst case is
   1,579 ms or 42 ms.

   **Whether the narrow path falls out of what already exists: yes, for the ownship half; the
   target half needs one open question flagged rather than resolved here.** Decision 16's
   relative-observation design already needs nothing from clustering/group reconciliation/
   enrichment/callout scheduling to refresh — it re-rotates a carried offset against *current*
   ownship attitude, which is one `get_telemetry_latest()` call and a trig re-derivation, not a
   perception tick. So a fast *ownship*-telemetry poll is a clean fit, outside the heavy loop
   entirely. The *target* half is less clean to resolve without building it: aircraft-layer's API
   has no per-object filter (`aircraft-layer/src/api/server.py`'s `/world_objects/latest` always
   returns the full cached snapshot, same shape as telemetry), so a fast poll of "just the current
   target" means either filtering the existing bulk payload client-side at 5 Hz (cheap per the
   figures above, since the heavy cost was never the HTTP/JSON step) or a new filtered endpoint —
   and whether the narrow path is a second loop or a sub-tick inside the existing one is the same
   open question. Left for whoever builds `BL-B63`, not settled here.

   **9K113 missile guidance is named as the second consumer, which makes this a known future
   requirement rather than speculative scope** — *"We'll need both anyway for 9K113 missile
   guidance to be precise."* `BL-B63` below is framed as a reusable seam for that reason, not as an
   attack-run-specific optimisation.

   **Filed, not built, and attack-run-scoped by construction.** A correction note on `AC-B3` and a
   rewritten `BL-B63` for the fast lane, cross-linked to each other and to `BL-14`. Neither is in
   `BL-14`'s scope: this plan's own staleness budget already closes with re-rotation alone at the
   existing 1 Hz rate (point 2 above), so the fast lane is an optimisation/future-requirement for a
   tighter-budget consumer, not a prerequisite for this one. No stage boundary in this plan moves —
   the fast lane is pure future scope, not a dependency of any stage below.

**The offset is relative on purpose, not as a formality.** Nothing on this datum is a map
coordinate: guidance adds ownship's own *displacement* since the observation (a telemetry delta,
not an absolute position) and rotates. So the channel keeps working unchanged if ownship world
position is later made ambiguous, which is §18's pre-GPS framing honoured structurally rather than
rhetorically — *"we might get lost, but still see units and world outside the aircraft and how it is
relative to ownship"*.

**The bound — this is what makes it a perception rather than a map read.** It is set **only** when:

- the cluster was admitted by the detection gate this poll (so it was genuinely looked at), **and**
- `live_los_clear is True` for that cluster — the same all-members-agree rule that field already
  follows.

`None` otherwise, and `None` is never interpreted as "no error"; it is Decision 17's tier change.
A consumer may use it only while
`now_sim - percept.t_sim <= ATTACK_RUN_RELATIVE_MAX_AGE_S` (proposed `2.0`, i.e. two polls), so a
stale value cannot quietly become a map read.

**The no-omniscience argument, written down rather than left implicit.** A future reader will see
DCS truth flowing toward speech and should be able to find the reasoning here instead of
reconstructing it:

1. **Why it is a legitimate perception.** `BEARING_SIGMA_DEG`'s own docstring says it is *"the
   crewman's own pointing precision, not anything DCS reports"*, bounded below by the optical
   resolution floor and above by the 15° clock half-bucket. It models **stating** a bearing — the
   right model for *"ground, two o'clock, two kilometres"* and the wrong one for *"come left"* while
   watching the thing. A crewman really can align an aircraft with a vehicle he is looking at far
   better than he can name its azimuth in degrees; and most of the world-position error is
   *ownship's own*, which cancels in a relative observation. The channel is not Petrovich knowing
   more; it is Petrovich being asked an easier question.
2. **Why it is bounded.** It exists only while the target is being looked at with the sightline
   clear (above). Lose the look and it is gone within two polls, and Decision 17's degraded tier
   takes over.
3. **How it differs from the 2026-09-24 hole it most resembles.** `hybrid_source.py`'s
   `SCOPE_UNCERTAINTY_M` docstring names that hole exactly: *"`associate()`'s truth-exact geometry
   would reach `belief/` unperturbed, behind a cosmetic uncertainty band — exactly the omniscience
   hole this whole plan exists to close, and it sat open on the channel the pilot actually flies
   with."* The difference is **which question the truth answers and who may ask it**: there,
   truth-exact *world* geometry fed the ordinary reporting path, under a declared uncertainty that
   was a fiction. Here, truth-exact *relative* geometry feeds one commanded, bounded manoeuvre, and
   the reporting path keeps its perturbed world-anchored estimate untouched. Reporting does not get
   better; only alignment does.
4. **Where this argument is weaker than the `live_los_clear` precedent, stated plainly.** That
   precedent's own words were *"Nothing the collector knows about a unit's identity or true position
   reaches belief; only the yes/no fact of whether a ray it already looked at was clear."* This
   datum **does** carry true relative position. Combined with ownship's own exact telemetry it is
   convertible to a world position, so **the protection is structural, not informational.** Two
   fences, both cheap and both testable:
   - **Single consumer, grep-enforced.** A test mirrors
     `test_belief_source_never_references_derived_world_position`: no file under `belief/` may
     mention `relative_direction` except `percept.py` (the projection) and `attack_run.py` (the one
     consumer). That test is the fence; without it this decision is a comment.
   - **Never written back.** The relative observation is an argument to the alignment derivation and
     is never assigned to `Contact.position`/`last_alt_m`, never fused, and never reaches
     `association_over_time` or `group_matches` — the same rule Decision 10 already states for the
     projected position, and for the same reason.
5. **Exactness is a parameter, not a property.** `RELATIVE_DIRECTION_SIGMA_DEG = 0.0` (Decision 11
   REVISED) with the perturbation wired in at `0.0`, so a non-zero value is a one-line change.
   **Settled by §20, 2026-10-14** — *"Relative direction while he's looking at it -> exact."* This
   was open decision B below; the value and the reasoning stand unchanged, so what moves is only
   that it is no longer flagged as an assumption awaiting confirmation. For scale, so the zero
   reads as a decision rather than an oversight: at 1 km, 1° of pointing error is 17 m against the
   proposed 5° lined-up band, so a non-zero sigma would be felt as occasional chatter near the band
   edge.

**What this costs.** One new field on two dataclasses, one mean on `Cluster`, one truth-to-truth
subtraction per admitted cluster per poll — mechanically cheaper than the world-anchored path it
replaces for this purpose, and it deletes a world-model query (Decision 4 REVISED).

**17. Two tiers, the same vocabulary, and the fallback's residual is ~3× what the direction document
computed — which changes what the fallback may say.** (§18/§7, amendment pass.)

| tier | condition | source |
|---|---|---|
| **1 — looking** | a `relative_direction` within `ATTACK_RUN_RELATIVE_MAX_AGE_S` | the relative observation, exact at `RELATIVE_DIRECTION_SIGMA_DEG = 0.0` |
| **2 — lost sight** | no fresh relative observation | world-anchored belief `contact.position.x/z` (Decision 10's projection when moving) for the horizontal, plus the **last remembered relative height** for the vertical, both against *current* ownship via `alignment_direction` |

**Tier 2's vertical does not read `Contact.last_alt_m`** — Decision 4's finding forbids it. It
reconstructs the target's altitude as
`percept.ownship_at_observation.alt_m + last_relative_direction.up_m`, both of which are already
legitimately on the percept (`ownship_at_observation` is report bookkeeping, `up_m` is Decision 16's
own field). That is the honest crew reconstruction — *"it was about a hundred metres below me and I
was at three hundred"* — and it needs no new field and no world-model query.

**The direction document's residual arithmetic, checked.** §18 states *"~1.2° azimuth / ~0.4°
elevation of bias-driven error at 1 km"*. Recomputed from `estimation.py`'s own constants
(`BEARING_SIGMA_DEG = 3.0`, `RANGE_FRACTIONAL_SIGMA = 0.17`, `SYSTEMATIC_BIAS_FRACTION = 0.4`):

| quantity | at 1 km | general |
|---|---|---|
| cross-range bias, 1σ | 20.9 m | `0.4 · sin(3°) · R` |
| → azimuth error **viewed from the same aspect** | **1.20°** | scale-invariant |
| down-range bias, 1σ | 68.0 m | `0.4 · 0.17 · R` |
| → azimuth error **after a ~90° change of aspect** | **3.89°** | scale-invariant |
| → elevation error, 120 m above the target | **0.46°** | `R·h/(R²+h²) · 0.068` |
| → elevation error, 300 m above the target | 1.07° | — |

So **the 1.2° and 0.4° figures are both arithmetically correct, and the azimuth one is incomplete in
the case §3 says the pilot is most likely to be in.** It is the residual seen from the *same* aspect
the looks were taken from. The 17%-fractional **down-range** bias — 3.2× larger in metres — rotates
into cross-range as the aircraft circles the target, giving **~3.9° at 1σ, at every range**, which is
78% of the proposed 5° band and exceeds it at 2σ. A pylon turn is exactly the manoeuvre §3 was
written for. The elevation figure is sound but depends on the depression angle, roughly doubling at
300 m AGL; it is not a constant.

**What follows, and it was a behavioural choice rather than arithmetic** — originally left open as
Decision A (see Decisions Requiring User Input), and the bullets below record the recommendation
that was made at the time:

- ~~**Tier 2 speaks the coarse register only**: o'clock (§6) and *"come left/right"* / *"higher"* /
  *"lower"*. It never speaks *"a bit left/right"*, and it never re-opens a band it has already
  called *"lined up"*. Both tiers use **one vocabulary**; tier 2 uses a subset of it, and the subset
  is exactly the words its ~3.9° residual can support.~~
- ~~**The tier transition is silent, and that is only defensible with the restriction above.** §7 is
  explicit that losing sight is not announced. But a silent tier change that moves the aim point by
  ~4° would, on its own, fire a spurious *"come left"* about an aircraft the pilot has not moved —
  Petrovich talking in the seconds before release, which is the one failure design A exists to
  prevent. With the fine word withheld and the lined-up band sticky, a ~4° shift inside a 5° band
  produces **no utterance at all**, so the transition is genuinely unobservable rather than merely
  unannounced.~~
- **Silence keeps one meaning across the transition**: *you are pointed at where the target is
  believed to be*. True in both tiers, which is what §7 requires. *(Kept — still true under the
  revision below, which is why it is not struck.)*
- **Guidance gets more accurate as the run develops** (§18), because tier 1 is the normal state once
  the gaze is claimed and tier 1 has no range-dependent error at all. *(Kept, unaffected.)*

> **Superseded by Decision 17 REVISED below (§19, 2026-10-14).** The two struck bullets above were
> the recommendation under Decision A; the user settled it differently. Kept in place, struck
> rather than deleted, because the arithmetic that motivated them is still the reason a mechanism
> is needed at all — only the mechanism changed.

**17 REVISED (§19, 2026-10-14). Tier 2 speaks a qualifier, not a restricted vocabulary — and the
sticky band is no longer needed.**

> *"When lost sight -> "right/left, obstructed"."*

The user's answer puts the tier **in the words**, rather than in a rule about which words tier 2 is
allowed to use:

- **Tier 2's utterance is `"right, obstructed"` / `"left, obstructed"` — direction plus qualifier,
  nothing else.** Not *"come right, obstructed"*, not *"a bit right, obstructed"*: the user's own
  example drops the magnitude word entirely, so the obstructed register ends up coarse by
  vocabulary rather than by a withholding rule layered onto tier 1's table. It reaches the same
  place the struck recommendation was reaching for — tier 2's ~3.9° residual cannot support a word
  that means "within a few degrees" — without a second mechanism. (The example given names the
  azimuth axis; the vertical analogue, by the same pattern, is `"higher, obstructed"` /
  `"a little lower, obstructed"` when the elevation gate is the one that fired — kept symmetric
  with azimuth rather than silencing the vertical axis in tier 2, consistent with Decision 11
  REVISED's rule that nothing in the renderer may special-case one axis. This symmetric extension
  is this plan's own inference, not quoted, and is worth confirming on the first sortie that
  exercises it.)
- **Why this is better than the struck recommendation.** A silent tier change inside the band would
  have produced no utterance at all — unobservable by design, but at the cost of a second mechanism
  (the sticky band) existing only to hide the transition. The qualifier instead makes the
  *transition itself* audible without being *announced*: the pilot hears which channel he is on,
  and discounts the precision himself rather than the system pretending to a precision it does not
  have. Silence still keeps one meaning (§7, kept above); the distinction now rides on the word, not
  on silence's absence.
- **The sticky lined-up band is struck, not kept belt-and-braces.** It existed only to make a ~4°
  silent shift inside the 5° band produce no utterance. With the tier named in the words, a
  transition is allowed to be heard, so there is nothing left for stickiness to protect.
- **This refines §7 rather than contradicting it, and both halves need stating because a reader who
  has seen only one will read them as opposed.** Losing sight is **still not announced as an
  event** — no *"lost contact"*, no interruption, no task change (§7/§15). What changes is that the
  *ongoing guidance callout*, when it is sourced from tier 2, now carries a qualifier. The event
  stays silent; the register does not.

---

### Spoken vocabulary

| situation | utterance |
|---|---|
| `select target` / `step` readback | `"Target, armour, 2 o'clock."` |
| `engage` — range spoken **once**, §1 | `"Attack run, armour, 2 o'clock, 1.5 kilometres."` (+ terrain fragment, §8) |
| outside the 12 o'clock sector | `"Two o'clock."` (+ terrain fragment until aligned) |
| inside the sector, large azimuth error | `"Come left."` / `"Come right."` |
| inside the sector, small azimuth error | `"A bit left."` / `"A bit right."` |
| outside the elevation gate | `"Higher."` / `"A little lower."` — combined into one utterance with the azimuth word when both fire |
| inside **both** gates | `"Lined up."` once, then **silence** |
| `disengage` | `"Attack run off."` |
| target record gone (Decision 13) | `render_lost_contact` |
| tier 2 — no fresh relative observation, azimuth out of alignment (Decision 17 REVISED, §19) | `"Right, obstructed."` / `"Left, obstructed."` |
| tier 2 — elevation gate fired instead (symmetric extension, flagged above) | `"Higher, obstructed."` / `"A little lower, obstructed."` |

Reuse `_format_range_km` (rounds to 0.5 km, spells `"kilometre"`), `_unit_type_display` and
`_round_enrichment_fragment` rather than new phrasing. The terrain fragment is **acquisition only**
and stops at `"lined up"` (§8).

**Two tiers, two vocabularies (Decision 17 REVISED, §19) — struck note below the table is kept for
history.** Tier 1 speaks every row above the tier-2 rows, selected by the two threshold tables
exactly as written (Decision 11 REVISED). Tier 2 does not share that table at all: it speaks one of
the two qualified rows added above, for as long as the degraded channel holds, and nothing from
tier 1's table leaks through — no o'clock, no *"come left"*, no *"lined up"*. The renderer still
takes the tier as an argument; what changed from the struck recommendation is that tier 2 is no
longer a *subset* of tier 1's table reached by withholding one row, but a separate, narrower
rendering path selected by the same argument.

**17b. Decision 17 REVISED, amended (2026-10-15 sortie, §5/§8) — `", obstructed"` is no longer the
qualifier for *every* tier-2 cause.** Tier 2's two-vocabulary structure above is unchanged and
stands; what changes is the qualifier it appends. The sortie found the attack target rejected at the
**`range_or_size`** gate, never at `cockpit_mask`, crossing at ~2,330 m — exactly
`7 m / LOWRES_ANGULAR_RADIUS_RAD` — so *"obstructed"* was spoken for a target in plain sight that
Petrovich's naked eye genuinely could not resolve. Per user direction (§8, *"'...obstructed' for DCS
LOS, be it terrain or buildings"*), the word's **only** remaining caller is a fresh
`live_los_clear is False`; the cockpit mask goes **silent** (§2) and range/size changes optic (§6/§7)
or falls back to `speech._spoken_age_phrase`. Replacement:
`plans/attack-run-sortie-fixes/plan.md`, `[[BL-B70]]`/`[[BL-B71]]`.

> ~~**One vocabulary, two tiers (Decision 17).** Every row above is spoken in either tier except
> *"a bit left"* / *"a bit right"*, which **tier 2 withholds** — its ~3.9° residual cannot support a
> word that means "you are within a few degrees". The renderer takes the tier as an argument and
> selects the threshold table; it does not have a second code path, and the withheld row is a table
> entry, not a branch (Decision 11 REVISED, rule 3).~~ *(Superseded by §19 — see above.)*

---

### Implementation Plan

> **Restaged 2026-10-14 (amendment pass).** §18's relative observation did not exist when this was
> first staged, and §15 settled the gaze claim, which is a *precondition* of the guidance loop
> rather than a follow-on. Stage 1 is unchanged; a new Stage 2 builds the perception datum; the old
> Stage 6 gaze claim folds into the new Stage 5; the degraded tier becomes its own stage because it
> is the part that cannot be observed in the cockpit without the log. **Flyable** below means
> "produces something the pilot can hear or see"; the original staging's seven-word labels are kept
> so the two can be diffed. The old numbering is given per stage.

**Stage 1 — selection, drop, and the standing-mode intent. Flyable.** *(was Stage 1)*
`TaskKind` gains `"attack_target"`; `tools.attack_target_task` mirrors `watch_contact_task`;
`select target <what> <where>` resolves per Decision 14, sets the target to `"priority"` and the
group to `"watch"`, creates the task, and reads back. `drop target` cancels it (attention reset is
free via `tools.cancel_task`), as does the existing `cancel`/`stop`. `_describe_task_for_speech`
gains its branch. Audio-adapter tokens, phrases and slot parsers land here.
*Observable:* a readback, and the target going orange in the eyesight view.

**Stage 2 — the ownship-relative observation channel (Decision 16). No cockpit observable.** *(new)*
`Cluster.centroid_alt_m`; `RelativeDirection` on `Observation` and `Percept`;
`naked_eye_source` populating it from truth-to-truth geometry for an admitted cluster with
`live_los_clear is True`; `estimation.RELATIVE_DIRECTION_SIGMA_DEG = 0.0` and its identity-at-zero
perturbation; the grep test fencing the field to `percept.py` and `attack_run.py`. Belief stores it
and **nothing reads it** — this stage is deliberately inert, per this project's pattern of building
the mechanism before anything switches on. Its acceptance is the test suite plus one detection-trace
field, not the ear.

**Stage 3 — the alignment derivation and renderers, pure and unwired. No cockpit observable.**
*(was Stage 2)*
`geometry.signed_angular_delta_deg` and `geometry.alignment_direction`; `attack_run.py`'s
`AttackRunState`, the two-gate evaluation, the register switch, the change-driven emit rule, and the
`render_alignment_*` family, **tier as an argument** with the two threshold tables (Decision 11
REVISED). Fully unit-tested against hand-built ownship/contact fixtures, including an **oblique**
heading and a **banked** case (the bank-stabilisation claim is a trig no-regression claim, and
axis-aligned angles cannot prove it), plus a case that pins the ≤1-poll re-rotation: the same
`RelativeDirection` against two headings 9° apart must yield azimuths 9° apart. `drain_attack_run`
exists but is not called from any poll loop.

**Stage 4 — `step`. Flyable.** *(was Stage 3)*
All four directions on the ordering primitive from Stage 3, the group-scoped candidate set, the
remembered descriptor, the stop-at-the-end rule, and the ungrouped and single-member cases.

**Stage 5 — wire the guidance loop, tier 1 only, *and* claim the gaze. Flyable, and this is the
acceptance sortie.** *(was Stage 4 + Stage 6)*
`engage` / `engage target` / `disengage`; `drain_attack_run` called from `_run_crew_text_poll_loop`
immediately before `drain_events`, reading `scheduler.busy_until_sim`; `AttackRunState` carried on
the runner; the `_WATCHED_ONLY_KINDS` suppression gate in `callouts.py` (Decision 5); the
Decision 13 end conditions. **Plus the gaze claim** (Decision 9 REVISED): a branch in `_active_gaze`
ahead of the `scan_area` loop returning the target's own one-leg `commanded_legs` or a `fixed_look`,
for the run's duration only. With no fresh relative observation the run **holds its last spoken
state and stays silent** — tier 2 does not exist yet, so this stage cannot produce a wrong callout
from stale belief. Add the attack-run target, the tier, and the current azimuth/elevation error to
the speech log, so a sortie can be triaged afterwards instead of recalled.

*Why the gaze claim belongs here and not after:* without it, tier 1 is the exception rather than the
rule under any standing scan, and under `scan left` it never holds at all — so an acceptance sortie
flown before it would be measuring the fallback while believing it was measuring guidance.

**Stage 6 — tier 2, the degraded fallback (Decision 17 REVISED, §19). Flyable, and now audibly so
— moved from "acceptance is the log" by the amendment pass.** *(new)*
Projection from world-anchored belief plus the remembered relative height, and the qualified
utterance (`"right, obstructed"` / `"left, obstructed"`, and the vertical analogue) that replaces
the struck coarse-register-restriction/sticky-band mechanism. This stage was originally staged as
"hard to observe by ear by design — a correctly-built tier transition makes no sound", because the
transition *was* designed to be silent. That is no longer true: the qualifier is audible by
construction, so the tier change can be heard directly. Acceptance is therefore the same shape as
Stage 5's — fly an occlusion into the run (a vehicle slipping behind a berm mid-attack is the
realistic trigger; see Risks) and listen for *"obstructed"* to appear and disappear — with the
speech log kept as the way to confirm both axis errors per utterance, not as the only evidence the
stage worked.

**Stage 7 — projected position for a moving target (Decision 10). Flyable; acceptance is the log.**
*(was Stage 5)*
Now strictly a tier-2 concern: tier 1 is a live look and never needs projection. That makes this
stage smaller than first planned and removes its only interaction with tier 1.

Run `ruff format`/`ruff check`/`mypy --strict`/`pytest` in **both** body-layer and audio-adapter from
inside each subproject (`mypy` config discovery is CWD-only).

---

### What a sortie must decide

*Added in the amendment pass — Decision 7 referenced this section and the first pass never wrote it,
so the pointer dangled. Four questions, none answerable by analysis:*

1. **`ATTACK_RUN_LINED_UP_AZIMUTH_DEG`** — does 5.0° read as "pointed at it" in a crosswind, or does
   Petrovich talk through a correctly-crabbed run (§5)?
2. **`ATTACK_RUN_CHANGE_THRESHOLD_DEG`** — does 3.0° produce a usable cadence, or does a slow steady
   drift stay silent while the aggregate error grows (§10's own named risk)?
3. **`ATTACK_RUN_ELEVATION_GATE_DEG`** — at 10.0° the vertical word may never fire. If it does not
   discriminate, narrow it; Decision 11 REVISED makes that a value change (§17).
4. **`RELATIVE_DIRECTION_SIGMA_DEG`** — does guidance feel uncannily precise at 0.0? The speech log
   carries the tier, so tier 1 and tier 2 runs are separable in one pass.

The log is what makes all four answerable from one flight rather than recalled: Stage 5 writes the
target, the tier, and both axis errors per utterance.

---

### Risks & Unknowns

- **Position freshness: largely answered for the run itself, still live for acquisition.** The
  original risk (below) was that the target sits in the 12 o'clock cone only 2 s in every 8 s under
  `FREE_SCAN_PLAN`, so belief is up to ~8 s stale — ~3.7° at 1 km for 8 m/s armour, the same order
  as the lined-up band. **With the gaze claimed from Stage 5 and the relative observation re-derived
  against current attitude every poll, the run's own staleness falls to ≤1 poll (~1.7° at 1 km worst
  case, ~0° flying at the target).** What survives:
  - **The acquisition phase, before `engage`**, is unchanged: `select target` and `step` both read
    world-anchored belief, at up to ~8 s of staleness, and the first readback can therefore name an
    o'clock the pilot does not see. The pilot's recourse is another `step`, which is the spec's own
    mechanism.
  - **Tier 2 re-inherits it in full**, on top of the ~3.9° bias residual (Decision 17). The two
    compound, which is the quantitative case for tier 2's narrower vocabulary (Decision 17 REVISED)
    rather than reasoning in the abstract.
  - **The sortie can now separate the two questions**, which the original risk said it could not:
    the speech log carries the tier, so "the band is too narrow" and "the belief was stale" are
    distinguishable after one pass rather than confounded.
- **`scan left` + `engage` leaves the target never looked at**, because `_SECTOR_LEGS["left"]` has no
  12 — **closed by §15 and Stage 5**, which is the case that settled the gaze claim. No acceptance-card
  workaround is needed any more. Worth keeping in the record because it is the concrete argument,
  not an abstraction.
- **A single occluded group member silences tier 1 for the whole cluster.** This is the dominant
  tier-flap mechanism and it is in `naked_eye_source._acquire_every_poll`: a cluster emits this poll
  only if **all** its members are currently visible. One vehicle of a three-vehicle group slipping
  behind a berm therefore drops the relative observation for the *selected* target too, and the run
  steps to tier 2 and its ~3.9° residual for as long as that lasts. Not a defect — the
  all-members-agree rule is deliberate and `live_los_clear` follows it for the same reason — but it
  means tier 2 is reachable far more often than "the target went behind a ridge" suggests, and it is
  why Decision 17 REVISED's narrower tier-2 vocabulary is load-bearing rather than belt-and-braces:
  the pilot will hear *"obstructed"* on a routine basis, not only on a dramatic loss of sight.
- **Guidance aims at the cluster centroid, which can be empty ground.** The attack-run target is a
  `Contact`, and a `Contact` stands for a cluster, so `RelativeDirection` is the centroid's. Three
  vehicles spread 30 m at 1 km is ~1.7° of spread — inside the band, so harmless for *alignment*,
  but it means *"lined up"* can mean "pointed between two vehicles". It also gives the undercount
  (4 records / 6 real units, measured) a vertical face: two vehicles at different ground heights
  folded into one contact have one averaged altitude.
- **The elevation gate's two purposes conflict arithmetically** — **recorded, no longer an open
  fork.** §17 declined the discrimination test and specified the two-vector mechanism instead, and
  §11 says the value is a sortie question. So the tension stands as a known consequence: at 120 m
  AGL two vehicles 1.0 km and 1.5 km out are ~2.2° apart in elevation, while a nose lofted for
  rockets is several degrees up, so a gate wide enough to ignore the loft is far wider than the
  separation it is meant to resolve. The mitigation is structural rather than numeric — Decision 11
  REVISED makes going fine-grained a parameter change, so if the flight says the wide gate
  discriminates nothing, narrowing it costs a value.
- **`BL-B61`**: at class level `Group.composition` buckets armour, SPAAG and all three SAM tiers to
  `OP_GROUPSOMETHING`, so `group_matches` test 4 does almost nothing and group identity is weaker
  than `step`'s *"stay inside the unit group"* assumes. Not a defect today; a real limit on `step`.
- **`BL-B48`**: the measured infantry cohesion bridge can merge non-infantry contacts across 6 km,
  which would let `step` walk to something nowhere near what the pilot is looking at.
- **The undercount is unfixed** (4 records / 6 real units, measured) and `collapse(group, depth)`
  does not touch it. A unit the pilot sees may be unreachable.
- **`_print`'s audio sink is a synchronous HTTP POST per line**, on the poll thread. The change-driven
  cadence plus shared occupancy is what keeps a run to a handful of utterances; if either is
  weakened the guidance loop starts blocking the poll loop. This is why Decision 7 is load-bearing
  rather than cosmetic.
- **The cluster bias anchor shifts the *believed* position when group membership changes — a
  **reporting** risk, not a guidance one.** The per-object systematic bias is hashed off
  `min(member.object_id)` of the cluster (`naked_eye_source.py:957`, a documented limitation, since
  a cluster has no stable identity to hash off). Destroying one vehicle of a group — exactly what a
  re-attack does — can therefore change the anchor and shift the world-anchored believed position by
  the bias delta: at 300 m a 20 m shift is 3.8°, enough to fire a spurious *"come left"*. **Guidance
  never reads that channel while looking** (Decision 16), so this lands on reporting, callout
  wording and group matching, and reaches the run only through tier 2. Kept here on that footing
  rather than deleted: it was raised to the user and §18 records the re-footing, and the reporting
  consequence is unaddressed by anything in `BL-14`.
- ~~**`elevation_at` depends on world-model grid coverage**~~ — **removed by Decision 4 REVISED.**
  There is no world-model elevation query in this plan any more, so neither the grid-coverage gap nor
  the measured "unit underground" error applies. The fail-open rule it justified moves to a different
  absence: no relative observation ⇒ tier 2, never a withheld *"lined up"*.
- **No DCS-internals claim is unverified here**, so no Investigator pass was needed: the geometry,
  the attitude sign conventions (user-confirmed 2026-09-17) and the damage-channel findings are all
  already recorded. The 9K113/ATGM half stays deferred — its optic does not exist
  (`perception/optics.py` declares two). **Still true after the amendment pass**: §17's claim that
  unit data carries elevation was checked against `aircraft-layer/src/schema/world_objects.py` on
  disk (per-object `altitude_m`, MSL metres), and that module's own docstring confirms the one thing
  the relative channel must *not* assume — `LoGetWorldObjects` carries **no pitch/bank/yaw**, so
  target attitude is unavailable and nothing here asks for it.
- Two subprojects change together, so a partial deploy (body-layer updated, audio-adapter not) means
  the commands are simply never recognised — silent, and worth one line in the test card.

---

### Second-order effect

`BL-14` builds two things the rest of the roadmap has been waiting on: the **advisory channel**
(deferred in general since 2026-09-24, now instantiated in its bounded, pilot-requested form) and
the **standing-mode-driven speech lane** (output whose trigger is a mode, not an `Event`). Both are
prerequisites for the deferred general advisory (*"break right"*) and for the 9K113 run, which needs
exactly this loop plus an optic that does not exist. It also **narrows rather than unblocks** the
attention-driven per-unit resolution milestone the tiers document calls for: selection and stepping
now walk belief, so that milestone's remaining job is completeness (units with no record at all),
not plumbing. And it gives the movement-keyed-uncertainty direction its first real consumer, which
is what will make that work's value measurable rather than argued.

**Added in the amendment pass — the relative channel reaches further than `BL-14`, and is filed
rather than built.** The user's own note is that the two-mechanism distinction *"likely explains why
Petrovich can point at things better than he can describe where they are"*. Reading the constants,
that looks right and is checkable: `BEARING_SIGMA_DEG`'s docstring says outright that it models
*stating* a bearing, and it is the only bearing-error model in the codebase — so every consumer that
actually wants a *relative* quantity is currently paying a describing-error it should not. Candidates,
named so they are not re-derived:

- **The 9K113/ATGM run**, which needs exactly this loop plus an optic that does not exist — it is a
  tracking task, not a describing one, and would be built on the relative channel from the start.
- **The deferred general advisory** (*"break right"*), which is pure relative direction and has no
  map content at all.
- **Terrain and world-feature references**, which are the opposite case and must stay on the
  world-anchored channel — *"edge of the forest"* is a map claim and the relative channel cannot
  answer it. Worth stating, because "use the better channel everywhere" is the wrong generalisation.

**This does not widen `BL-14`'s scope.** Filed as `BL-B62`, because the general version needs its own
plan: a second consumer immediately breaks Decision 16's single-consumer grep fence, which is the
fence doing the actual work, and replacing it needs a considered answer rather than deleting a test.

---

### Decisions Requiring User Input

> **Amended 2026-10-14.** All three original decisions are now **settled by the user** — §17 closed
> 1 against the discrimination test, §15 settled 2 yes, §16 settled 3 yes. They are kept below with
> their outcomes. Two new items, A and B, replaced them.
>
> **Second amendment, same day: A and B are now settled too.** §19 settled A — not as recommended
> (see Decision 17 REVISED, which replaces the struck recommendation below with the vocabulary
> mechanism the user specified). §20 settled B, confirming the assumption as planned (see Decision
> 16 item 5). Both are kept below with their outcomes, same convention as the three above. Nothing
> in "Still open" (below) is touched by either.

**A. Tier 2 speaks the coarse register only — confirm or overrule.** *(Decision 17, and it is a real
behavioural choice, not arithmetic.)* ~~The arithmetic is settled: the fallback's azimuth residual is
~1.2° at 1σ from the same aspect but **~3.9° after a quarter-turn around the target**, because the
down-range bias (3.2× larger in metres) rotates into cross-range — 78% of the 5° band at 1σ, over it
at 2σ. The question is what Petrovich does with that. **Recommendation: withhold *"a bit left/right"*
in tier 2 and make the lined-up band sticky**, so a silent tier change inside the band produces no
utterance and §7's "say nothing" stays honest. The alternative — speak the same words in both tiers —
is simpler and would occasionally have Petrovich correcting a correctly-flown aircraft in the last
seconds of a run, which is the one failure design A exists to prevent. Your call because it decides
what the pilot hears, not how it is computed.~~

> **Settled by §19, 2026-10-14 — not the recommendation above.** The arithmetic above is unchanged
> and is still the reason a mechanism is needed; the user answered with vocabulary instead of a
> restriction: tier 2 speaks `"right, obstructed"` / `"left, obstructed"`, not a withheld row inside
> tier 1's table, and the sticky band this recommendation asked for is struck as no longer needed.
> See Decision 17 REVISED.

**B. The exactness assumption, flagged as an assumption per §18's own invitation.** ~~§18's *"guide to
it exactly because we look at it"* is being planned as **v1 treats the relative direction as exact
while the look holds**, with the noise term present as `RELATIVE_DIRECTION_SIGMA_DEG = 0.0` so a value
can be given later without a rewrite. §18 itself says *"if a small error was meant from the start,
this is the line to correct"* — so this is a confirm-or-correct, not a blocker, and either answer
costs the same because the parameter exists either way. Worth knowing before you answer: at 1 km, 1°
of pointing error is 17 m, and the proposed lined-up band is 5°.~~

> **Settled by §20, 2026-10-14: as planned.** *"Relative direction while he's looking at it ->
> exact."* `RELATIVE_DIRECTION_SIGMA_DEG = 0.0` stands, confirmed rather than corrected. See
> Decision 16 item 5.

---

> **Settled by §17, 2026-10-14: the wide absolute gate, with the discrimination test declined.** The
> user did not take the fork — he specified the two-vector mechanism instead (Decision 3a) and said a
> flight decides the value (Decision 11 REVISED). The arithmetic tension the recommendation below
> rested on is real and is kept as a recorded risk, not as an open question. Kept in place because
> the measurement is the useful part.

1. **The elevation gate: a wide absolute gate, or a discrimination test?** §11 states the purpose —
   *"It's there to make me aim at the correct unit, not wrong one"* — and separately says *"the gate
   can be wide"*. The arithmetic says these pull apart: a gate wide enough that a lofted nose stays
   inside it (~10°) is far wider than the vertical separation between two candidates a few hundred
   metres apart in range (~2°), so the vertical word would almost never fire and would discriminate
   nothing. **Recommendation: the discrimination test.** Speak *"higher"*/*"lower"* when the nose's
   current elevation would put it on a *different* candidate than the selected one — which is the
   stated purpose exactly, is immune to ballistic loft whenever there is no other candidate nearby
   (the common case), and reuses the candidate set `step` already builds. The wide absolute gate is
   the cheaper Stage-2 fallback if you prefer the literal reading.
> **Settled by §15, 2026-10-14: yes.** The recommendation below was accepted and the safety trade
> accepted with it. See Decision 9 REVISED — it also moved into the wiring stage.

2. **Does an attack run claim the gaze (Stage 6)?** It would give near-continuous eyes-on — the
   tiers document's own *"target units get constant eyes-on… attention stealing behaviour when
   implemented"* — and it is the only fix for the `scan left` + `engage` blindness above. The cost
   is that Petrovich stops scanning elsewhere for the run's duration, so a threat appearing
   mid-run may go unseen. **Recommendation: yes** — the pilot asked for the run, the run is short,
   and §4's silence design leaves the channel free for a genuine threat call. Your call because it
   is a real safety trade.
> **Settled by §16, 2026-10-14: yes, no exemption.** The recommendation below was accepted
> unchanged. See Decision 8.

3. **Does `silence` spoken mid-run mute the guidance?** **Recommendation: yes, no exemption** —
   consistent with your "absolute silence" choice, and a run cannot *begin* while muted because any
   command clears silence. One line, mostly here so it is not discovered in the air.
