# Body-layer — Backlog

Split out of `body-layer/ROADMAP.md` on 2026-09-27. **`ROADMAP.md` remains this subproject's source
of truth for milestone status; this file is its backlog and nothing else.**

The split is not cosmetic. Both files are in the knowledge-graph corpus, whose semantic extraction
cache is keyed per file on content, so *any* edit re-extracts the whole file through an extraction
subagent. `ROADMAP.md` was ~21,900 words — 11,700 of stable milestone history plus 8,600 of backlog
that changes almost every merge — so adding one backlog line re-billed the milestone history too.
Apart from the cost, 1,900 lines was more than anyone wanted to scroll to find an open item.

Item IDs are unchanged and stay `BL-B<n>`; see root `CLAUDE.md`, "Backlog Management", for the
never-reuse rule. Numbering continues from the highest here, not from a count.

Items here are `BL-B<n>`. A new one takes the next unused number; numbers are never reused or
renumbered, `[x]` items included (root `CLAUDE.md`, "Backlog Management").

- [ ] **BL-B1 — Threat-database follow-on extraction: search/track radar + acquire time — raised
  `plans/watch-reporting/plan.md` Decision 4f-iii, 2026-09-24.** The Hoggit source page (saved
  beside `body-layer/data/threat_envelopes.json` for exactly this) carries `Track RADAR`/`Search
  RADAR` columns with HARM codes and an acquire-time column; none of it is in the extracted
  payload. Both are worth a *later* pass, not the one that just landed:
  - **Search/track radar is detection range, a different and longer claim than weapon range** —
    being tracked at 12 NM by a gun that reaches 2 NM is information, not a threat. Natural home of
    a future "he's looking at us" warning (a slewed dish is *observable*, not an omniscience
    problem) — needs a behaviour-change channel that does not exist yet, so the data would sit
    unused if extracted now.
  - **Acquire time** would decide whether a fast crossing pass actually gets engaged — needs a
    time-in-envelope model nothing in this codebase has.
  Re-extract from the already-saved HTML; no re-fetch needed.

- [ ] **BL-B2 — `OP_SRSAM`'s ~4x-7x internal range spread makes its class-level danger call early and
  often badly wrong in magnitude — recorded, not fixed, `plans/watch-reporting/plan.md` Decision
  4c, 2026-09-24.** `belief.threat._CLASS_ENVELOPES`'s derived rollup for `OP_SRSAM` is driven by
  whichever member has the longest reach in the extracted table (S-125/SA-3 at 25.0 km,
  `body-layer/data/threat_envelopes.json`) while the bucket also holds SA-8/SA-9/SA-13/SA-15, some
  under 6 km — a pilot told "danger" at 25 km for what turns out to be an SA-13 is being warned
  roughly 4-7x earlier than the real threat. Tightens automatically once type-level recognition
  resolves which member it actually is; this is a property of this project's own `op_class`
  buckets grouping systems with a wide range spread, not a defect in the belief-keyed lookup
  design, and should be recorded against the buckets (a future `object_model.py`/classification
  pass) rather than patched in `threat.py`.

- [ ] **BL-B3 — `belief.threat`'s class-level rollup only actually joined 3 of ~19 SAM/AAA threat rows into
  a class bucket on the real table — found during `watch-reporting` implementation, 2026-09-24.**
  `_derive_class_envelopes` joins `body-layer/data/threat_envelopes.json`'s `threat` names through
  `perception.object_model.profile_for` by design (Decision 4c: computed, not hand-written), but
  `object_model`'s keyword table was authored against DCS unit names, not Hoggit's wiki names, and
  most rows (Kub, Tor, Tunguska, Rapier, Roland, Chaparral, Hawk, Patriot, NASAMS, S-75, S-300, …)
  do not share a matching substring with any `_KEYWORD_PROFILES` entry, so `envelope_for` at
  `CLASS` level currently only resolves for `OP_ZU23`/`OP_SPAAG`/`OP_SRSAM` (the last via S-125
  alone) — every other SAM tier's class-level warning is silently absent until either
  `object_model.py`'s keyword table gains matching entries or `TYPE`-level recognition supplies the
  specific row directly (which already works correctly for every row, independent of this gap).
  Not a defect in the join mechanism itself (a hand-authored patch here is exactly what Decision 4c
  warns against) — the fix belongs in `object_model.py`'s own keyword coverage.

- [ ] **BL-B4 — `alt_ok` has no hysteresis counterpart to `range_ok`'s `ENGAGEMENT_LEAVING_HYSTERESIS` —
  found during the watch-reporting performance-review fix, 2026-09-24.** The short-circuit that
  skips `line_of_sight_clear` when `range_ok and alt_ok` is already `False` (performance fix,
  `contacts.py`) means any tick where ownship altitude oscillates right at `envelope.alt_min_m`
  now discards an in-progress LOS mask dwell (`los_masked_since_sim = None` on the skip path),
  which didn't happen before (LOS ran unconditionally every tick pre-fix). Traced as fail-safe,
  not a correctness bug: resetting the dwell only pushes `masked_for_s` back toward 0, which keeps
  `los_ok` (and `current_engaged`) `True` longer, never shorter — it can delay a warning clearing,
  never drop or falsely clear one. Fix (not done in `watch-reporting`, deliberately, per the fix
  review): a matching hysteresis margin on `alt_min_m` for symmetry with the range side.

