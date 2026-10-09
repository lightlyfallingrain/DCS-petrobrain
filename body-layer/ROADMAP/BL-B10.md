# BL-B10 — Movement detection

- [x] **BL-B10 — Movement detection — ACCEPTED 2026-09-23** #status/done on the five-fix sortie (user: *"pass on
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
  [[BL-4]]'s attention machinery than to this gate.

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
