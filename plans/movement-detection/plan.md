### Goal

Give Petrovich a perception-limited `moving`/`stopped` belief per contact — DCS unit velocity in at
the source, an apparent-angular-rate gate that discards it into a tri-state boolean before it can
cross into `belief/`, and a `CONTACT_MOTION_CHANGED` event as the project's first behaviour-change
channel.

The perceptual design is the user's, recorded in `body-layer/ROADMAP.md` 2026-09-20 and not
re-derived here. This plan resolves the four things it left open: where velocity enters the
pipeline, how it is batched, what "movement" is downstream, and whether attention-capture is in
this slice (it is not).

---

### Affected Modules / Files

**aircraft-layer (velocity transport — the expensive half)**

- `aircraft-layer/dcs-export/petrobrain-mission-telemetry-hook.lua` — **new.** A third Hook script,
  polling `net.dostring_in("scripting", VELOCITY_CODE)` at 1 Hz and forwarding one JSON datagram to
  a new loopback port. Not an extension of `petrobrain-f10-commands-hook.lua`: opposite data
  direction, independent lifecycle and rate, and that file's audited "exactly two fixed literal
  snippets, never built from runtime input" property is worth preserving intact. Cost: one extra
  `dostring_in` per second (see Stage 1's measurement plan).
- `aircraft-layer/dcs-export/Export.lua` — add `unit_name` (from `LoGetWorldObjects`' `UnitName`
  field) to each exported object; bump the wire-format version. This is the **join key** — see
  Decision 1.
- `aircraft-layer/src/schema/world_objects.py` — `WorldObjectSample.unit_name: str | None`
  (nullable: scenery/statics may carry no `UnitName`; tri-state discipline, never coerced to `""`).
- `aircraft-layer/src/schema/unit_velocity.py` — **new.** `UnitVelocitySnapshot` /
  `UnitVelocitySample`, mirroring `world_objects.py`'s structure: `dcs_model_time_s`,
  `received_wall_clock_s`, `samples` keyed by `unit_name`, plus the snippet's own
  `unit_count`/`bridge_call_ms` diagnostics.
- `aircraft-layer/src/collector/unit_velocity_receiver.py` — **new.** UDP listener, port 7795,
  modelled directly on `f10_command_receiver.py`.
- `aircraft-layer/src/collector/cache.py`, `__main__.py`, `api/server.py` — a
  `UnitVelocityCache` alongside `WorldObjectsCache`, and `GET /unit_velocity/latest`. **A separate
  endpoint, not merged into `/world_objects/latest`** — see Decision 2.

**body-layer — perception (the gate)**

- `body-layer/src/perception/motion.py` — **new.** The whole perceptual gate, as pure functions:
  `apparent_angular_rate_rad_s(observer, target, velocity)` and
  `is_apparently_moving(...) -> bool | None`, plus the threshold constants. No I/O, no imports from
  `belief`, fixture-testable with plain vectors.
- `body-layer/src/perception/association.py` — `WorldObjectCandidate.velocity: Vec3 | None`
  (DCS-native m/s, converted once in `from_dict` the same way `heading_true_rad` → degrees is).
  `None` = no velocity for this object this poll, which is **unknown, never "stopped"**.
- `body-layer/src/perception/source.py` — `Observation.apparent_motion: bool | None = None`.
  Perceived metadata on exactly the same footing as `classification_level` and `count_bucket`: the
  channel's own honest statement, not a truth field.
- `body-layer/src/perception/naked_eye_source.py` — fetch the velocity snapshot, pair it to the
  world-objects snapshot by sim time, run the gate for each visible candidate, stamp
  `apparent_motion`.
- `body-layer/src/aircraft_client.py` — `get_unit_velocity_latest()`.
- `body-layer/src/perception/detection_trace.py` — record the gate's inputs and verdict
  (`|v|`, `|v⊥|`, range, rate, threshold, skew) so a negative is inspectable rather than silent.

**body-layer — belief (the state and the event)**

- `body-layer/src/belief/motion.py` — **new.** `MotionBelief` (`state`, `established_sim`,
  `confidence`) and `fold_motion`, the asymmetric promote-fast/demote-slow rule (Decision 4).
  Sibling of `belief/classification.py`, same shape.
- `body-layer/src/belief/decay.py` — **consumes the already-present `MOTION_HALF_LIFE_S = 60.0`**,
  which has sat in that table unused since BL-2 with a docstring explicitly reserving it for this.
  Adds `motion_confidence_at(contact, now_sim)` next to `classification_confidence_at`, and
  `MOTION_STOP_CONFIRM_S`. **No existing constant changes value.**
- `body-layer/src/belief/contacts.py` — `Contact.motion: MotionBelief | None`, folded in
  `record()`, compared in `tick()` with `last_emitted_motion` + the existing
  `EVENT_COOLDOWN_S` bookkeeping. Touches no lifecycle/classification/cardinality logic.
- `body-layer/src/belief/events.py` — `CONTACT_MOTION_CHANGED` added to `EventKind`, and
  `motion_event_kind`, the fourth twin of `lifecycle_event_kind`/`classification_event`/
  `attention_event_kind`. (This module's docstring currently names a placeholder `CONTACT_MOVED`
  as future work; that name is superseded — see Decision 5.)
- `body-layer/src/belief/tool_api.py`, `speech.py` — surface motion in `get_situation` and allow
  one mention in contact-report text. Narrowest stage; trimmable.

**Docs**

- `body-layer/ROADMAP.md`, `aircraft-layer/ROADMAP.md`, `docs/concept/STATE_TRANSITIONS.md`
  ("**None of this exists yet**" for behaviour changes stops being true for the first row).

---

### The gate, stated precisely

Given ownship position `o`, target position `p`, target **absolute** velocity `v` (DCS m/s):

```
d = p - o ;  range = |d| ;  u = d / range
v_perp = v - (v · u) u
rate_rad_s = |v_perp| / range
moving = rate_rad_s >= MOTION_ANGULAR_THRESHOLD_RAD_S
```

Early-out first, exactly as the roadmap specifies: since `|v⊥| ≤ |v|`, if
`|v| / range < threshold` the candidate is rejected with one divide and one compare and no vector
algebra at all. Most candidates die there.

**The `t` in `s = v·t` cancels and must not appear in the code.** The ~1 s window is part of the
*derivation* of the threshold (the perceptual integration time over which 8 arcmin of displacement
must accumulate), not a term in the expression — both sides of the comparison carry the same `t`.
An implementer will naturally reach for the inter-poll `dt` here; that would make the result
poll-rate-dependent and non-deterministic across replays. The window belongs in a comment, not a
constant.

Threshold, written as the derivation rather than the product, per the `BINOCULAR_OPTIC`
stabilisation-penalty precedent:

```python
MOTION_THRESHOLD_LAB_ARCMIN_PER_S: Final[float] = 2.0   # lab smooth-motion detection
MOTION_COCKPIT_PENALTY: Final[float] = 4.0              # vibration + scanning + divided attention
MOTION_ANGULAR_THRESHOLD_RAD_S: Final[float] = math.radians(
    MOTION_THRESHOLD_LAB_ARCMIN_PER_S * MOTION_COCKPIT_PENALTY / 60.0
)  # 8 arcmin/s = 0.133 deg/s = 2.327e-3 rad/s
```

Absolute velocity, not ownship-relative (roadmap's reasoning: ground units are judged against a
static background, and humans discount self-motion through optic flow). The constant-bearing
zero-rate blind spot falls out of `v_perp` and is **not** special-cased.

---

### Implementation Plan

**Stage 0 — measure the cost before building the transport.** The only genuinely unknown quantity.
Split into three parts, because only two of them are Mac-answerable and the task's framing needs one
correction:

1. *Bridge call overhead.* Already measured in production: `petrobrain-f10-commands-hook.lua` has
   polled `dostring_in` at 1 Hz since 2026-09-13, flown and accepted. Adding a second call per
   second is a known, small, already-tolerated delta. No new measurement needed.
2. *The in-state `O(N)` loop with N `Object.getVelocity()` calls.* **This is not measurable on the
   Mac** — no DCS, no mission-scripting sandbox, and `getVelocity`'s per-call cost is the thing in
   question. Do not pretend otherwise. Instead make it **self-measuring at zero user cost**: the
   Hook wraps its `dostring_in` in `os.clock()` (available in the Hook/GameGUI environment, unlike
   the sanitised mission sandbox), and the snippet returns its own unit count as the payload's first
   field. Both go to `dcs.log` and into `UnitVelocitySnapshot`. The next sortie the user flies for
   any reason answers the question, and every later sortie keeps answering it.
3. *Python-side parse, join and gate cost at realistic N.* Fully Mac-answerable today, no DCS and no
   user: a pytest benchmark that synthesises a 300-unit velocity snapshot plus a 300-object
   world-objects snapshot, and times parse → join → early-out → gate. Write this in Stage 0 so the
   number exists before the code it justifies. Expect it to be irrelevant next to the existing
   per-candidate `check_visibility` cost; confirm rather than assume.

   Note the real risk this is guarding: the mission-scripting state runs on the **sim thread**, so a
   slow in-state loop costs frame time directly. Escape hatches, in order of preference if (2) comes
   back bad: cap units per poll; drop the poll to 0.5 Hz; filter in-state by distance from
   `world.getPlayer()`; and finally the fallback in Decision 6.

**Stage 1 — velocity transport (aircraft-layer), end to end, no body-layer changes.**
New Hook script, one fixed literal snippet enumerating `coalition.getGroups(side)` (units) plus
`coalition.getStaticObjects(side)` (zero velocity by definition, no `getVelocity` call needed),
emitting one compact string `"<timer.getTime()>|<unit_name>:<vx>:<vy>:<vz>;…"`. Sim time is
stamped **inside the scripting state with `timer.getTime()`**, never in the Hook with
`DCS.getRealTime()` — see Risks. `Export.lua` gains `unit_name`; collector gains receiver, cache and
endpoint. Acceptance: `GET /unit_velocity/latest` returns a populated, sim-stamped snapshot during a
live sortie, and `dcs.log` carries the Stage 0 timings.

**Stage 2 — the gate (body-layer perception), offline and independently landable.**
`perception/motion.py`, `WorldObjectCandidate.velocity`, `Observation.apparent_motion`, the
snapshot join, the trace fields. **This stage is a no-op without Stage 1**: velocity absent →
`None` → `apparent_motion is None` → nothing downstream changes. So Stages 1 and 2 can land in
either order, and Stage 2's tests are pure fixtures. Reproduce the roadmap's three sanity rows as
test cases verbatim — including the middle one that must read *not moving* — plus a
constant-bearing case asserting `False`, which is the design's deliberate blind spot and must be
protected by a test so a later "fix" trips it.

**Stage 3 — the belief state and the event.**
`belief/motion.py`, `MOTION_HALF_LIFE_S` finally consumed, `Contact.motion`, `motion_event_kind`,
`CONTACT_MOTION_CHANGED` through the existing cooldown machinery. Tests: promote on one
above-threshold observation; no demote until `MOTION_STOP_CONFIRM_S` of continuous sub-threshold
observation; `None` never demotes; cooldown suppresses emission without losing the transition
(the existing `last_emitted_*` contract).

**Stage 4 — reporting surface.** `get_situation` exposes motion; one clause in contact-report text.
Deliberately last and deliberately thin — the milestone's value is the belief and the event; the
wording is cheap to iterate later and should not hold up the merge.

**Seam:** between Stage 1 and Stage 2, at `WorldObjectCandidate.velocity`. Everything above that
field is source-agnostic.

---

### Decisions (resolved here, stated so they can be revisited)

**1. The join key is `UnitName`, and this is why Export.lua must change.**
The mission-scripting environment and `LoGetWorldObjects` do not share an identifier.
`LoGetWorldObjects`' `pairs()` key is an export-side index whose cross-poll stability is still
formally unconfirmed; mission scripting keys units by `Unit:getName()`. The one field both sides
demonstrably carry is the ME unit name — `UnitName` is in the roadmap's full `pairs()` enumeration
of `LoGetWorldObjects`' fields, and `Unit:getName()` returns the same string. So Export.lua exports
it and the join happens in body-layer on a string key. Positional proximity matching was considered
and rejected outright: it would fabricate associations, which is exactly the class of error
`association_over_time` exists to prevent.

*Cheaper alternative worth one probe later:* if `Object.getID()` in the scripting state equals the
export-side object id, the Export.lua change and the string join both disappear. Unverified; not
worth blocking on, since `unit_name` is additive and harmless if later superseded.

**2. Velocity gets its own endpoint; it does not ride `/world_objects/latest`.**
Merging in the collector would mean holding a world-objects snapshot back until a matching velocity
snapshot arrives, or emitting a snapshot whose two halves carry different sim times under one
timestamp — silently destroying the provenance the dual-clock schema exists to preserve. Two
endpoints, two sim stamps, an explicit join in body-layer with an explicit skew bound, keeps the
provenance boundary visible. This also keeps the two feeds independently degradable: no
`autoexec.cfg` opt-in → no velocity → motion unknown everywhere → nothing else regresses.

**3. Skew bound: `MOTION_VELOCITY_MAX_SKEW_S = 2.0`.**
Objects arrive at 5 Hz, velocity at 1 Hz, so worst-case skew is ~1 s plus transport. Beyond the
bound, velocity is dropped to `None` — **unknown, never reused as stale**. 2.0 s is tolerable
because a ground vehicle's velocity barely changes over 1 s, and anything whose velocity *does*
change materially in 1 s (aircraft) exceeds the threshold by one to two orders of magnitude anyway,
so the verdict is insensitive to the staleness.

**4. Movement is a property of an `Observation` in `perception`, and a `MotionBelief` on a
`Contact` in `belief`. Both, not either.**
The gate is perceptual — it is "what did this look like from here", the same question
`check_visibility` answers — so it belongs in `perception`, and putting it there is what enforces
the invariant: **the velocity vector never leaves `perception/`.** Only the tri-state boolean
crosses into `belief`, which is the roadmap's "omniscience removed by the gate, not the source"
expressed as a module boundary rather than a convention. `belief` then owns the *persistence* of
that judgement across polls — decay, hysteresis, event emission — because that is contact state,
not observation content. `perception` imports nothing from `belief`; the dependency runs one way,
unchanged.

The fold is deliberately asymmetric: one above-threshold observation promotes to `moving`
immediately (motion is positive evidence and you notice it at once); demotion to `stopped` requires
`MOTION_STOP_CONFIRM_S` of continuous sub-threshold observation (concluding something has stopped
takes watching it a while). This is also what stops a unit hovering at the threshold from flapping
the event once every `EVENT_COOLDOWN_S`. `None` — unobserved, or no velocity match — holds; it
never demotes and never promotes.

**5. The event is `CONTACT_MOTION_CHANGED`, not `CONTACT_MOVED`.**
`events.py` names `CONTACT_MOVED` as a placeholder for future work, but that name describes a
position change; what this milestone produces is a `moving`↔`stopped` *state* transition, which is
the shape of `CONTACT_ATTENTION_CHANGED` and `CONTACT_CARDINALITY_CHANGED`. Consistency with the
three existing twin-comparison kinds matters more than the placeholder. Local and reversible;
stated rather than escalated.

**6. Attention-capture is the NEXT slice, not this one.**
`Optic.peripheral` and `naked_eye_source.peripheral_stimulus_ids` shipped in cones 2B with no
producer, and movement is the natural first producer. But wiring it means computing the gate for
**un-gazed** candidates and feeding ids back into the *next* poll's bypass set — which changes what
Petrovich *detects*, not merely what he *reports*, and touches the gaze/bypass path this task
explicitly fences off. It would roughly double the slice and put a detection-behaviour change in a
milestone whose value is a reporting trigger. Out.

What this plan does do is leave the door open at no cost: the gate is a pure function of
`(observer, target, velocity)` with no dependency on visibility, so moving its call site from
"after `check_visibility`, for visible candidates" to "beside `group_salient_ids`, for all
candidates" is a two-line relocation when that slice comes. v1 calls it post-visibility because that
is the minimal correct version.

---

### Risks & Unknowns

- **Replay determinism — the sharpest risk, and it has two distinct failure modes.** (a) If the
  Hook stamps the snapshot with `DCS.getRealTime()` (as `f10_command.py` was forced to, having no
  cheap sim-clock access from Hook state), the feed becomes wall-clock-driven and replay diverges.
  The fix is structural and free: the snippet runs *inside* the scripting state, which **does** have
  `timer.getTime()`, so it stamps its own sim time at the point of read. Reject any implementation
  that timestamps in the Hook. (b) Replay must feed velocity snapshots from the recorded trace, in
  `t_sim` order, exactly as world-objects snapshots are — otherwise a replayed sortie silently loses
  all motion. `replay.py` drives only the ownship half and lets each source fetch its own data, so
  this is the *source*'s obligation: the fixture client must serve both endpoints from the trace.
- **`timer.getTime()` and `LoGetModelTime()` are assumed to be the same clock.** Both are documented
  as seconds since mission start, but this is an unverified DCS-internals claim and the skew bound
  in Decision 3 depends on it. It costs nothing to verify: Stage 1's first live run logs both, and
  the collector sees them side by side. If they differ by a constant offset, the join needs that
  offset; if they drift, Decision 3's bound must be rethought. **Do not treat this as settled until
  the first sortie's log is read.** (Not routed to `investigator` — the answer arrives free with
  Stage 1 rather than needing its own reconnaissance pass.)