- [ ] **BL-B5 — Two non-blocking hardening items from `watch-reporting`'s security deep review, deferred
  to backlog by user direction, 2026-09-24.** Both are unreachable through the code that exists
  today; recorded because the two processes that make them unreachable restart independently.
  - `body-layer/src/belief/crew_console.py:486,1009` (and the token-keyed siblings at
    `:474,477,762`) — `_CLOCK_REPORT_LABELS[clock]` is a plain dict index on a value that arrives
    over the audio-adapter -> body-layer wire. `logger._poll_transcripts` validates only that a
    `slots` value is `int | str`, not that a `clock` value is one of the nine legal forward hours.
    Change to `_CLOCK_REPORT_LABELS.get(clock, str(clock))` so an out-of-range value degrades to a
    plain number instead of raising.
  - `body-layer/src/logger.py`'s `_poll_transcripts` slot validation — add a membership check for
    `slots["clock"]` against the same forward-hour set `audio-adapter`'s `vocabulary.
    FORWARD_CLOCK_POSITIONS` names, hand-mirrored the same way `crew_console.
    _FOLLOW_DESCRIPTOR_OP_CLASSES` already is, so a wire violation is dropped at the boundary
    rather than reaching the dict index above three calls later.

- [x] **BL-B6 — `OP_LRSAM` folded into the air-defence command classes — merged 2026-09-24
  (`fix/lrsam-air-defence`).** "Watch nearest air defence" could not select an S-300:
  `crew_console._AIR_DEFENCE_OP_CLASSES` held the two gun systems and the short/medium SAM tiers
  and nothing else. The excluded contact was the worst possible one to miss — at the calibrated
  8.89 km detection range the S-300's tracking-radar mast is the furthest-detectable thing in the
  profile table, so it is both the most dangerous thing the command exists to find and the one
  most likely to be the *only* air-defence contact held at all.

  **Drift, not a decision.** The set was enumerated by hand against `perception.object_model`'s
  profile table when that table genuinely had no long-range SAM entry, and its own comment
  ("exactly the air-defence entries in `object_model`") stayed true only until the table gained
  one. Nothing connected the two. So the fix ships a guard test that recomputes the air-defence
  classes present in the profile table and asserts the command set covers them — verified to fail
  against the pre-fix set rather than assumed to — alongside the S-300 regression itself.
  `object_model` carries no structural air-defence marker to derive the set from, so the guard
  matches on `OP_*` naming and says in its own docstring that a class escaping that pattern is a
  signal to give `object_model` a real marker, not to loosen the assertion.

  Found while reading `plans/watch-reporting/plan.md`, which flagged it and deliberately left it
  unfixed; fixed on user direction ("it is air defence"). Merged as a small fix, no DoD pass.

- [x] **BL-B7 — F10 radio-menu command input for Petrovich — mechanism done, merged 2026-09-13 (merge
  `eacc45c`, `feature/f10-crew-commands`).** The player's preferred in-cockpit command UI: the
  native DCS F10 radio menu, not keybinds (F-4E-style radial wheel explicitly out of scope). A
  Hook script (`aircraft-layer/dcs-export/petrobrain-f10-commands-hook.lua`) registers
  F10 → Other → Petrovich (Watch Nearest / Scan Forward / Cancel Task) via
  `net.dostring_in("scripting", "missionCommands.addCommand(...)")` at `onSimulationStart`, polls
  selections back at 1 Hz, and forwards them over loopback UDP 7794 to the collector's
  `GET /f10_commands/poll` (drain-once queue); `logger --crew-text --f10-commands` dispatches them
  through `CrewConsole.handle_f10_command` into the same output/overlay path as typed commands.
  Prerequisite: `Saved Games\DCS\Config\autoexec.cfg` with `net.allow_dostring_in = { "scripting" }`
  (minimal set, live-confirmed). Recon: `aircraft-layer/research/2026-09-13-f10-radio-menu-command-input.md`
  Findings 7–11. **Live acceptance (user, 2026-09-13, DCS 2.9.29.27278):** menu appears and all
  three items reach body-layer, including across pause and mission restart. User verdict: "the
  commands themselves need work. But the mechanism is ok." — merged on the mechanism, command
  behaviour split into the follow-ups below. History: `plans/f10-crew-commands/` (plan, review,
  dod-check). Next-milestone impact: none on the BL sequence; it adds a second `CrewConsole` input
  surface that BL-10's audio transport can follow.

- [x] **BL-B8 — F10 command vocabulary and ownship-relative sectors — command half done, merged
  2026-09-16, merge `1a9189c` (`feature/f10-command-vocabulary`,
  `plans/f10-command-vocabulary/plan.md`).** Addresses "F10
  command refinement and specification" below for the command half of `docs/concept/
  state-transitions.jpg`'s spec — the vocabulary/geometry/wiring half, not the autonomous-behaviour
  half (deliberately out of scope, see that plan's Scope section). Widens the F10 menu from three
  flat items to 15 tokens (D4): **Scan** → Ahead/Left/Right/Full (ownship-relative) + eight compass
  **Bearing** items (absolute), **Watch** → Nearest/Nearest Air Defence, **Cancel Task**;
  `scan_forward` was *replaced* by `scan_ahead`, not kept as a synonym. **Watch → Nearest Air
  Defence** (D6) filters on the *believed* classification -- `class`/`type` level resolving into
  the air-defence `OP_*` buckets (four of them at this merge — `OP_LRSAM` was missing and was
  folded in 2026-09-24, see the entry below) -- so a `presence`-level contact is never matched even when
  the object really is a SAM; it will honestly report nothing rather than name an unidentified
  blob as air defence. New ownship-relative `AttentionArea` kind
  (`belief/attention.py`'s `RelativeSector`/`wedge_deg`/`project_relative_area`) that re-projects
  onto ownship's current heading every telemetry tick (`ContactStore.reproject_relative_areas`,
  called from `logger.py`'s `run_once` before `ingest`/`tick`) — a standing "watch left" now tracks
  the nose through a turn instead of freezing to the heading held when the button was pressed (D1-D3).
  **D5 fixes the hollowness this backlog item's live test found**: every `scan_*` token now
  registers a real `belief.tasks.PendingIntent` via `belief.tools.scan_area` *before* firing the live
  effector, wrapped so a failed trigger still leaves the task registered — `cancel_task` (previously
  always "no pending task" in `--crew-text` sessions) is no longer dead. What this milestone did
  **not** do: the spec's `Observ`/`Track` verbs (still blocked — the 9K113 OBSERV OFF control is
  still not identified, BL-6 recorded only 3001/3015; an Investigator pass is needed before that's
  plannable) and the spec's autonomous-behaviour half (weapon filtering, classification-upgrade
  reports, engagement-envelope danger/safe calls, auto-watch-on-engaged, group-as-single-threat,
  mission-lifecycle reset/debriefing — deferred to design against real sortie feedback, same
  reasoning that gates BL-8 on real flights). No live-DCS acceptance in this milestone's own DoD —
  the whole point is to enable the next sortie; that sortie is the acceptance test and feeds the
  autonomous half. Next-milestone impact: none on the BL-x sequence.

- [x] **BL-B9 — F10 Watch Nearest reply in contact-report format — done, merged 2026-09-13 (merge
  `a4e8704`, `fix/f10-watch-nearest-readback`).** Live
  2026-09-13 it replied "Watching CONTACT_1."; now `"Watching <unit type>, <clock> o'clock, <range>
  km[ <semantic fact>]."` via `speech.render_watch_nearest_readback` / `_contact_report_text`, no
  spoken id. Typed `watch <id>` readback unchanged.

