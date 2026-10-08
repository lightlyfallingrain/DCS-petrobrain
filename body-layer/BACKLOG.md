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

  **Needs world-model support — the one expensive item. Unblocked 2026-10-05, not done.**
  - **"200 meters north of the road"** and **"next to the road, north side"** both need the
    *direction from the feature to the contact*. `query.describe.RoadInfo` carries `distance_m` and
    `orientation_deg` (the road's own heading) but **no such bearing**, and neither do
    `SettlementInfo` or `WaterInfo`. So this is a `describe_position` change in world-model, not a
    phrasing change in body-layer. Given a bearing *and* the road's existing `orientation_deg`,
    "which side" falls out; without the bearing, neither does. Sequence this before the two wording
    items that depend on it rather than half-building them.
    **`plans/terrain-feature-probing/plan.md` Revision 3, Stage 4 closed the world-model half**:
    `RoadInfo`/`SettlementInfo`/`WaterInfo`/`TerrainLineInfo` all now carry `bearing_deg: float |
    None` (direction from the feature's closest point to the query position, via `store.reader.
    closest_point_on_feature`). This bullet does **not** go to `[x]` — the two wording items above
    are body-layer phrasing and are still unbuilt; only the world-model dependency they were blocked
    on is gone.

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


- [x] **BL-B23 — `ContactStore` is never pruned, so clustering cost grows with every contact ever
  seen.** Fixed `fix/contact-store-pruning` (2026-10-02, `plans/contact-store-pruning/
  implementation.md`): `ContactStore.tick`'s eighth block now filters its `reconcile` input to
  `belief.decay.certainty_of(contact, now_sim) != "lost"` — the existing lifecycle ladder, no new
  field — rather than passing the full historical `_contacts` set. `_contacts` itself is untouched
  (a `lost` contact stays full memory, still answerable by `describe_contact`); only clustering's
  input is filtered. Re-measured at the same scale sweep: `GroupStore.reconcile` alone still costs
  0.15-403 ms across 22-1200 *total* contacts (confirms the old number), but `ContactStore.tick()`
  end to end, given 20 live contacts plus up to 1200 total (the rest long-lost), now costs
  0.15-1.4 ms flat — clustering cost tracks the live picture, not sortie length. Found by the
  Performance Reviewer during the group-cohesion pass (2026-10-01), and
  **pre-existing** — `fix/group-undermerging` only added a few per-pair dict lookups on top of a
  growth path group-reporting Stage 2 already created. `ContactStore._contacts` has no delete path
  anywhere in the class, and `tick()` passes `list(self._contacts.values())` to
  `GroupStore.reconcile`, i.e. every contact ever folded rather than the live set. So
  `_cluster_contacts`'s O(n²) pairing scales with total-ever-seen, not with how many contacts are
  actually out there.

  Measured, same pass: 22 contacts 0.17 ms, 50 0.72 ms, 100 2.96 ms, 300 24.75 ms, 500 70 ms, 800
  180 ms, 1200 406 ms — clean quadratic from 100 up. Trivial today (the 2026-10-01 sortie had 22
  objects admitted), and the point is that it is **the sortie length that drives it, not the
  threat picture**: a 90-minute mission accumulating long-LOST records reaches the 70-180 ms band
  on a 5 Hz loop, where it starts costing the pilot latency.

  Fix shape: filter `reconcile`'s input by lifecycle or age before clustering, rather than pruning
  the store itself — a LOST contact is still memory Petrovich should have, so dropping the record
  is the wrong move; excluding it from *clustering* is the right one.

  **Player-bubble interaction (`plans/player-bubble/performance.md`, 2026-10-02, MONITOR):** the
  10 km player bubble filters the *candidate* pool, not admitted contacts, and nothing beyond
  `NAKED_EYE_RANGE_CAP_M` (10 km, same value as the bubble today) could ever have reached
  `ContactStore` before the bubble existed either — so the bubble **does not reduce the rate at
  which `ContactStore` accumulates**. Whoever measures this backlog item should not assume the
  bubble changed the baseline; it will only start doing so once `NAKED_EYE_RANGE_CAP_M` and
  `PLAYER_BUBBLE_RADIUS_M` diverge (9K113 sight).

- [ ] **BL-B24 — Two close contacts can become ambiguous reacquisition candidates for each other
  after a long gap.** Found 2026-10-02 while fixing `BL-B23`, **pre-existing and not introduced by
  it**; the Reviewer recommended filing it for discoverability rather than leaving it only in a
  plan's "Notable Discoveries" and two test docstrings.

  `association_over_time`'s gate inflates with elapsed time since a contact was last seen — correct
  in itself, since a unit unobserved for two minutes could genuinely have moved. But two contacts
  roughly 17 m apart, both reacquired in the same poll after a 120 s+ gap, each fall inside the
  other's inflated gate. The plain spatial gate then has two candidates for one observation, and
  `ingest`'s anti-guessing rule treats "2+ candidates" as ambiguous — the same shape as
  `plans/contact-duplication-ambiguity-runaway/`, with elapsed-time inflation as the trigger rather
  than range-scaled sigma.

  Real traffic routes around it: naked-eye and hybrid observations both carry
  `continues_observation_id`, which resolves the pairing without consulting the spatial gate, and
  `BL-B23`'s own tests use that path for the same reason. So this is reachable mainly where an
  observation arrives *without* a continuation id. Worth establishing when that actually happens
  before sizing a fix — if it never does in production, the honest outcome is a test and a comment,
  not a change to the gate.

  Note the existing lost-and-reacquired test only ever exercised a single contact, which is why
  this had no coverage until a two-contact fixture was written.

  **Still open after `fix/contact-report-flood` (2026-10-04).** That branch muted the *audible*
  symptom of the same underlying engine — `ContactStore.ingest`'s "2+ candidates → always found a
  new contact" rule — by suppressing the spoken first-report of a merge-echo. It did not touch the
  rule, and this item's own case (two close contacts ambiguous for each other after a long gap) is
  unaffected: suppression is scoped to `CONTACT_DETECTED` and never to `CONTACT_REACQUIRED`, which
  is the path this item is about. See `plans/contact-report-flood/plan.md`.

  **Still open after `fix/redundant-group-disclosure` (2026-10-05).** That branch silences a
  `Group`'s own *first disclosure* when every current member's content already reached the pilot —
  a third, speech-layer symptom of the same underlying ambiguity, one layer up from the merge-echo
  case above. It, too, leaves `ContactStore.ingest`'s root "2+ candidates → always a new contact"
  rule untouched: nothing about which `Contact` a percept resolves to changes, only whether a
  `Group`'s opening line repeats what a member's own events already said. This item's own case
  (ambiguous reacquisition for `CONTACT_REACQUIRED`) is unaffected either way. See
  `plans/redundant-group-disclosure/implementation.md`.

- [ ] **BL-B25 — `_already_reported_member_ids` evaluates its merge-echo predicate at the current
  tick, not the tick the original suppression happened.** Found by Reviewer during
  `fix/redundant-group-disclosure` review (2026-10-05); recorded, not fixed — judged bounded and
  not a correctness issue.

  `CalloutScheduler._already_reported_member_ids` (`body-layer/src/belief/callouts.py`) decides
  whether a group member was merge-echo-suppressed by re-running `_is_merge_echo_of_earlier_
  contact` against the *current* belief state, not the state at the moment the original
  `CONTACT_DETECTED` was actually suppressed. If the earlier, plausibly-same contact has since
  gone `lost`, or the two contacts have since drifted far enough apart that
  `contacts_plausibly_same` now reads `false`, a member that *was* genuinely suppressed stops
  counting as "already reported" — and a group's first disclosure can then re-speak content that,
  strictly, already reached the pilot.

  This pushes in the opposite direction from the user's "prioritize less speaking" instruction for
  this fix (it risks one extra spoken line, never a missed one), and is scoped to the
  first-disclosure window only — it cannot cause a contact to go permanently unreported, and it is
  not a no-omniscience violation. Worth fixing only if it is ever actually heard as a real
  duplicate on a live sortie; until then, the fix would require either snapshotting the
  suppression decision at the moment it happens (a new piece of per-contact state this project has
  so far avoided adding) or accepting the current, cheaper, re-evaluated-each-tick approximation.

- [ ] **BL-B26 — `CalloutScheduler.tick` gathers each group's full member facts up to three times
  per tick, whether or not anything changed.** Found by the performance pass on
  `feature/terrain-callout-stages-345` (2026-10-05); **pre-existing to that change, not caused by
  it** — it is `group-reporting` Stage 4's scheduling-loop architecture.

  For every tracked group, every 5 Hz tick, `tick()` gathers full member facts — one
  `describe_contact` call per member, and now one `divides_between` query per member as well —
  in three separate places: scoring, candidate re-render, and `group_membership_state`'s own
  re-gather. **The "nothing changed, skip" check runs *after* the gather, not before it**, so the
  work is done and then discarded on every tick where the group is unchanged, which is most of
  them.

  **UPGRADED 2026-10-05 — the estimate below is two orders of magnitude out. Scheduled as
  `BL-11` Stage 3.** Measured against the real 738 MB `syria-full.sqlite` at the sortie's own
  scale: `describe_position` is **median 51.6 ms, 41.4 ms even on a repeat** (CPU-bound Python,
  not cold I/O), not the ~0.3 ms the figure below assumes, and one tick was observed making **47
  calls for 1,579 ms**. Worse, `WorldEnrichmentCache` **misses by construction** for exactly the
  contacts that get spoken about: its key is exact structural equality of `Contact.last_position`,
  which a re-observed contact updates every poll — 92 % hit rate overall, but
  `distinct_positions == describe_calls == cache_misses` in *every* callout-bearing tick, and a 1 m
  nudge costs the full 42 ms. Cheapest fixes, neither touching the scheduling loop this entry
  correctly assigns to Architect: memoize `describe_position` per tick on a quantised `(x,z)`, and
  quantise the cache key. Full evidence: `body-layer/research/2026-10-05-performance-review.md`.
  World-model's own half of the cost — `nearest_feature` spending 73 % of `describe_position`
  proving that 86 theatre-wide features are not nearby — is `world-model/ROADMAP.md`'s `M11`.

  **Order of magnitude, estimated rather than measured** (no live sortie log was available to the
  pass): ~15 ms/tick for 5 groups × 10 members. That is not alarming on its own, and the terrain
  qualifier adds one cheap SQL query (0.02–0.11 ms measured) to each redundant gather rather than
  creating the redundancy. Recorded because the multiplier is what matters: any future per-member
  enrichment pays 3× for nothing.

  **Escalate to Architect, not to a one-line fix.** Hoisting the changed-check above the gather
  sounds trivial and is not — scoring needs facts to decide whether the group is worth speaking
  at all, so the three gathers are not obviously redundant from inside any one of them. This is a
  scheduling-loop design question. Related: `BL-B23` was the same shape of finding (cost scaling
  with something other than the threat picture) and the fix there was to filter the input, not to
  restructure the loop.

  See `plans/terrain-feature-probing/performance-rev3.md`.

- [ ] **BL-B27 — `say again` fires on ordinary cockpit speech that was never addressed to
  Petrovich.** Found in the 2026-10-05 sortie's speech log, not reported by the pilot — four
  interruptions in 70 minutes, so it is a polish item rather than a defect that spoiled the flight.

  `"Peace."` (confidence **1.00**), `"All right."`, `"See you again."` and `"Can I sell it?"` all
  produced `say_again` — Petrovich audibly asking the pilot to repeat something that was not a
  command. `"Yes."` by contrast fell through silently, which is correct.

  **So the two non-command paths disagree**, and that is the actual bug: some unrecognised
  utterances fall through (right) and others reach the say-again band (wrong). This is the same
  class as the bare `"quiet"` phrase dropped during the `silence` work — a confident recognition of
  something that was never addressed to him — and the fix is likely a floor on what may reach the
  say-again band at all, not a threshold tweak. Do not fix it by raising `CONFIRM_FLOOR`:
  `"Peace."` scored 1.00.

  Log: `~/dcs-speech.jsonl`, and the analysis in
  `aircraft-layer/research/2026-10-05-dcs-los-first-sortie-log-analysis.md`.

- [ ] **BL-B28 — `report right` is not recognised while `report left` is.** Same sortie, 40 seconds
  apart: `"report left."` (0.83) reached `confirm`, `"report right."` (0.85) got `say_again`.

  **DIAGNOSED 2026-10-06, and it is not an asymmetry — it is a silent wrong-direction match.
  Scheduled as `BL-13` Stage 1.** Measured directly against `command_matcher.match_transcript` and
  independently re-run by the main loop:

  | transcript | result |
  |---|---|
  | `"report left"` | `token='report_bearing_e'`, ratio **0.75**, `ambiguous=True` — **reports EAST** |
  | `"report right"` | `token=None` |
  | `"scan left"` / `"scan right"` | `scan_left` / `scan_right`, 1.0 each |

  So the `confirm` the pilot heard 40 s before the `say_again` was Petrovich offering to report **a
  compass direction he was never asked about**. *"report left"* fuzzy-matched *"report east"*.
  **The left side was the dangerous one**, which is the opposite of how this entry read — a
  `say_again` is a failure the pilot can hear and correct; a confirm prompt for the wrong direction
  is one he might accept.

  **Root cause: there is no own-ship-relative frame on the report side at all.** `PHRASES` has
  `scan_left`/`scan_right`, while the report family has only cardinals, clock hours and
  `report_bearing_deg`. So the fix is not a phrase-table entry: left/right are a *where* value in
  decision 12's grammar, and this falls out of `BL-13` Stage 1 rather than needing its own change.
  Full analysis: `plans/crew-query-path/plan.md`.
  **An asymmetry between left and right in one session is a phrase-table defect, not a recognition
  accident** — the confidences are near-identical and the second is *higher*. Look directly at
  `audio-adapter/src/vocabulary.py`'s `PHRASES` and body-layer's own token handling for a missing
  right-hand form, rather than treating it as a matcher-tuning question.

  Cheap, and worth doing alongside the `describe` synonym (`plans/sortie-2026-10-05-refinements/`
  item 2) since both touch the same table.

- [x] **BL-B30 — RESOLVED 2026-10-06 by `feature/bl11-tick-cost` (`BL-11` Stages 1/2/3b), DoD
  PASSED on bench measurement; the flight is on the live-acceptance debt list.** The original
  title — "roughly 0.7 Hz against a specified 5 Hz" — was wrong in both halves, and the correction
  is recorded below under "DIAGNOSED 2026-10-05": there is **no 5 Hz specification anywhere in
  body-layer** (about 5× of the apparent gap was a constant nobody had read), and the real mechanism
  was `work + interval` rather than `interval`.

  **Measured at the fix** (`plans/bl11-tick-cost/performance-review.md`, real `syria-full.sqlite`,
  440 objects, 300 polls):

  | | pre-branch | at the fix |
  |---|---|---|
  | **realised poll period, median** | **1.33 s** | **1.000 s** (mean 1.008) |
  | poll work, median | ~330 ms | **12.6 ms** |
  | poll work, p90 / max | — / 1,736 ms | 98.6 / 1,642 ms |
  | `group_salient_ids` | ~300 ms every poll | **1.1 ms** |
  | enrichment-cache hits within a callout tick | **0 %** | **89.7 %** |
  | polls overrunning 1.0 s | — | **2.0 %** |

  `_wait_for_next_tick` realises `max(interval, work)` to within 0.1 ms. The entry's own
  prescription — *"a timing instrument around the loop is the next step, not more log reading"* —
  was **not** what resolved it: cProfile plus a bench harness at the sortie's scale did, and the
  in-flight instrument (the note's finding 0) is still unbuilt. Worth knowing, because the
  instrument would have cost a sortie and the harness cost none.

  **What this does NOT close.** The 2.0 % overrun tail is entirely `describe_position`'s unit cost
  (57–85 ms/call, identical cold or warm) and is `world-model`'s `M11`, not body-layer's. And the
  sortie's **4.98 s p90 remains unexplained** — nothing in the CPU measurements reaches it; the
  candidates are `BL-B33` and `BL-B32`, both across a subproject seam. **The median is fixed and the
  tail is not**, so the "every decay half-life and cadence constant was tuned against the wrong
  rate" concern below is now answered for the typical tick and still open for the worst case.

  (Original filing, kept because the premise's correction is the instructive part:)

  **The poll loop runs at roughly 0.7 Hz against a specified 5 Hz. HIGH — the largest
  finding of the 2026-10-05 sortie, and it degrades everything downstream of the tick.**

  Measured from two independent logs of the same flight
  (`aircraft-layer/research/2026-10-05-dcs-los-first-sortie-log-analysis.md` §2):

  | source | polls | span | median gap |
  |---|---|---|---|
  | DCS Hook (producer, for reference) | 5,534 | 5,568 s wall | **1.00 s** |
  | detection trace | 2,621 | 4,235 s sim | **1.44 s** |
  | belief-truth log | 1,340 | 4,233 s sim | **1.43 s**, p90 **4.98 s**, **max 193 s** |

  Specified 5 Hz (0.2 s), observed ~0.7 Hz — **about seven times slower** — with a 193-second window
  in which body-layer did not poll at all.

  **Pre-existing, not caused by `X-B29`.** The LOS work only made it visible, by adding a producer
  with a known, independently-logged 1 Hz cadence to compare the consumer against. There was no
  reference clock before.

  **Why it matters beyond latency**: every decay half-life, dwell and cadence constant, the
  movement-detection thresholds and the callout timing were tuned against an assumed 5 Hz tick. At a
  real 1.4 s tick they are being applied at a seventh of their intended rate — so any that "felt
  about right" in flight were calibrated against the wrong cadence.

  **Diagnose before fixing.** Candidates, none confirmed: the world-model LOS fallback (an SQLite
  query per candidate per poll, and that path carried 77 % of admissions — see `BL-B31`);
  `BL-B26`'s triple-gather in `CalloutScheduler.tick`; the detection-trace writer; LAN latency on
  the aircraft-layer poll. **A timing instrument around the loop is the next step, not more log
  reading** — the existing logs record what happened per poll, never how long the poll took.

  ---

  **DIAGNOSED 2026-10-05, and the premise above is wrong — scheduled as `BL-11` Stage 1/2.**
  Two whole-subproject passes (`body-layer/research/2026-10-05-performance-review.md`,
  `body-layer/research/2026-10-05-security-audit.md`) reached this independently, from different
  evidence.

  **There is no 5 Hz specification anywhere in body-layer.** `logger.py:999` is
  `_DEFAULT_POLL_INTERVAL_S = 1.0`, unchanged since `abf49cd` (2026-09-08); `body-layer/RUN.md`'s
  documented run command never passes `--poll-interval-s`; and this file's own `ROADMAP.md:1288`
  and `audio-adapter/ROADMAP.md:473` already call 1.0 s "the project's own default". The 5 Hz
  figure survives only in four stale **docstrings** (`logger.py:1446`,
  `belief/brain_client.py:12` and `:274`, `perception/motion.py:91`) and belongs to
  `Export.lua`'s producer rate, not the consumer. So the gap is **1.43 s against 1.0 s, ~1.4×,
  not 7×** — about 5× of it was a constant nobody had read.

  **The mechanism is `work + interval`, not `interval`.** Both poll loops end with
  `stop_event.wait(poll_interval_s)` *after* the work (`logger.py:1552`, `:1192`), so the period
  is the sum. Measured work at the sortie's own scale (440 objects, 142 contacts, against the real
  738 MB `syria-full.sqlite`): **median ~330 ms, peaks 1,736 ms** → 1.33 s period against the
  sortie's measured 1.43 s. Quantitatively accounted for.

  **The decay-constant corollary above is withdrawn.** Every half-life, dwell and cadence
  constant was tuned in flight at 1 Hz, which is what the code has always done — they were not
  calibrated against a rate the loop never had. (`perception/motion.py:91`'s *comment* does assert
  5 Hz arrival; that is a correctness question, filed separately as `BL-B34`, not a cost one.)

  **The leading hypothesis is ruled out.** The whole gate chain including world-model terrain LOS
  is **2.4–21 ms/poll for all 440 candidates** — the cheap gates reject almost everything before
  the expensive one runs. Measured independently in `world-model/research/2026-10-05-performance-review.md`
  at 43.4 ms worst case for 71 candidates, ~4 % of the interval. `BL-B31`'s closing
  "one problem seen from both ends" is answered: they are two problems. `BL-B31` stands entirely
  on its own observability merits.

  **What the 330 ms actually is**, measured not reasoned:
  1. **`perception/group_salience.group_salient_ids` — ~300 ms of *every* poll, unconditionally**,
     58 % of a 300-poll cProfile, and it was not on the suspect list above at all. `_cohesive`
     recomputes two `profile_for` lookups and two `range_m` calls **per pair** of an O(n²) loop,
     all four depending on one candidate only. Hoisting them into the `_resolvable` pass plus
     `@lru_cache` on `profile_for` measures **8.1×** (215 → 27 ms at n=440) with the returned
     `frozenset` **asserted bit-identical at every n ∈ {55,128,250,440,800}**. Pure recomputation
     removal, not an approximation.
  2. **`CalloutScheduler.tick` — up to 47 `describe_position` calls in one tick, 1,579 ms
     measured.** That is `BL-B26`, whose own estimate is two orders of magnitude out — see its
     entry.

  **The 193 s "gap" is probably not a 193-second poll.** Both logs derive poll gaps from distinct
  `t_sim` in *conditionally written* rows, so they cannot distinguish "did not poll" from "wrote
  nothing" from "sim paused". The note's own table is the proof: two consumers of the *same* loop
  report 2,621 and 1,340 polls over the same span.

  **The one open decision is the user's**: is the intended rate 1.0 s or 0.2 s? No optimisation
  closes a gap a constant opens, and at 0.2 s both findings above become mandatory rather than
  worthwhile. `gaze.FOCUS_DWELL_S = 2.0` currently sits at twice the poll period either way.

  **Where the instrument goes** (the sortie note's actual ask): wrap the five phases already
  separated in `_run_crew_text_poll_loop` with `perf_counter`, emit one line per 60 polls with
  per-phase mean/max in wall clock, and — more useful than any timing — count `len(candidates)` at
  `naked_eye_source.py:520` and `describe_position` calls per tick. Both are the multipliers and
  both are invisible in a timing number. **The one number that could re-rank the findings is the
  real per-poll in-bubble candidate count**: everything above assumes 440, and the sortie logged
  "444 distinct objects over 70 minutes" and "median 43 units in a LOS result", neither of which is
  that quantity. It is one `len()`.

- [ ] **BL-B31 — Nothing notices when the live LOS feed is absent and the offline fallback takes
  over.** Security flagged this before the flight as low/low; the flight upgraded it.

  On 2026-10-05 **only 23 % of admitted contacts used a live DCS verdict**; the other 77 % silently
  used world-model's offline SRTM primitive with the 12 m terrain tolerance the user has ruled
  obsolete for live use. Every degradation path (no feed, stale skew, malformed verdict, duplicate
  unit name) converges on "absent" — correct behaviour, and completely silent.

  It *is* visible per-poll in the detection trace's `live_los_clear`/`hour_used`/`fov_half_deg_used`
  fields, but only to someone who goes looking. A whole sortie can run on the fallback while the
  pipeline reports success.

  Wanted: something that notices — a periodic log line when the live-verdict share over the last N
  polls drops below a threshold is probably enough. **It must not become a callout**; the pilot
  cannot act on it mid-flight.

  **SUPERSEDED 2026-10-06 by the unit-id probe — the structural cause below is the wrong one.**
  `aircraft-layer/research/2026-10-06-unit-id-join-results.md`: `unit_name` is never null and never
  duplicated in either flown mission (units 50/50, statics 94/94 join by name), so the
  nameless/duplicate mechanism described below **did not reproduce in the mission it was diagnosed
  from**. The real cause is that the LOS Hook walks `coalition.getGroups()` only, so **68.8 % of
  objects are statics it never enumerates** — see `BL-11` Stage 4, rewritten. The paragraph below is
  kept because the *reasoning error* is the instructive part: it explained the range anomaly
  correctly and was still wrong about why.

  **2026-10-05 security audit — the 77 % has a structural cause, not a timing one, and it is worse
  than "unobserved".** Scheduled as `BL-11` Stage 4.

  The LOS join key is `unit_name` (`perception/naked_eye_source.py:1066`, drop at `:1118`), and
  aircraft-layer's own schema declares that field `str | None`, **`None` for scenery and statics**
  (`aircraft-layer/src/schema/world_objects.py:109`). A nameless object can therefore **never**
  receive a live verdict — not an outage, a permanent hole — and falls through to the
  building-blind SRTM primitive forever. Objects sharing a name are dropped too
  (`name_counts[name] > 1`). Buildings and statics cluster close in, which is the only explanation
  offered so far that predicts the *sign* of the sortie note's §3 anomaly correctly (no-verdict
  rows median 3,820 m vs with-verdict 6,750 m). It means the building-occlusion capability `X-B29`
  was built for is structurally unavailable for exactly the population whose occlusion matters
  most — a `5p73 s-125 ln` behind a village building gets admitted and called out.

  **Verify before acting**: `DetectionTrace` carries `object_type` but not `unit_name`, so no
  existing trace can confirm it. Add `unit_name` plus a `los_join` reason enum, fly once, reduce.

  **The observable gap is total, not partial.** `naked_eye_source.py:348/976` stamps the same
  provenance string on every naked-eye `Observation` whichever primitive gated it;
  `visibility.py:785-790`'s two branches return identical `VisibilityResult`s; and
  `Contact.live_los_clear`'s `None` — the only in-principle signal — reaches the engagement gate
  and nothing else, never `tools.py`, `belief_truth_log.py`, or any counter.

  **Which way it fails**: the engagement gate (`belief/contacts.py:1357-1366`) fails open and is
  *right* to (it over-warns about something already seen). The **admission** gate fails open into
  a weaker instrument — one that cannot see buildings and carries 12 m of terrain slack. Same word,
  different thing. Yes, contacts are admitted with no verdict at all: 11,268 of 14,703, and nothing
  records it.

  **Interaction with `BL-B30`**: if the loop is slow *because* the fallback is doing SQLite work per
  candidate, these are one problem seen from both ends and fixing availability would fix the rate.
  A hypothesis, not a finding.

- [ ] **BL-B29 — `cancel all` is not in the vocabulary.** Same sortie: `"cancel all."` (0.77) →
  `say_again`. `cancel task` and `cancel everything` exist; `all` does not. One phrase to add,
  recorded so it is not rediscovered on the next flight.
  See `plans/redundant-group-disclosure/review.md`, "Optional Refinements" (second finding), and
  `plans/redundant-group-disclosure/implementation.md`.

- [ ] **BL-B32 — `audio-adapter`'s `POST /speak` synthesizes TTS synchronously, inside the poll
  body.** Found by the 2026-10-05 performance pass
  (`body-layer/research/2026-10-05-performance-review.md`). `audio-adapter/src/server.py:190`
  synthesizes before responding, and body-layer's `push_speech` runs inside `drain_events`, inside
  the poll body — so **every spoken callout blocks perception on speech synthesis**, and it stalls
  exactly the polls right after Petrovich notices something. Magnitude unmeasured (no TTS engine in
  the agent's sandbox). Crosses the body-layer/audio-adapter seam, so it is an Architect question
  (async synthesis, or a fire-and-forget hand-off), not a local edit. Not folded into `BL-11`
  for that reason.

- [ ] **BL-B33 — The poll body makes five sequential HTTP GETs with no connection reuse, each with
  a 2.0 s timeout.** Same pass. The loopback floor is 3.4 ms, so this is not the median cause — but
  it is a **~10–20 s worst-case blocking budget on one thread**, which is the right shape for the
  2026-10-05 sortie's otherwise-unexplained p90 of 4.98 s. Dropping the `/latest` timeouts to
  0.3–0.5 s is a constant change; a shared `http.client.HTTPConnection` is the fuller fix. A stale
  `/latest` is worth nothing anyway — these endpoints have no history.

- [x] **BL-B34 — RESOLVED 2026-10-06, and the interesting half was wrong.** The three comment-only
  docstrings (`logger.py:1446`, `belief/brain_client.py:12`/`:274`) are stale and go with `BL-11`
  Stage 1. **But `perception/motion.py:91`'s "objects arrive at 5 Hz, velocity at 1 Hz" is
  CORRECT** — verified against the installed Lua rather than the plan quoting it: `Export.lua:143`
  `EXPORT_INTERVAL_S = 0.2` gates the `LoGetWorldObjects` send at `:881`, and
  `petrobrain-mission-telemetry-hook.lua:91` `POLL_INTERVAL_S = 1.0` gates the velocity send. Both
  are **producer** rates, and the bound they guard is
  `|world_objects_t_sim − unit_velocity["dcs_model_time_s"]|` — a difference between two *producer*
  sim stamps, which body-layer's own `_DEFAULT_POLL_INTERVAL_S` cannot enter. No threshold depends
  on the consumer rate.

  **Recorded at length because this comment has now been misread twice** — by `BL-B30`'s original
  premise and by this entry — each time as a claim about the poll loop. The fix was to add the
  provenance to the comment, not to change behaviour. Kept `[x]` rather than deleted so a third
  reader finds the answer instead of re-deriving it. See `plans/callout-observability-gate/debug.md`.

- [ ] **BL-B34 (original text) — Four stale "5 Hz" docstrings, and one of them is a behavioural
  assumption.**
  `logger.py:1446`, `belief/brain_client.py:12` and `:274` are comments and cost nothing but the
  misreading they already caused (`BL-B30`'s premise, and a wrong budget figure in the
  performance-reviewer's own memory). **`perception/motion.py:91` is different** — it asserts
  *"objects arrive at 5 Hz"* as the basis of `plans/movement-detection/plan.md` Decision 3, so
  movement detection may be reasoning from a sample interval five times shorter than the real one.
  That half is a correctness question for a debugger, not a cost one.

- [ ] **BL-B35 — Unbounded `response.read()` on all seven peer HTTP calls.** 2026-10-05 security
  audit. A peer (aircraft-layer, audio-adapter, brain-layer) that returns an enormous body puts it
  straight into memory on the poll thread. Fix-when-public rather than fix-now: every peer is on
  the LAN and ours. One `Content-Length` check and a cap.

- [ ] **BL-B36 — The speech log is a verbatim transcript of everything the microphone heard,
  including speech never addressed to Petrovich.** 2026-10-05 security audit. The 2026-10-05 sortie
  log contains `"Peace."`, `"All right."`, `"Can I sell it?"` — the pilot talking, not commanding.
  Harmless on this machine; this repo is **intended to go public open-source**, and a shared or
  committed log is a voice transcript of someone's living room. Wanted: either hash/omit
  non-command utterances, or make the log opt-in with that stated in `RUN.md`.

- [ ] **BL-B37 — Four `assert`s doing real runtime work in `belief/tools.py` and
  `belief/enrichment.py`.** 2026-10-05 security audit. They vanish under `python -O`, and the
  checks they perform are not developer-only invariants. Convert to explicit raises.

- [ ] **BL-B38 — `BL-B23` bounded total-ever-seen for *clustering only*; two other loops still walk
  every contact ever founded.** 2026-10-05 performance pass. `tick`'s per-contact loop and
  `ingest`'s non-short-circuiting gate scan are 6.4 ms / 0.7 ms today, so LATER — but they grow with
  `BL-B24`'s churn, and that churn is getting worse (554 contacts for 444 objects on a 70-minute
  sortie, 81 % of objects carrying 2+ contact ids). Worth re-measuring after `BL-B24`, not before.

- [ ] **BL-B39 — A log that disabled itself mid-sortie reads as a log that simply stopped.** Found by
  the `BL-11` security pass, 2026-10-06 (`plans/bl11-tick-cost/security-review.md` finding 4), and
  filed rather than fixed because it is a *reading*-side gap, not a defect in the mechanism.

  Stage 5's degrade is correct and was traced: a write failure reports once on stderr, stops trying,
  and the collector is still drained (`logger.py:1231`'s `else: records.clear()` covers the
  degraded-to-`None` case, and all six writer call sites are `is not None`-guarded). **But the file
  it leaves behind has no in-band marker.** The disk fills at `t_sim 1200`, the trace just ends, and
  a later triage reads "nothing admitted after 1200" and diagnoses a perception defect that does not
  exist.

  **That matters more here than it would elsewhere**, because post-flight log archaeology *is* this
  project's primary diagnostic method — the 2026-10-05 sortie analysis is four research notes built
  entirely on these files, and `.claude/skills/sortie-log-triage` exists to automate it. `RUN.md`
  documents the stderr line for a human; the skill has been taught the stamping/glob half but not
  this one.

  **Cheap fix**: inside the existing `contextlib.suppress`, attempt one
  `{"event": "<writer>_disabled", "t_sim": ...}` row. It fails silently on a genuinely full disk —
  which is fine, that case has the stderr line — and succeeds on the path-gone-bad case, which is
  the one that produces a plausible-looking truncation. Teach the triage skill to look for it, and to
  treat a trace with neither the marker nor a clean ending as suspect.

- [ ] **BL-B40 — The last 1.6× of `group_salient_ids`' hoist is located but not worth taking yet.**
  Found by the `BL-11` performance pass, 2026-10-06 (`plans/bl11-tick-cost/performance-review.md`),
  which **declined the code change and recorded the number instead** — filed here so the analysis is
  not lost rather than because it should be done.

  `clustering.py:195-196`'s `angular_separation_rad` rebuilds each candidate's observer-relative
  difference vector **per pair** — the one per-candidate quantity Stage 2 left inside the O(n²) loop.
  Hoisting it (keeping `atan2(|cross|, dot)` verbatim, output bit-identical) measures **8.0× at 58 k
  pairs** against the shipped 5.1×, i.e. exactly the 8.1× the original note predicted.

  **Why it is not worth doing now, with the arithmetic**: the whole term is **1.1 ms in situ**, so
  1.6× saves ~0.4 ms of a 12.6 ms poll against a 1,000 ms budget. Revisit only if the realised
  period starts overrunning — and note the pass's own finding that the ratio **saturates at 5.1×
  from ~2,500 pairs upward** and is still 5.1× at 169 k pairs, nearly double the sortie's ~96 k, so
  a bigger mission does not make this term grow back into relevance.

  **The real tail is elsewhere**: the residual 2 % of polls that overrun 1.0 s is entirely
  `describe_position` at ~57–85 ms/call, which costs the same cold, warm, 1 m apart or within one
  cell. That is a `query.describe` question, not more body-layer caching.

- [ ] **BL-B41 — The watched-group callout keeper is elected per *contact*, while what it suppresses
  is per *event*.** Found by review round 3 of `feature/sortie-refinements`, 2026-10-06, and
  reproduced independently by the main loop.

  `belief.speech.may_be_callout_keeper` picks one member of a group and `CalloutScheduler.tick`
  `_consumed`s the rest's `_WATCHED_ONLY_KINDS` events. When every member is watched and eligible
  **but the keeper happens to have no event of that kind this tick**, the peers' events are already
  consumed and the kind goes unreported for the group. Reproduced with three cohering watched members
  and motion events on the two non-keepers: nothing about movement spoken across three ticks.

  **Eligibility cannot close it** — a `(store, contact)` predicate cannot express a per-event
  question, which is why round 3's fix is correct within its remit. The answer is a **per-event
  election**.

  **Bounded, and narrower than either failure it sits between**: `CONTACT_RANGE_CROSSED`
  self-corrects when the keeper crosses the same kilometre mark a poll later, and where envelopes
  exist the widest-envelope member — the most dangerous, and the one most likely to emit
  `CONTACT_ENGAGEMENT_CHANGED` — is always the keeper, so engagement is largely self-protecting. It
  is strictly less bad than the flood it replaced (N lines per group) and than the round-2 silence it
  fixed (nothing at all, for any kind).

  **One refinement to the review's account, from the reproduction:** the observable is not
  necessarily silence. In a construction where all three members were newly watched, the group's own
  disclosure line fired for an unrelated reason, so what is actually lost is *that kind's content*,
  not every utterance. A triage reading "the group said something" is not evidence the motion report
  survived.

  **Do this together with the observability-gate interaction**, which needs the same redesign:
  `fix/callout-observability-gate` (merged, `24746f5`) skips an unobservable keeper with a bare
  `continue` while its peers are already consumed — the identical silence mode by a second trigger.
  Doing them apart means designing the per-event election twice.

- [ ] **BL-B42 — Over a dense city the LOS sightline cap binds. The population is now identified,
  and it is all worth seeing.** Found during the user's 2026-10-08 test flight of `fix/los-hook-statics`
  (`docs/acceptance/2026-10-08-los-statics-sortie-feedback.md` item 2), on first flight of the
  `BL-11` Stage 4 statics enumeration.

  Measured over Damascus: `objects_in_bubble=~200+`, `objects_in_wedge=~200+`, `cap_hit=1` against
  the 128-candidate cap — nearest-first sort, so the dropped candidates are the farthest, the right
  failure direction but a real truncation. The user's reading, **not yet measured**: *"those are
  buildings, I believe. We don't really need buildings in objects that we track, especially we
  don't need to LOS them."*

  **RESOLVED 2026-10-08, and the answer removes the filtering premise.** The user supplied the
  Damascus scan line and the mission itself (`win-mac-sync/from-windows/MI24-outpost-M03.miz`):

  ```
  objects_in_bubble=238 statics_in_bubble=182 objects_in_wedge=152 statics_in_wedge=113
  candidates=152 sightlines_computed=128 max_sightlines=128 cap_hit=1
  LOS cap bit: sightlines_computed=128 of objects_in_wedge=152 (dropped=24 farthest candidates)
  ```

  The mission's 388 statics, counted from its own `mission` Lua by category:

  | count | type |
  |---|---|
  | 120 | Soldier M4 GRG (infantry) |
  | 65 | tanks — 31 T-55, 19 T-72B, 15 T-72B3 |
  | 70 | APCs — 25 Tigr_233036, 23 BTR-80, 22 BMP-2 |
  | 8 | ZSU-23-4 Shilka |
  | 60 | parked aircraft — MiG-21Bis, SA342L, Mi-24P, MiG-29A |
  | 21 | `big_smoke` |
  | ~12 | carrier deck crew, misc |

  **Zero buildings.** `coalition.getStaticObjects` behaved exactly as documented — DCS scenery
  buildings are terrain objects with no coalition and never appeared. The user's in-flight reading
  (*"those are buildings, I believe"*) was mistaken, and filtering on it would have blinded
  Petrovich to 120 infantry, 65 tanks, 70 APCs and 8 Shilkas — the contacts the copilot exists to
  call. This is the second time this session the statics-are-decorative assumption was overturned by
  looking at the actual inventory; the first was the 2026-10-05 reversal in
  `docs/acceptance/2026-10-05-sortie-feedback.md`.

  `big_smoke` was proposed as the one droppable class (21 slots, against 24 dropped at the cap — it
  would have recovered almost exactly the deficit). **The user rejected that too, and the reason is
  domain knowledge worth recording:**

  > *"Big smoke can actually be usefull. In same way as signal smoke and signal flares, they work as
  > landmarks for referencing."*

  So smoke is a *referenceable feature* — something Petrovich can see and name to locate a contact —
  not scenery. It stays.

  **Net: nothing in this population should be filtered.** The item is therefore not "which objects
  to exclude" but **"the 128 cap is too small for a dense city"**. Still open: whether the cap rises,
  whether the budget becomes time-based rather than count-based, and whether the nearest-first sort
  plus a cap is already an acceptable answer given the dropped 24 were the farthest. The per-poll
  cost does **not** currently argue for urgency — see the cost note below.

  **Measured cost, and it decides the shape of the fix.** `bridge_call_ms` is ~2 ms over semi-open
  terrain, ~5 ms over Damascus, and **27 ms at the measured maximum** (confirmed: `sort -n | tail -3`
  gives `26.00 26.00 27.00`). An earlier reading of `max 2026` as a 2-second stall was the log line's
  **year** — `2026-10-08` leads every line. Nothing stalls.

  That maximum is the useful number. 27 ms across 128 sightlines is **~0.21 ms per sightline** (two
  engine calls each: `world.searchObjects`/`SEGMENT` plus `land.isVisible`). At 60 fps a frame is
  16.7 ms, so:

  | sightlines | est. cost | frames |
  |---|---|---|
  | 128 (today's cap) | 27 ms | ~1.6 |
  | 152 (this sortie's full wedge) | ~32 ms | ~1.9 |
  | 256 | ~54 ms | ~3.2 |

  **So the cap must not simply rise** — it is already above a one-frame budget, and covering the full
  city wedge in one poll would make the poll itself the hitch that this sortie proved it currently is
  not.

  **Proposed shape instead: amortise, don't enlarge.** Hold a per-poll budget near one frame, keep the
  nearest candidates checked every poll, and carry a **rotating offset** through the far tail so it is
  covered over successive polls rather than discarded. Far contacts gain eventual coverage at flat
  per-poll cost — strictly better than both today's truncation and a larger cap. At 1 Hz the whole
  152-candidate wedge would be covered within ~2 polls. Not yet designed or decided; this is the
  direction the cost data points at, and it needs `/explore` before an Architect pass.

  **The 5 s stutter is RESOLVED 2026-10-08: a probe Hook left deployed.** The user found it:

  > *"I think the 5s interval micro stutter may have been caused by
  > petrobrain-unit-id-join-probe-hook.lua that I had forgotten to remove. Now that I removed it, no
  > stutter."*

  Removing it ended the stutter. Worth recording honestly: that probe polls at **1 Hz**
  (`POLL_INTERVAL_S = 1.0`), not 5 s, so the felt period did not match its interval — but it does far
  more work per poll than the LOS Hook (a full unit enumeration plus `getObjectID` per unit), which
  fits a heavier, less regular hitch. The empirical result is the evidence; the period was an
  estimate.

  **The process gap is the finding, not the probe.** A probe Hook stays in
  `Saved Games/DCS/Scripts/Hooks/` until someone remembers to delete it, and while it is there it
  taxes every sortie and contaminates exactly the performance measurements a sortie is flown to take.
  Three hypotheses were tested against the real cause sitting in the Hooks directory the whole time.
  Filed as **`AC-B5`**.

  The refuted-hypothesis record below is kept, because the reasoning still holds for the LOS Hook
  itself and the measurements are the ones that cleared it.

  **What was ruled out, and why it stayed ruled out.** The user reported *"a small stutter every
  5 s"*. A full gap scan of the scan-line cadence over the whole sortie finds exactly
  **two** gaps — 7.62 s at `16:04:24.954` and 2.65 s at `16:26:56.273` — against an otherwise
  metronomic 1.004 s. Two isolated events 22 minutes apart are not a 5 s period.

  Three hypotheses tested and refuted:

  | hypothesis | refuted by |
  |---|---|
  | `Export.lua` reconnect (`RECONNECT_INTERVAL_S = 5.0`, blocking 200 ms connect) | `grep "connect failed"` empty — collector connected throughout |
  | LOS poll cost | `bridge_call_ms` max 27 ms; nothing above 100 ms all sortie |
  | LOS poll cadence | only two gaps in the sortie, neither periodic |

  Nothing in the *shipped* set injects a 5 s period (LOS Hook 1 Hz, F10 Hook 1 Hz, `Export.lua` 5 Hz)
  and nothing in it is slow — all three conclusions stand. The gap the reasoning had was that the
  deployed set was assumed to be the shipped set, and a leftover probe Hook was in it. **The lesson is
  to enumerate what is actually in the Hooks directory before reasoning about what runs on the DCS
  thread**, rather than reasoning from the repository.

  The two cadence gaps remain unattributed and are not worth chasing: two events 22 minutes apart,
  with the periodic symptom now explained.

  **Explicitly not a blocker on `BL-11` Stage 4's statics fix** — the fix under that stage is the
  enumeration itself, and this is a consequence to design for separately. Per root `CLAUDE.md`'s
  "flight feedback is captured, then explored, then planned," this goes to `/explore` with the user
  before any Architect or Implementer pass.