- **Sim-thread cost is the real performance exposure**, not the Python side. Stage 0 part 2 is the
  only thing that answers it, and it answers it only after a sortie. Build Stage 2 first if that
  ordering is more comfortable — it costs nothing and is a no-op until Stage 1 lands.
- **`UnitName` may be absent or non-unique** for scenery, statics and some spawned objects. Absent →
  no join → `None` → unknown. Non-unique → the join must not silently pick one; detect collisions
  and drop both to `None` rather than guessing.
- **A parked static never reads "stopped", only "unknown"**, unless the snippet enumerates statics
  explicitly. Stage 1 does enumerate them (zero velocity, no `getVelocity` call), which removes most
  of this; genuinely unmatched objects remain honestly unknown, which is the correct answer.
- **The ×4 cockpit penalty is unmeasured** — named, isolated, movable in one place, and only a
  purpose-built sortie can calibrate it (no screenshot ladder can show motion). Same accepted debt
  class as the stabilisation penalty.
- **The empty-sky exception is not implemented.** The roadmap notes that a unit seen against sky has
  no static background, so ownship-relative velocity would be the correct input there. Implementing
  it needs a horizon test plus a second velocity path, and its only beneficiaries are air contacts,
  which almost always clear the absolute-velocity threshold regardless. Accepted limitation, stated
  rather than silently omitted.
