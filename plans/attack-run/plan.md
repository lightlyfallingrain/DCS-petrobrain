# BL-14 — Attack run: target selection, step-adjust, alignment guidance, end conditions

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

**Changed — body-layer**

- `src/perception/geometry.py` — add `signed_angular_delta_deg(from_deg, to_deg) -> float` in
  `(-180, 180]`, beside its existing unsigned sibling `angular_delta_deg`; add
  `alignment_direction(...)`, a named wrapper over `body_relative_direction` (Decision 3).
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

**8. `silence` mid-run mutes guidance — no exemption.** `self.silenced` gates exactly one thing,
`_print`'s `speech_client.push_speech`, and does so for `bypass_gate=True` urgent lines too, by the
user's own explicit choice. Guidance should not be the first exception, and the overlap window is
almost empty anyway: **any recognised command clears silence**, and `engage` is a command, so a run
cannot begin while muted. The only remaining case is the pilot deliberately saying `silence` during
a run, where honouring it is the right answer. Text and overlay keep showing the guidance either
way. (Flagged below as a one-line confirmation, not a blocker.)

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

- Stages 1–4 hold **last known**, unconditionally. §7's own fallback, and correct for the stationary
  majority the position-uncertainty direction is about.
- Stage 5 adds projection, from the only inputs that exist: direction from `Group.heading_deg` (the
  sole direction-of-travel estimate in belief, group-level, held only while
  `movement_state == "moving"`, with `heading_confidence`), speed from
  `plausible_speed_mps(op_class, installation_component=)`, gated on
  `contact.motion.state == "moving"`. `motion is None` means *never observed for movement* and must
  be treated as "hold", never as "stopped" and never as "moving".
- **The projected position is passed to the alignment derivation as an argument and is never
  assigned to `Contact.position`.** Writing it back would corrupt the association gate and
  `group_matches`' displacement bound, which both read the same estimate.

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

Reuse `_format_range_km` (rounds to 0.5 km, spells `"kilometre"`), `_unit_type_display` and
`_round_enrichment_fragment` rather than new phrasing. The terrain fragment is **acquisition only**
and stops at `"lined up"` (§8).

---

### Implementation Plan

**Stage 1 — selection, drop, and the standing-mode intent. Flyable.**
`TaskKind` gains `"attack_target"`; `tools.attack_target_task` mirrors `watch_contact_task`;
`select target <what> <where>` resolves per Decision 14, sets the target to `"priority"` and the
group to `"watch"`, creates the task, and reads back. `drop target` cancels it (attention reset is
free via `tools.cancel_task`), as does the existing `cancel`/`stop`. `_describe_task_for_speech`
gains its branch. Audio-adapter tokens, phrases and slot parsers land here.
*Observable:* a readback, and the target going orange in the eyesight view.

**Stage 2 — the alignment derivation and renderers, pure and unwired. No cockpit observable.**
`geometry.signed_angular_delta_deg` and `geometry.alignment_direction`; `attack_run.py`'s
`AttackRunState`, the two-gate evaluation, the register switch, the change-driven emit rule, and the
`render_alignment_*` family. Fully unit-tested against hand-built ownship/contact fixtures,
including an **oblique** heading and a **banked** case (the bank-stabilisation claim is a trig
no-regression claim, and axis-aligned angles cannot prove it). `drain_attack_run` exists but is not
called from any poll loop.

**Stage 3 — `step`. Flyable.**
All four directions on the ordering primitive from Stage 2, the group-scoped candidate set, the
remembered descriptor, the stop-at-the-end rule, and the ungrouped and single-member cases.

**Stage 4 — wire the guidance loop. Flyable, and this is the acceptance sortie.**
`engage` / `engage target` / `disengage`; `drain_attack_run` called from `_run_crew_text_poll_loop`
immediately before `drain_events`, reading `scheduler.busy_until_sim`; `AttackRunState` carried on
the runner; the `_WATCHED_ONLY_KINDS` suppression gate in `callouts.py` (Decision 5); the
Decision 13 end conditions. Add the attack-run target and the current azimuth/elevation error to the
speech log, so a sortie can be triaged afterwards instead of recalled.

**Stage 5 — projected position for a moving target (Decision 10).** Flyable; hard to observe
directly, which is why its acceptance is the log, not the ear.

**Stage 6 — the gaze claim (Decision 9), gated on the user's answer.** A branch in `_active_gaze`
ahead of the `scan_area` loop, returning the target's own one-leg `commanded_legs` (the shape
`scan_clock_N` already uses) or a `fixed_look`, for the run's duration only.

Run `ruff format`/`ruff check`/`mypy --strict`/`pytest` in **both** body-layer and audio-adapter from
inside each subproject (`mypy` config discovery is CWD-only).

---

### Risks & Unknowns

- **Position freshness is bounded by the scan cycle, not the poll rate.** Target in the 12 o'clock
  cone 2 s in every 8 s under free scan ⇒ up to ~8 s stale ⇒ ~3.7° at 1 km for 8 m/s armour, the
  same order as the proposed lined-up band. A sortie cannot separate "the band is too narrow" from
  "the belief is stale" in one pass; Stage 6 is what makes them separable.
- **`scan left` + `engage` leaves the target never looked at**, because `_SECTOR_LEGS["left"]` has no
  12. Guidance degrades silently. Until Stage 6, the honest mitigation is a line in the acceptance
  card telling the pilot to cancel a standing scan before engaging.
- **The elevation gate's two purposes conflict arithmetically** — see the open decision. At 120 m AGL
  two vehicles 1.0 km and 1.5 km out are ~2.2° apart in elevation, while a nose lofted for rockets
  is several degrees up. A gate wide enough to ignore the loft is far wider than the separation it
  is supposed to resolve.
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
- **`elevation_at` depends on world-model grid coverage**, and the coarse grid has been measured
  placing a unit "underground". The vertical half fails open (Decision 4), so the failure mode is a
  missing word, never a withheld *"lined up"*.
- **No DCS-internals claim is unverified here**, so no Investigator pass was needed: the geometry,
  the attitude sign conventions (user-confirmed 2026-09-17) and the damage-channel findings are all
  already recorded. The 9K113/ATGM half stays deferred — its optic does not exist
  (`perception/optics.py` declares two).
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

---

### Decisions Requiring User Input

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
2. **Does an attack run claim the gaze (Stage 6)?** It would give near-continuous eyes-on — the
   tiers document's own *"target units get constant eyes-on… attention stealing behaviour when
   implemented"* — and it is the only fix for the `scan left` + `engage` blindness above. The cost
   is that Petrovich stops scanning elsewhere for the run's duration, so a threat appearing
   mid-run may go unseen. **Recommendation: yes** — the pilot asked for the run, the run is short,
   and §4's silence design leaves the channel free for a genuine threat call. Your call because it
   is a real safety trade.
3. **Does `silence` spoken mid-run mute the guidance?** **Recommendation: yes, no exemption** —
   consistent with your "absolute silence" choice, and a run cannot *begin* while muted because any
   command clears silence. One line, mostly here so it is not discovered in the air.