- [x] **BL-B10 — Movement detection — ACCEPTED 2026-09-23** on the five-fix sortie (user: *"pass on
  preliminary test, will test and adjust more in future"*). Design settled 2026-09-20 (user),
  implemented 2026-09-22 (`plans/movement-detection/plan.md`).

  **Accepted on a preliminary reading, not a thorough one** — the user said so explicitly, and the
  distinction is worth keeping rather than rounding up to "done": what was confirmed is that moving
  units are called as moving and static ones are not, which is the behaviour the milestone exists
  to produce. The constants (`MOTION_STOP_CONFIRM_S`, `MOTION_COCKPIT_PENALTY`) remain uncalibrated
  and will move once there are more flights behind them. The velocity transport
  (`petrobrain-mission-telemetry-hook.lua` + `GET /unit_velocity/latest`), the apparent-angular-rate
  gate (`perception/motion.py`), the belief fold and event (`belief/motion.py`,
  `CONTACT_MOTION_CHANGED`), and the reporting surface (`get_situation`'s `facts["motion"]`, one
  trimmable clause in contact-report speech) are all built and unit/fixture-tested — 887 passing
  before this work, 929 after, 0 regressions. Stage 0 part 3's Mac-answerable benchmark measured
  parse->join->gate at N=300 units at ~1 ms, confirming the plan's expectation that this cost is
  irrelevant next to `check_visibility`'s own. **Not yet flown**: Stage 0 parts 1-2's own
  self-measurement (the Hook's `os.clock()`/`dcs.log` unit_count/bridge_call_ms pair, and the
  `timer.getTime()`/`LoGetModelTime()` clock-identity assumption Decision 3's skew bound depends on)
  only answer themselves on a live sortie. The diagram
  (`docs/concept/STATE_TRANSITIONS.md`) lists `moving / stopped` as a reporting trigger, and
  `docs/concept/threat-levels.md` uses motion as a danger criterion. Nothing in the built event set
  can produce either. The user's design, recorded here so it is not re-derived:

  **Take the velocity vector from unit data rather than differencing observed bearings.** This is
  deliberately omniscient at the source and the user accepts that trade for the compute it saves —
  differencing angular positions across frames means retaining history per candidate and eating the
  noise. **The omniscience is then removed by the gate, not by the source**, which is the shape this
  project already uses elsewhere: truth in, perception-limited out.

  **The gate is apparent angular change over a short interval.** For velocity `v` over time `t` the
  unit travels `s = v·t`; the angular change seen from ownship is the component of `s` perpendicular
  to the line of sight, divided by range. Movement is detected only when that exceeds a perceptual
  threshold.

  **Cheap early-out first, and cheaper than it looks.** Since `|v⊥| ≤ |v|`, the test
  `|v|·t / range < threshold` rejects a candidate with no perpendicular component and no
  trigonometry at all — one multiply and one compare. Most candidates die here.

  **Use the unit's own velocity, not its velocity relative to ownship.** A stationary truck seen
  from a moving helicopter sweeps across the field of view but does not *look* like it is moving,
  because it is static against its background; humans discount self-motion through optic flow. So
  absolute velocity is correct for ground units against terrain. The exception is anything seen
  against empty sky, where there is no static background to be judged against — the same case as the
  next paragraph.

  **The model reproduces a real human failure mode for free, and this is a feature.** A unit on a
  constant-bearing collision course produces zero angular change, so it reads as "no movement" —
  precisely the general-aviation blind spot where an aircraft on an intercept course is hard to
  see because the eye perceives no motion (user's own example). No special-casing required; it
  falls out of the geometry. **Do not "fix" it.**

  **Two further perceptual inputs the user named**, not yet designed: higher speed grabs attention
  automatically rather than merely being detectable, and **lights and flashes** do the same —
  aircraft strobes, tracers, explosions, flares. Those are an attention-capture channel, closer to
  BL-4's attention machinery than to this gate.

  **The perceptual threshold: 8 arcmin/sec (≈0.133 °/s), over a ~1 s window.** Derived on user
  direction (2026-09-20) as **2 arcmin/sec lab baseline × 4 for the cockpit**. Human smooth-motion
  detection runs about 1–2 arcmin/sec in laboratory conditions; 2 is taken as the baseline because a
  *higher* threshold means motion is *harder* to detect, so it is the conservative end. The ×4
  covers three effects that stack and that lab conditions exclude by design: canopy vibration
  smearing the image, **scanning rather than fixating**, and divided attention — a lab subject
  stares at a known location, which is the opposite of what a scanning crewman does.

  Same debt class as `BINOCULAR_OPTIC`'s ~0.67 stabilisation penalty: **the factor is not measured,
  but it is named, isolated and measurable**, rather than buried inside the threshold as a single
  unexplained number. A sortie can measure it later; until then it can be moved in one place.

  Sanity-checked against three cases before adoption, which is what makes it credible rather than
  merely arithmetic:

  | Case | Angular rate | Detected |
  |---|---|---|
  | Truck 10 m/s crossing at 2 km | 17 arcmin/s | yes |
  | Truck 5 m/s crossing at 5 km | 3.4 arcmin/s | **no** |
  | Jet 200 m/s crossing at 5 km | 137 arcmin/s | yes, easily |

  The middle row is the one that argues for the number: a slow truck at 5 km genuinely does not read
  as moving at a glance, and a threshold that flagged it would be modelling a machine, not a crewman.

  **Velocity source — resolved, and the bridge to it was already shipping (2026-09-22).**

  `Object.getVelocity()` in the Mission Scripting environment is reachable **today**, through
  machinery this project already deploys: `petrobrain-f10-commands-hook.lua` has used
  `net.dostring_in("scripting", …)` since 2026-09-13, polling at 1 Hz, and the user has flown and
  accepted it. **The "gated on probing that bridge" condition below is already satisfied**, and the
  differencing fallback — with its per-`object_id` position history, poll-interval sensitivity and
  load-bearing id continuity — is not needed. What remains unknown is the per-call cost at the rate
  movement detection would need: a performance question, not a feasibility one. The same bridge
  reaches fog, so the weather half of detection conditions is unblocked with it.
  See `aircraft-layer/research/2026-09-22-mission-bridge-already-shipping.md`, which also records
  why the false "unprobed" claim propagated into four places before anyone grepped for it.

  Original entry follows, still correct about *where* velocity lives.

  **Velocity source — resolved 2026-09-21, and not where the design assumed.**

  `LoGetWorldObjects` carries **no velocity**, under any name. Its complete per-object field set is
  `Pitch, Bank, Heading, Type, Country, Coalition(ID), GroupName, Name, UnitName, Position,
  PositionAsMatrix, LatLongAlt, Flags` — a full `pairs()` enumeration listing a dozen fields this
  project never requests, so no synonym could have hidden.
  (`LoGetLockedTargetInformation` does return a velocity vector, but only for a locked target.)

  **But `Object.getVelocity()` in the Mission Scripting environment returns a vec3 for every unit**,
  which is how Tacview records speed for everything on the map
  (`aircraft-layer/research/2026-09-21-unit-velocity-via-mission-scripting.md`). Reaching it costs
  the mission-sandbox bridge — and that bridge **also** gates the fog half of "detection under real
  world conditions", so one probe unblocks both. Filed in `todo/todo.md`.

  So there are two routes, and the design should not be fixed until the bridge is probed:

  - **Via the bridge** — an exact `v⊥` per unit. Simpler *and* more accurate: no differencing, no
    accumulated sampling noise, no per-candidate history.
  - **By differencing in the collector** — the fallback, with three concrete consequences: the
    collector must hold a previous position per `object_id`; the computed rate is sensitive to the
    poll interval; and **`object_id` continuity across polls becomes load-bearing for movement** in
    a way it is not for position.

  Note that no screenshot ladder can ever supply the perceptual threshold the way it supplied the
  detection-range constants: a still frame cannot show motion, so that constant's only calibration
  path is a purpose-built sortie.

- [>] **BL-B11 — Threat-based report prioritisation (`docs/concept/threat-levels.md`) — spec exists, mostly
  gated.** The user's own table: five priority bands (urgent / high / medium / low / ignore), what
  each does to reporting, and what counts as "dangerous to us". Raised 2026-09-20 asking where it
  fits; the answer is that it is **not one milestone** — it decomposes by what each row needs, and
  most rows are behind gates.

  **The dominant gate is coalition.** Roughly 15 of the 24 rows key on friendly/enemy/neutral/
  unknown, so they are downstream of the Coalition/IFF item below — which is itself deferred and
  needs terrain-control data `world-model` does not have. Today every contact is `UNKNOWN`, which
  collapses the table to its one unknown row.

  What the other rows need, none of which exists: unit **engagement envelopes** and "capable of
  firing at us" (also in the STATE_TRANSITIONS autonomous-behaviour backlog, with its 1.5 factor); a
  **behaviour-change channel** for "tracking us"/"engaging us" (there is none — the built event set
  is lifecycle, classification and cardinality); **terrain control** for the friendly-terrain /
  frontline / enemy-territory rows; **Mission Interpreter** output for "mission target" and escort
  targets; and a real **weapon detector** for the aimed-at-us rows, where `UrgentCall` already
  provides the mechanism and `!inject-urgent` is still the only trigger.

  **The buildable slice, and the recommended entry point: the bands themselves.** Urgent interrupts,
  high reports first, low gets the coarse form the spec writes out ("friendly ground 10 o'clock"),
  ignore is silent. This extends BL-7's relevance scoring with a band output and gives
  `belief/speech.py` a coarse rendering path. Every contact would band as `medium` today — which
  sounds useless and is not: it builds the machinery so each row lights up as its own input lands,
  rather than arriving later as one large blocked milestone with a dozen prerequisites.

  **No-omniscience constraint — corrected 2026-09-20 by the user, and the correction matters.** An
  earlier version of this entry claimed that "unit well outside its engagement envelope" and "not
  tracking self/flight" require knowing things Petrovich cannot perceive. **Both were wrong**, for
  two different reasons worth keeping distinct:

  - **An engagement envelope is knowledge, not perception.** A crewman knows what a Shilka can
    reach; it is doctrine held in the head, not a fact sensed about the particular unit. The error
    was conflating "cannot perceive X" with "cannot know X" — only the first is an omniscience
    problem, and envelopes are the second.
  - **"Tracking us" is observable.** Guns or a radar dish slewed onto you is a visible fact at
    usable range, and radar lock is a real signal. (Simplification, user: only the pilot has RWR and
    it is poor, but model it as radar lock rather than building an RWR fidelity model.)

  What survives is narrower and still binding: **envelope knowledge is keyed on unit type, so it
  inherits the classification tier.** A contact held only as `lowres` presence has no type, so there
  is nothing to look the envelope up *for*, and it cannot band above unknown/medium. The band must
  be computed from **believed** classification and carry that belief's uncertainty. Computed from
  ground truth instead, it would be an omniscience backdoor wearing a prioritisation label — and an
  invisible one, since the output would merely be unaccountably well prioritised.

  **Open question for an Investigator pass** before the tracking-us rows are built: is turret or
  dish azimuth actually exportable from DCS? `LoGetWorldObjects` gives position and heading; whether
  a unit's *turret* bearing is reachable at all is unverified, and the rule depends on it.

  Also connects to two things already recorded: "urgent units must receive automatic tracking
  status" is the auto-watch-on-engaged rule in the STATE_TRANSITIONS autonomous half, and the
  group rule ("use the highest-capability threat to determine reporting") is the threat-based member
  selection that `clustering.py` deliberately does not do.

  **Do not start without the user's instruction**, same posture as the coalition item it depends on.

- [>] **BL-B12 — Coalition/IFF for contact reports — deferred, inferred not omniscient.** Raised 2026-09-10:
  the new contact-report format (`belief/speech.py`'s `render_contact_report`) has a
  FRIENDLY/ENEMY/HOSTILE/UNKNOWN slot, always `"UNKNOWN"` for now — no coalition/IFF perception
  channel exists (`perception.association`'s own docstring: "no coalition/IFF filtering"), and
  reading `LoGetWorldObjects`'s real ground-truth coalition straight into `Contact` would violate
  the no-omniscience invariant `percept.py` enforces on purpose. **User decision: when built, infer
  coalition from unit-type vocabulary (which types each side is known to field) and world position
  (whose controlled terrain the contact sits in) — not from DCS truth.** Terrain-control data
  doesn't exist in world-model yet either. Not scoped to a specific BL-x milestone. **Do not start
  without the user's instruction.**

- [>] **BL-B13 — Parked: stop consuming DCS's ambient detection at all, own perception end-to-end.** Raised
  2026-09-09 after the PB-1.5 live probe showed DCS's ambient callout is unreadable/late/
  sight-coupled. All four open questions were answered by the user 2026-09-09 (scope channel
  stays — needed for future acquire/lock/fire gameplay, which is why the association-namespace-
  mismatch fix above mattered; suppressing DCS's own radio callout text is low-priority,
  investigate only if resumed; BL-2 is barely affected since it already consumes `Observation`s
  channel-agnostically). What's left, once those deferrals are subtracted, is not architectural:
  reclassify `visibility.py`'s naked-eye filter from "fallback" to "primary mechanism" in the
  docs, and calibrate its tier/range constants against "if the player can see a unit, Petrovich
  should too." Calibration needs live sorties, so it's meant to ride along with a milestone that's
  flying anyway rather than run standalone. **Do not start without the user's instruction.**

- [ ] **BL-B14 — Contact report fine tuning — a running list, appended to as real sorties surface things.**
  Opened 2026-09-18 from the first flights with TTS live. These are about what Petrovich *says* and
  how it sounds, not about what he believes; most touch `belief/speech.py` and
  `belief/enrichment.py` only. Grouped by what they cost.

  **Cheap — wording, in `speech.py`. ✅ All shipped 2026-09-19 (`9035317`).**
  - **Spell units out.** "m" and "km" must become "meters" and "kilometers"; TTS does not handle the
    shorthands. Note `_format_range_km` and `_round_enrichment_fragment` both currently emit them.
  - **Acronyms need spacing or expansion.** TTS reads a designation as one token. Wanted: "M I 8".
    **"SAM" is the exception** — a well-known word TTS already says correctly, so this is a
    per-token table, not a blanket rule. *Shipped: the table applies only at `type` level, and
    "SAM" is a `class`-level word, so it is structurally out of reach rather than protected by an
    exception entry. Two of this bullet's original examples were wrong and were corrected during
    implementation: "LR" occurs nowhere in the vocabulary (checked the class table and all reporting
    names) and was left out rather than given an invented use; the real string is "Mi-8", mixed
    case.*
  - **"very close" under 0.5 km.** Replaces a bare range figure at the distance where the exact
    number stops mattering and the fact of proximity starts to.

  **Cheap — thresholds, in `enrichment.py`. ✅ Shipped 2026-09-19 (`9035317`).**
  - **Within 10 m of a feature → "on the road"** (and the same for any feature reference, not just
    roads). *User correction 2026-09-19: originally written as "0 m", which a first pass read
    literally with a float-noise epsilon, leaving a 0.5-10 m gap that rendered as "near a road
    (~4 metres)". Within ten metres you are on it, and no eye resolves the difference.*
  - **Between ~10 m and ~100 m → "next to the road"**, with the side named. *Shipped without the
    side, which needs the bearing below. Note a deliberate gap: 0.5-10 m still renders as
    "near X (Nm)", disclosed in the code rather than silently rounded into one of the neighbours.*
  - These replace the current "near X (~200m)" shape entirely at short distances. The existing
    1000 m `NEAR_FACT_RADIUS_M` gate stays above them.

  **Needs world-model support — the one expensive item:**
  - **"200 meters north of the road"** and **"next to the road, north side"** both need the
    *direction from the feature to the contact*. `query.describe.RoadInfo` carries `distance_m` and
    `orientation_deg` (the road's own heading) but **no such bearing**, and neither do
    `SettlementInfo` or `WaterInfo`. So this is a `describe_position` change in world-model, not a
    phrasing change in body-layer. Given a bearing *and* the road's existing `orientation_deg`,
    "which side" falls out; without the bearing, neither does. Sequence this before the two wording
    items that depend on it rather than half-building them.

  **Deferred (user, 2026-09-19):**
  - [>] **Airborne contacts should be called "aircraft" or "helicopter"**, refining to
    fighter/bomber/attack/transport. Check what actually exists before scoping: whether the
    perception channel can tell a contact is airborne at all (candidate altitude versus terrain
    elevation is available to the naked-eye channel, but nothing currently reads it that way), and
    whether `object_model`'s `OP_*` vocabulary has air classes or needs them. This is plausibly a
    classification change rather than a speech one, which would put it outside this item.

- [ ] **BL-B15 — Petrovich's voice has no character — generic English TTS, and monotonous with it.** Deferred deliberately at
  BL-10 slice 1 (`plans/tts-voice-output/plan.md` Decision 7) rather than forgotten. macOS `say`
  ships no Russian-accented English voice (`Milena` is Russian-*language*, a different thing), and
  solving it would have expanded a slice whose point was "audible at all". Options when picked up:
  a different local engine with a suitable voice, a trained/cloned voice, or accepting a generic
  one permanently. **Delivery is a separate problem from accent** (user, 2026-09-18, on first
  hearing it): the voice is flat and evenly stressed whether it is reading a routine contact
  report or an urgent break call. Prosody may matter more for believability than the accent does,
  and it has different fixes — SSML, per-line rate and pitch, or urgency-aware templates. Cheap to try in isolation — `audio-adapter --target local --voice <name>` plays a
  line on the Mac with nothing else running, so voice auditioning costs one command per candidate.

- [ ] **BL-B16 — Cross-channel contact duplication — continuity maps are per-channel, not shared.** Found
  2026-09-10 during the object-permanence fix's live acceptance: a real civilian bus was tracked as
  two separate contacts, one per channel (naked-eye and scope/HelperAI), because each
  `PerceptionSource` instance keeps its own `object_id → observation_id` continuity map, not a
  shared cross-channel store, even though the underlying DCS `object_id` namespace is global.
  Candidate fix: a shared, cross-channel map (owned where — `belief/`? a new shared perception-layer
  component?). Not investigated or scoped yet.

- [~] **BL-B17 — `certainty`/classification fusion is last-writer-wins — classification half resolved by
  BL-2.6, certainty half still open.** `Contact.classification` no longer overwrites on last-write
  (BL-2.6's `fold_classification`). `decay.certainty_of` is still a pure function of
  `now_sim - last_seen_sim` with no notion of which contributing observation had tighter position
  uncertainty or which channel produced it — a tight naked-eye observation followed by a
  wider-uncertainty scope observation still fully resets `certainty` to `"observed"`. Reworking into
  a quality-weighted ladder is a real design question (what "better" means across channels with
  different uncertainty models), not a quick patch — revisit once real sortie data shows it actually
  degrading perceived contact quality.

- [x] **BL-B18 — BL-2.5 overlay clips its last line at 420×200 — REJECTED 2026-09-26 (user), not fixed.**
  Closed as won't-fix rather than done: the clipping is real and the candidate fix still stands
  (re-implement dynamic sizing as its own commit, separate from any cosmetic change — the fix was
  bundled with a since-reverted restyle and went back with it). The user judged it not worth
  spending on. Reopen only if a future overlay change makes it cheap or makes the clipping worse.

- [x] **BL-B19 — BL-2.5 overlay has no dismiss affordance — REJECTED 2026-09-26 (user), not fixed.** It was
  already moot while the titled window keeps its close button; the user closed it outright. It
  would only return if the borderless restyle is ever revisited, and that restyle is itself
  rejected.

<!-- BL-B20/B21/B22 arrived here with the fix/sortie-2026-09-26 merge (2026-09-27). The branch
     predated this file's split out of ROADMAP.md, so it raised them in ROADMAP.md's own Backlog
     section; the merge routed them here instead of reverting the split. Ids unchanged -- B20 was
     the next unused number here too, so nothing needed renumbering. -->

- [ ] **BL-B20 — Sector coverage — Decision 2a of `plans/sortie-2026-09-26-fixes/decisions.md`, staged out
  as a follow-on, 2026-09-26.** The user's requirement: if a scanned/watched sector holds several
  contacts, all of them should eventually get the attention needed to say what they are — not just
  re-eligibility for whichever one `choose_look` happens to land on. This is a `choose_look`
  selection-fairness redesign (least-known-first or round-robin among worth-a-look candidates), a
  different mechanism from the per-contact eligibility fix `sortie-2026-09-26-fixes` shipped
  (Stages 2/3, time-based retry). **Needs its own `/explore` pass with the user before Architect**
  (per `AGENTS.md`'s "Explore Before Deciding") — the starvation bound (what stops a 30-unit sector
  from crowding out search/react-to-threat/other watched contacts) and the give-up condition (what
  happens to a contact that genuinely cannot be resolved) are both open and need the user's
  cockpit-feel judgment, not a derived answer. Proposed plan location:
  `plans/optic-sector-coverage/plan.md` (not created yet).

- [ ] **BL-B21 — More frequent glances at a watched contact — Decision 1's third point,
  `plans/sortie-2026-09-26-fixes/decisions.md`, 2026-09-26.** The user's own framing: the durable
  fix for a watched contact staying observable is Petrovich looking at it often enough to keep the
  knowledge fresh (and learn more about it), not a longer grace window — `CALLOUT_OBSERVABILITY_
  GRACE_S` (`sortie-2026-09-26-fixes` Fix A) only covers a brief occlusion, deliberately, and must
  not be tuned as a substitute for this. The user places this under **attention-grabbing
  behaviour, which does not exist yet** in this codebase — no plan or milestone currently owns it.
  Once it exists, revisit whether `CALLOUT_OBSERVABILITY_GRACE_S` still needs to be as long as it
  is, since attention-grabbing is what is meant to make the grace window rarely matter in practice.

- [ ] **BL-B22 — Pull-only briefing-derived belief (Decision 3, `plans/sortie-2026-09-26-fixes/
  decisions.md`, 2026-09-26) — a real exception to the no-omniscience callout gate, not built.**
  The user's spec: a unit believed to be at a location per the mission briefing is legitimate
  knowledge (a crew briefing is something Petrovich perceived, before the flight), but it may
  *only* be spoken in answer to a direct player question ("where are the trucks?" -> "beyond the
  hill at 2 o'clock"), never volunteered, and only position ("roughly where"), never state
  ("doing what"). `sortie-2026-09-26-fixes`' Fix A deliberately placed its observability gate only
  on the spontaneous path (`ContactStore.tick`/`route_event`) so this can be added later as a
  separate query path through the existing `describe_contact`/`render_contact_report` machinery,
  without needing to touch or work around the gate. **Three prerequisites, none built yet**:
  briefing-derived contacts reaching belief at all (Mission Interpreter output reaching
  body-layer — see BL-7's own still-open "phase data is unreachable in a sortie" entry below for
  the sibling MI-integration gap), free-text questions (today "where are the trucks?" is a
  `fallthrough` to the brain layer, not a parsed command), and terrain knowledge to phrase "beyond
  the hill at 2 o'clock" (world-model ridge/relief query). Not actionable until at least the first
  two exist; recorded here so the constraint on Fix A's design isn't lost before this becomes
  buildable.

- **Detection under real world conditions — weather, light, vegetation.** Raised by the user
  2026-09-19, not started, no milestone assigned. **The framing matters more than the list:** every
  detection test so far has been flown in near-perfect visual conditions, which makes the current
  calibration *an upper bound on what is possible*, not a model of what usually happens. Conditions
  do not replace it; they multiply down from it.

  That gives the work the same shape as the optics split the detection-cones milestone owns, and
  the two compose cleanly rather than competing: **optics multiply apparent size up, conditions
  multiply detectability down, and the three calibrated angular thresholds stay fixed in the
  middle.** Neither needs a new acuity ladder. This is worth stating before anyone starts, because
  the obvious alternative — a separate detection model per condition — would throw away a
  calibration that cost a screenshot campaign and one invalidated merge.

  Four factors, in the order their cost-to-value argues for:

  1. **Vegetation and terrain cover — cheapest by a wide margin, because the data is already
     here.** Forest and other vegetation make ground detection hard and often impossible. World-model
     already resolves landcover (`forest`/`orchard`/`scrubland`/`open fields`/`barren`) and it
     already reaches body through `belief/enrichment.py`'s `inside_landcover` — it simply is not
     wired to `perception/visibility.py`. Nothing new has to be extracted from DCS. Note the
     asymmetry this introduces: a contact *in* forest is hard to see, and a contact *against* forest
     is a different problem again (contrast, factor 4).

     **Update 2026-09-20 — ED already does this, and decomposes it better than the sketch above.**
     `Scripts/AI/Detection.lua` sets `trees_LOS_test_T4 = true`, and all five installed theatres
     (Syria included) are Terrain-4, so **ED's AI detection samples tree geometry for line of
     sight**; our `line_of_sight_clear` samples the bare terrain mesh only, making us strictly more
     permissive through forest than the engine. Separately `background_factors[FOREST] = 0.3`, but
     the file states in capitals that background applies to **airborne targets only** — so ED models
     "hard to see an aircraft against trees" and deliberately does *not* model "hard to see a tank
     against trees" as a contrast effect. That resolves the asymmetry this bullet anticipated: the
     two halves are an **LOS term and a background term**, they apply to different target classes,
     and only the first one touches ground units.

     **First real condition measurements exist, 2026-09-26** — the user's own, in
     `docs/concept/detection-in-non-perfect-conditions.md` (low light at three sun angles, two rain
     presets, four instruments each), analysed in
     `body-layer/research/2026-09-26-condition-factors-first-analysis.md`. **They do not support
     the shape stated above.** Two findings, both structural rather than numerical: the condition
     factor varies 0.04–0.25 *within one condition* depending on which instrument is looking, so a
     scalar applied after the optic multiplier cannot express it; and the wide/narrow ordering
     **reverses** between rain and darkness, because rain attacks the *windscreen* (which the eye
     and binoculars look through and the sight does not) while darkness attacks *contrast* (where
     magnification does not help and the sight's orange filter does). The term is therefore at
     least `f(condition, optical path)`, needing a per-`Optic` property that does not exist today.
     The tiers also compress rather than scaling together — type collapses to zero for the naked
     eye in every measured rain and low-light row while class survives at short range. Also
     measured, and it closes an open question in factor 2 below: **NVG is useless for detection**
     in this aircraft. Do not re-derive the shape from this paragraph — read the analysis, which
     carries the error bands, and note the user's own caution that measurement precision itself
     degrades with the conditions being measured, which argues for a few coarse condition tiers
     rather than a continuous curve.

     **Decision 2026-09-25 (user): the two channels get two different vegetation models, and the
     split is not a compromise — it is what each channel actually is.**

     - **Naked eye and binoculars: model forest statistically.** A per-landcover-class transmission
       probability, not a geometric test. This is the honest description rather than an
       approximation of one: a sweeping unaided gaze through woods *is* probabilistic — you catch
       things through gaps, and whether you see a given vehicle depends on where you happened to be
       looking as you swept. We hold landcover polygons, not trunks; a polygon cannot answer "is
       there a tree on this exact ray", and pretending otherwise would invent geometry we do not
       have.
     - **The 9K113 sight: ask DCS for the real line of sight.** One narrow line to one target,
       pointed deliberately, usually just before shooting — the case where precision is worth a
       live call, and the only channel whose per-poll call count makes one affordable.

     **Both the cost argument and the fidelity argument point the same way**, which is why this is
     worth building rather than settling for one model everywhere: the channel that cannot afford
     per-candidate DCS calls is exactly the one that does not need them, and the channel that needs
     precision makes one call per poll.

     **Three things to settle before it is built:**

     1. **Flicker is the real failure mode, and it is not a smoothing problem.** An independent
        random draw per poll makes a contact strobe in and out at 5 Hz — Petrovich repeatedly
        reporting and losing the same thing. The draw must be **stable per contact-and-geometry**,
        re-rolling only when something meaningful changes (ownship moves enough, the contact moves,
        the gaze shifts). A seeded, deterministic draw is required rather than preferred:
        everything in this subproject must be replayable with no live DCS session, which an
        unseeded draw breaks.
     2. **The two models will disagree, and that is correct.** Naked eye glimpses something the
        sight finds blocked, or the reverse — both are real. What must never happen is one channel
        contradicting *itself* between consecutive polls, which is (1) restated as an invariant.
     3. **A live-DCS LOS call inside a perception gate fights the no-live-DCS testability rule.**
        The shape that survives it: DCS LOS as an *additional* gate on the sight channel only,
        layered over world-model's offline primitive rather than replacing it, with the offline
        answer as the fallback when the bridge is unavailable and the recorded answer used on
        replay. `query.line_of_sight` stays authoritative everywhere else, including Mission
        Interpreter's own use of it.

     **Prerequisite, gating only the second half: does `land.isVisible` actually test trees, or only
     the terrain mesh?** Unverified — ED's *AI detection* sampling tree geometry
     (`trees_LOS_test_T4`) is a different claim from the *scripting API* doing so, and this
     project's rule is not to design against an unverified DCS-internals claim. `land.getIP` may be
     the more useful call, since it returns where the ray was blocked and so distinguishes a ridge
     from a treeline 200 m short of the target. The transport is not in question —
     `net.dostring_in("scripting", …)` has been in production since 2026-09-13 — but per-call cost
     at realistic candidate counts, and whether a result returns synchronously or needs a side
     channel, are both open (the same two questions left unanswered when the mission-bridge probe
     item was closed). **Needs an investigator pass plus a probe on the Windows box, run before the
     9K113 slice is scoped rather than during it.** If the answer is terrain-only, the sight half
     has nothing to call and the statistical model has to cover every channel.

     Calibration cost is small and composes with the conditions campaign rather than adding to it:
     one transmission number per landcover class, obtainable from a screenshot ladder rather than
     from flying.
  2. **Light level — dawn, day, dusk, night.** The user: *"light/dark/dusk matters immensely."*
     Mission time and sun elevation are the inputs; the effect is large and non-linear, and dusk is
     the interesting case rather than full night, because full night is nearly a binary. Needs a
     decision on whether Petrovich has any low-light aid at all.

     **Update 2026-09-20 — the inputs need no new channel.** `Export.lua` ships
     `LoGetMissionStartTime()` and `LoGetModelTime()` (both documented in the installed file), so
     time of day is already reachable on the existing telemetry path. With the mission date (the
     Mission Interpreter already parses it from the `.miz`) and ownship lat/long (already in
     telemetry), sun elevation is ordinary astronomy computed locally — **no Hook, no
     `net.dostring_in`, no new transport.** That makes this factor materially cheaper than factor 3
     and fully independent of it, which was not true when the four were first ordered.
  3. **Weather — visibility, fog, precipitation, cloud.** ~~**Needs an investigator pass
     first**~~ — **the pass is done (2026-09-19 desk, 2026-09-20 install).** `Export.lua` exposes
     **no** weather getter beyond `LoGetVectorWindVelocity` and `LoGetBasicAtmospherePressure`;
     fog is confirmed absent from that channel, so the Hook -> mission-sandbox bridge is the only
     candidate route and its reachability is still unprobed. ED's own fog is a **time series**
     (`fog2.manual = {{time, visibility, thickness}, ...}`), not a constant, so anything built here
     must sample rather than read once. Do not plan against assumed fields.

     There is prior art to read before inventing a curve, and 2026-09-20 made it concrete:
     `min_contrast_f` and `min_fog_transparency` are **Mi-24P HelperAI's own thresholds applied on
     top of the engine detector's outputs** (`wDetector::getContrastFactor`,
     `getMaxVisibilityDistWithFog`), while the engine's own fog term is
     `atmosphere_transparency_factor.fog_transparency_threshold = 0.085` in `Detection.lua`.
     `perception/visibility.py`'s docstring names the first two as deliberately unaddressed here.
  4. **Colour separation and camouflage — explicitly deferred by the user.** It is why units are
     painted the way they are, and it is the factor that interacts with all three above rather than
     standing alone. Do not start it with the others.

  **Do not start any of this without the user's instruction** — the note exists so that detection
  logic written between now and then leaves room for a conditions modifier instead of hard-coding a
  clear-day assumption, not as a call to build it.

- **PREREQUISITE for the detection-cones milestone: research ED's own detection and identification
  model.** Raised by the user 2026-09-19: *"ED native model should be researched in detail for
  detection and identification logic. What is there that we have not thought of, what is there that
  we are missing?"* Started as a desk pass from the Mac (forums, Hoggit, the existing
  `world-model/data/raw/dcs/2026-09-02/DCS-files.txt` listing); **the deep pass happens on the
  Windows box**, where the installed DCS tree can actually be read rather than inferred.

  **It gates the cones milestone's *later* slices rather than the whole thing** (narrowed
  2026-09-20, see the interdependence note below). The questions it answers are about dwell, scan
  pattern and range uncertainty — none of which slice 1 builds — so slice 1 can proceed without it
  and the deep read is needed before slice 2. Two of the questions it answers would change that
  milestone's design rather than its details:

  - Whether ED separates *detected / visible / type known / **distance known*** as distinct states.
    If it does, that is a near-exact analogue of our own PRESENCE → CLASS → TYPE lattice, and the
    fourth flag speaks directly to the range-uncertainty work the cones milestone owns — ED may
    already model the thing being deferred.
  - Whether ED models sensor field of view, scan pattern or dwell. That is the cones milestone's
    central mechanism, and the one part with no precedent anywhere in this codebase.

  **Desk pass done 2026-09-19** —
  `aircraft-layer/research/2026-09-19-ed-native-detection-identification-gap-analysis.md`. Four
  results worth carrying forward:

  - ~~**The movement suspicion was wrong, and that is useful.**~~ **THIS BULLET WAS ITSELF WRONG —
    corrected 2026-09-20 from the installed tree.** It said *"neither ED nor we model movement or
    dwell."* ED models both. `Scripts/AI/Detection.lua` has a `motion_factor` (detection-distance
    bonus up to 1.5x, keyed to angular speed over angular size, saturating at 10) and an aspect-
    and class-dependent detection-*time* model (1 s for a target ahead at max range, 10 s behind;
    10 s and 60 s respectively for ground units), plus a scan-time term for optic sensors. The
    desk pass reached its conclusion honestly — the Mi-24P tree genuinely contains neither term —
    but generalised from the module to the engine. Full reading:
    `aircraft-layer/research/2026-09-20-dcs-install-detection-deep-read.md` findings 2-3.

    **What survives, and matters more than the correction:** ED's motion term and our own
    movement-detection design answer *different questions* and must not be swapped. ED's ratio
    reduces algebraically to `v_perp / size` — body-lengths per second, range-invariant — and it
    asks "is this easier to spot". Ours is an absolute angular rate and asks "can the crew tell it
    is moving". ED has no moving/stopped state at all, so our design is not redundant. The
    argument for building it on crew realism rather than parity stands unchanged; only the
    "nothing to catch up to" premise is gone.
  - **ED never exposes a raw numeric range on any crew-facing channel** — only a 24-bucket range
    fragment, or nothing. That corroborates rather than merely supports moving range uncertainty
    into this milestone: ED's own AI crew does not get a number either.
  - **Weather is live-readable after all.** `world.weather.getFogThickness()` and
    `getFogVisibilityDistance()` are real getters (DCS 2.9.10+), reversing the assumption that
    weather was `.miz`-only. They live in the Mission Scripting sandbox rather than `Export.lua`, so
    they need the Hook → `net.dostring_in` → UDP bridge already proven for F10 commands — untested
    against the `"mission"` target specifically.
  - ~~**The formula is still only partly known**, and the next artifact is named: `./Scripts/AI/
    Detection.lua` … **the single highest-value thing to read on the Windows box.**~~ **DONE
    2026-09-20** — read, along with `Skill_Factors.lua` and the detector symbol tables:
    `aircraft-layer/research/2026-09-20-dcs-install-detection-deep-read.md`. Four results that
    change what slice 2 is planning against:

    - **ED models dwell and scan, with numbers.** Detection takes time; the time depends on aspect
      (6x penalty for a ground unit behind you versus ahead) and, for optics, on the ratio between
      the area being swept and the instrument's field of view. This was the part of the cones
      milestone described here as having "no precedent anywhere in this codebase." It has one now.
    - **The `min_contrast_f` hunt is closed.** The consumer is the engine's own `wDetector`, which
      `CockpitMi24.dll` constructs and calls directly (`getContrastFactor`, `isTargetDetected`);
      `Detection.lua` configures it via `wDetectorInfo::load_from_state`. So ED's two constant sets
      are **layered, not alternative** — engine detection first, module reporting filter on top —
      which is the same two-stage shape as our own `hybrid_source` -> `classification` split.
    - **Petrovich-class omniscience has a number: 27x.** `Skill_Factors.lua`'s `HUMAN_SKILL` tier
      (its own comment: *"for example, gunners on UH-1"*) multiplies visual detection distance by
      27.0 against the excellent-AI baseline, which clips against the 50 km absolute cap. This
      project is not working around an accident; it is replacing a deliberate concession.
    - **One disagreement to settle deliberately, not discover mid-build:** ED gives optics a
      *recognition* advantage over and above magnification (`recognition_distance_ratio_threshold`
      0.5 for optics vs 0.25 for the naked eye). Our 2026-09-17 calibration concluded the opposite
      — that the tiers belong to the eye and the optic only multiplies the angle. Ours is
      screenshot-calibrated on this aircraft and ED's is a game-tuning constant, so this is not a
      defect; it is a real, specific disagreement that slice 2 should decide on the record.

  **Not everything ED does is worth copying.** Our tier semantics are this project's own modelling
  choice and are already documented as never verified against ED internals; the goal is a crew
  simulation, not a reimplementation of ED's AI. The research should say plainly where adopting
  ED's approach would be wrong, and where we have reinvented something ED already does better.
  Nothing found may become a route to omniscience: a field that would let Petrovich know what a
  crew member could not perceive is unusable however readable it is.

- **Cones, calibration and the sortie are interdependent — plan it as a loop, not a chain**
  (user, 2026-09-20: *"I need the cone system to be able to tell whether detection ranges make
  sense. It's all inspect and adapt."*).

  The dependency was previously written as a chain: research, then cones; sortie, then calibration.
  That is wrong in a way worth stating, because it would have produced bad data. **Today Petrovich
  sees in every direction at once**, so a range-calibration sortie flown now measures "at what range
  does an all-seeing observer first report" — not the quantity anyone wants. The confound is exactly
  the thing cones exist to remove. And cones need flown numbers to set their own constants. Neither
  can honestly go first.

  **So the milestone gets sliced, and slice 1 is deliberately the part that needs no research and no
  prior sortie:**

  - **Slice 1 — the cone test and the optics table. DONE (2026-09-20).** `perception/optics.py`
    with an `Optic` dataclass and `within_optic_fov`; `check_visibility` takes an `optic` parameter
    and threads its magnification through the range formula.

    **It did not land as written here, and the difference matters.** This entry anticipated
    "mak[ing] the binocular default an explicit choice." The shipped outcome is the opposite: the
    **naked eye is now the default** (`UNAIDED_OPTIC`, M=1.0) and **binoculars became the explicit
    non-default choice**. The old default applied `BINOCULAR_OPTIC` unconditionally to every
    candidate — Petrovich permanently glassed-up, with binocular magnification across the whole
    cockpit-mask envelope at no cost in field of view. **Default detection range dropped roughly
    4×**, which is the largest single correction to over-detection the project has made, and larger
    than anything the cone test itself contributes.

    `BINOCULAR_OPTIC` is a Б-6 6×30 at M=4.0 — *derived* as 6× glass × a ~0.67 unstabilised-platform
    penalty, not the inherited `HelperAI.lua` constant restored — carrying a real 4.25° field-of-view
    half-angle that becomes enforceable once slice 2 can select an optic. The 9K113 was cut from this
    slice. Its figures live in `body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`, and
    the deferred backlog item is in `todo/todo.md` — filed on `main` (7a87514) as a side quest, so
    it is not visible from this feature branch.

    Full record, including a 4.0 → 8.0 → 4.0 excursion that the 2026-09-17 photographic ladder
    refuted within a commit: `plans/detection-cones-slice1/plan.md`.
  - **Slice 2 — scanning, dwell and honest range.** The attention state machine, detection as a
    process rather than a predicate, and range as a belief instead of a ground-truth figure.
    **Gated on the ED research deep pass**, because that is precisely what those questions are
    about.

  **The loop, then:** slice 1 → fly it (with BL-9 making belief-vs-truth visible) → adapt the
  constants and the FOV numbers → slice 2 once the ED read has happened. Inspect and adapt at
  milestone boundaries, which is what root `CLAUDE.md` already asks for at merges.

- **Attention direction and detection cones (much-later milestone).** Deliberately deferred, not
  started. **Now also owns range uncertainty** (moved here by the user, 2026-09-19), because that
  turned out to be the same kind of problem: a genuine perception limit that differs by optic, not a
  presentation choice. Summary of what moved, full reasoning below:

  > Count vagueness is presentation — the model may hold an exact twelve and still say "several".
  > **Range vagueness is not**: the eye cannot judge distance at these scales, which is why
  > everything that shoots far has carried a rangefinding solution. Today range reaches belief as a
  > ground-truth figure, so a brain layer asking "how far?" would get an answer no crew member could
  > give — the no-omniscience invariant leaking, which adverbs in the callout would have hidden
  > rather than fixed. The 9K113's stadiametric aide (useful to ~5 km, verify before building) means
  > certainty should *narrow* when he uses the sight. The settled rendering rule, once the belief
  > actually holds uncertainty: precision degrades with distance — "very close", a plain figure
  > close in, "about four kilometres", "eight, nine kilometres". Open: whether attention tightens
  > range — probably **no** by default, since attention does not improve the eye, unless it implies
  > he is looking through the sight.

- **Attention direction and detection cones (much-later milestone).** Deliberately deferred, not
  started. Today's channels implicitly assume Petrovich is looking everywhere at once within
  range/FOV gates. Future design: distinct optical modes (naked eye, binoculars, and the 9K113
  sight, each its own FOV/acuity/movement-tradeoff), an attention/scan state machine, a scanning loop
  interrupted periodically by a full-area sweep. Would change what feeds `Percept`/`Observation` in
  the first place, upstream of everything BL-2 built — a future perception-layer milestone, likely
  well after BL-4.