- **Scope check on the whole milestone:** this is a genuine multi-subproject build (Export.lua wire
  bump, a third Hook script, a new receiver/cache/endpoint, a perception module, a belief module, a
  new event kind). That is larger than the roadmap entry's framing suggests, and it is worth saying
  so before Stage 1 starts rather than at Stage 3. The structure above is chosen to contain it: the
  seam at `WorldObjectCandidate.velocity` means Stages 2–4 are **source-agnostic**, so most of the
  build survives even if the transport is replaced.
- **The fallback, and an honest note that its cost picture has changed.** If Stage 0 part 2 comes
  back bad, the escape is to fill `WorldObjectCandidate.velocity` by differencing successive
  world-object positions in **body-layer** — not in the collector, as the 2026-09-20 entry
  considered and rejected. The rejection cited retaining per-candidate history and eating the noise,
  but body-layer already retains per-`object_id` state across polls (`continues_observation_id`,
  `OBJECT_ID_MEMORY_S`, the association gate), and movement is only ever reported for contacts that
  are being observed anyway — so the marginal cost is lower now than when that reasoning was
  written. Stages 2–4 are unchanged under it; only Stage 1 is discarded. This is recorded as a
  fallback, not a proposal to revisit a settled decision.

### Second-order effect

Unblocks more than it looks: the Hook script built in Stage 1 is the project's first general
mission-scripting **data** feed (the F10 hook is a command channel), and fog — the other half of
"detection under real world conditions" — needs exactly that transport, so it arrives nearly free
afterwards. Downstream, `CONTACT_MOTION_CHANGED` is the first behaviour-change event, which is the
prerequisite `docs/concept/threat-levels.md`'s motion-as-danger-criterion has been waiting on, and
the motion gate is the missing producer for `peripheral_stimulus_ids`. It narrows nothing; the one
thing it complicates is `Contact`'s growing per-attribute fold surface, now four belief attributes
each with their own fold, decay and twin comparison — worth a consolidating pass before a fifth.

### Decisions Requiring User Input

- **Stage 4's scope.** Should Petrovich *say* "moving" in a contact report in this milestone, or is
  the event plus `get_situation` enough for now? Assumed: one clause, trimmable — proceeding on that
  assumption rather than blocking.
- **Hook count.** Three Hook scripts after this (`overlay`, `f10-commands`, `mission-telemetry`) vs.
  folding velocity into the existing F10 hook to keep one poll tick. Decision 1 above picks the
  separate file; say so if you would rather have one.
