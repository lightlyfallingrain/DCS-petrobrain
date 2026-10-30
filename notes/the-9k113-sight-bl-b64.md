# The 9K113 sight (BL-B64)

- **A field that should carry a physical/mechanical bound and is only ever read with `is not
  None` downstream needs the real bound check added at the point the value is *chosen*, not at the
  point it is consumed.** `Optic.regard_azimuth_half_deg`/`regard_elevation_*` were added as data
  in Stage 1 with a docstring saying enforcement was deferred to Stage 2; Stage 2 landed and never
  closed that deferral, because nothing on its own task list named "close the deferral" and three
  review passes each verified a true but narrower claim (the cone reads actual aim; the cone and
  cap are correctly paired; OBSERV-off tears the cone down) without ever checking whether the aim
  the cone was built from had itself been validated against what the instrument could mechanically
  reach. Found by Security, not Review, because Review's checklist never had "was this bound ever
  enforced" on it — the docstring read as "deferred, not yet due" rather than "missed."
- **Fixing a leak at the point a value is chosen does not fix every place that value is swept or
  derived.** The field-of-regard fix closed `_decide_sighting`'s look-selection leak; a second,
  smaller leak survived in `look_sweep`, which could still generate steps past the same mechanical
  limit at a tighter margin (67° against a 60° limit, found while fixing the first). Any check
  added at a "where the value is chosen" point should prompt a grep for every other place the same
  raw value is swept, widened, or otherwise derived into a new value before being used.
- **A deferral note that outlives the stage it names reads as a settled decision to everyone after
  it, not as an open item.** "Enforcement deferred to Stage 2" shipped in Stage 1; Stage 2 landed
  without adding the enforcement and without updating or removing the note. Three independent
  review passes read the unchanged comment as "this is still pending, as documented" rather than
  "the thing this note promised should have happened by now and didn't." A deferral note needs a
  stage name that can be checked against reality, and checking it against reality is only cheap if
  something other than the note's own wording prompts the check.
- **A dataclass documented as "frozen and replaced rather than mutated" can still silently drop a
  persisted field, if some of its construction sites build it fresh instead of calling
  `replace()`.** `OpticState`'s docstring reads as if every transition goes through
  `dataclasses.replace(state, ...)`, which would carry every field forward automatically — but two
  phase-entry branches construct `OpticState(...)` fresh, naming only the fields that phase's own
  bookkeeping needs, so a newly added persistent field (`actual_aim_*`) silently resets to its
  default on exactly those transitions. Before adding a field meant to persist independently of a
  state machine's phase, grep every construction site of the dataclass and classify each as
  `replace()` (safe) or a fresh call (needs the field added by hand) — this is invisible to "does
  the feature work" testing if the feature's own trivial-passthrough stage never exercises the gap.
- **The same defect shape — state that should reset or carry across a transition, and doesn't —
  recurred independently seven times across two related features** (`BL-14`'s attack-run work and
  this entry): a stale target surviving re-selection, a dataclass field dropped on fresh
  construction, a command-driven field divergence invisible to a phase dispatch that only checked
  its own internal stop conditions, and others. Four different people/passes found instances of it
  (two by the implementer's own failing tests, one by a reviewer building a diverged state by
  hand, one by security executing a scenario) — suggesting this is a property of this kind of
  code (phase/mode state machines with more than one field that should move together) rather than
  of any one implementation, and worth a structural check (e.g. "do all fields that should move
  together actually get updated by every transition path") rather than relying on each instance
  being caught individually.
- **Two Hook scripts can share state with no new transport, because their separate
  `dostring_in("scripting", ...)` calls execute in the same persistent mission-scripting Lua
  state.** A global a first Hook script's drained snippet writes (`PB_ACTIVE_FIRING_UNITS`,
  `petrobrain-firing-events-hook.lua`) is directly readable by a second, unrelated Hook script's
  own snippet (`petrobrain-line-of-sight-hook.lua`'s sort-key splice) with no collector round trip,
  no wire message, and no coupling between the two scripts' own code beyond agreeing on a global's
  name. This was not obvious from reading either script's header alone — found only by noticing
  that `petrobrain-f10-commands-hook.lua`'s own header already documents the same persistence for
  its own queue global. Worth checking for before reaching for a new transport whenever one Hook
  script's state needs to influence another's `dostring_in` snippet (`plans/emitter-visibility/
  implementation.md`, Notable Discoveries Stage B).
- **`Contact` carries no DCS `object_id` at all** -- the no-omniscience boundary means belief
  retains what was *observed*, not the engine's ground-truth identity -- so any later code needing
  to correlate a raw `object_id` back to a `contact_id` has to build its own cache from admitted
  rows rather than reading the id off `Contact`. `BL-B76`'s rejected-candidate join hit this and
  had to invent one; `perception/naked_eye_source.py` already keeps a richer private version for
  its own majority-overlap clustering. The gap is structural, not an oversight, so expect it to
  recur whenever new code needs that correlation *outside* a normal admission -- and note that any
  such cache, being admitted-only, cannot see a cluster split whose child was rejected that poll
  (`plans/bl-b76-tripwire/implementation.md`).
- **A helper written for an optic with no field-of-regard limit can have an elevation gap that is
  a true no-op for every existing caller, and stays invisible until a *new* caller gives it an
  optic that is actually regard-bound.** `belief.optic_policy.search_pattern`'s elevation
  (`atan2(altitude_agl_m, range_m)`) was never checked against `regard_elevation_down_deg` —
  harmless for its original caller (`BINOCULAR_OPTIC`, which has no field of regard at all), and
  still harmless for the plan's own azimuth-only framing of the fix. `9k113-narrow-search`'s idle
  search cycle became the function's first caller for a regard-bound sight optic, at an ordinary
  cruise altitude (>~625 m AGL, not an edge case) — a third occurrence of the exact field-of-regard
  enforcement gap this entry's first bullet already names, missed by the plan, the implementer and
  two Reviewer passes, caught only by Security's deep analysis. When a plan reuses an existing
  helper for a new optic/caller, ask explicitly which of the helper's own silent assumptions were
  true only because of the *old* caller's properties — "no field of regard" is one such property,
  and it does not transfer.
- **An invariant test built with empty/default inputs and a realistic-geometry test that checks
  only one axis can sit side by side for an entire review cycle without ever covering the
  combination that matters.** The existing `within_field_of_regard` idle-aim tests passed no real
  `sight_*_search` sequences at all, so they exercised the trivial hold-last-position fallback, not
  `search_pattern`; the tests that *did* drive real geometry checked azimuth sub-spans only, never
  elevation. Neither test was wrong on its own terms, and together they still missed the gap above.
  When adding a new producer to an existing invariant test, drive it with the real sequence-builder
  the production call site uses, not a synthetic or empty stand-in, and check every axis the bound
  has, not just the one the existing tests already cover.
- **A bound check can be present, tested, and still wrong — if it is evaluated in the wrong
  reference frame.** The fix above (occurrence 3) checked the idle search cycle's elevation against
  `regard_elevation_down_deg`, correctly, but computed that elevation from ground-anchored
  range/altitude geometry (`atan2(altitude_agl_m, range_m)`) — correct only at wings-level,
  nose-level flight. The user's own correction named the actual requirement: the ±60°/+20°/−15°
  limits are *boresight*-relative, mechanical rotation limits around the aircraft's own axes, not
  ground-relative — nose-down at altitude recovers a near scan the ground-anchored formula said was
  unreachable, and nose-up tightens it the other way. The fix (a shared `heading_relative_to_
  body_relative`/`body_relative_direction` conversion, applied before the regard check everywhere a
  sight or binocular aim is produced) is this project's standing frame-correctness question
  (`notes/solve-the-problem-in-its-natural-coordinate-space.md`) applied to a case that looked
  settled: a check that is correct "on average" or "in the common case" (level flight is typical)
  can still be wrong on the axis that actually varies (attitude), and nothing about the check being
  *present* and *passing its own tests* protects against the tests themselves sharing the same
  frame assumption as the code.
- **A fix for a pathological/stuck case can silently throttle the ordinary/healthy case too, and a
  narrative figure cannot settle whether it did.** `BL-B85`'s stall-cooldown fix (closing a contact
  stuck forever at `presence` from monopolising the sight) also made every *scheduled* dwell-
  boundary break commit a pending mark for the first time — including a contact whose
  classification was genuinely advancing, which the review caught by measuring a concrete case (a
  progressing contact's re-look cadence went from ~33 s to ~94 s). The first re-measurement of "is
  the common case still fine" was shipped as prose numbers in the roadmap entry, not a test; a
  second independent reproduction of that same prose disagreed with it by nearly 2×, because
  "the poll after the look ends" turned out to be ambiguous enough that two correct-looking scripts
  resolved it differently. Only a committed, deterministic test — pinning the exact convention in
  its own docstring — could settle which number was real. When a fix narrows or re-times a shared
  gate to handle a pathological input, the healthy-input re-measurement belongs in a committed test,
  not a one-off script's printed number, even when the fix is otherwise obviously correct.
- **A readback value and the command value that produced it can share a physical quantity (degrees)
  and formula on one half of their range while needing genuinely different formulas on the other
  half, with nothing in the type system to tell them apart.** `BL-B80`'s elevation calibration has
  one linear conversion for the readback argument (`arg_876 * 20.0`, both signs — a piecewise 0.75
  gauge factor on the negative argument side exactly cancels the 20/15 degree-per-unit asymmetry)
  and a genuinely different piecewise conversion for the command value sent via `SetCommand` (no
  readback step happens on the way out, so nothing cancels). The first implementation applied the
  readback formula's piecewise version by mistake and a unit test caught it immediately
  (`sight_elevation_raw_to_deg(-0.75)` returned `-11.25`, not `-15.0`) — but only because that test
  existed; both functions take and return a bare `float`, so a future call site swapping one for
  the other would type-check and silently produce a wrong-but-plausible number. When a conversion
  has a command direction and a readback direction, treat them as two formulas from the start
  rather than assuming one is the other's algebraic inverse, and say in each function's docstring
  which domain it is for.
- **A per-optic perception cap can be defeated by a shared belief field that keeps the previous
  optic's last real value instead of clearing when the optic that owns it stops being used.**
  `BL-B80`'s gyro-alignment window caps `optic_decision.optic` to `BINOCULAR_OPTIC` specifically so
  naked-eye/binocular perception does not read through the sight while it is unusable — but
  `GuidanceUnitState.sight_az_raw`/`sight_elev_raw` (consumed generically by
  `perception/naked_eye_source.py`'s gaze-cone builder, not only by sight perception) are set by
  `refresh_readback` on every numeric sample and never cleared back to `None`, so once any sight
  readback has ever arrived, naked-eye/binocular perception keeps reading the sight's literal head
  position for the rest of the mission regardless of which optic is actually in use — defeating the
  cap's purpose everywhere, not only during the alignment window it was built for. No test combined
  a non-sight optic with a populated readback field, so the gap went unexercised rather than merely
  untested-for. The general shape: a field two code paths share (one that owns writing it, several
  that read it generically) must be gated at the read site on which path currently applies, not
  assumed clear just because the writer's own caller thinks it is between uses.
- **DCS's AI axis (the 9K113's own guidance-unit servo) only obeys a `SetCommand` write whose
  value differs from the previous frame's — a per-frame constant value, however correct, is
  silently ignored after the first frame.** Eleven probe runs on `BL-B80` chased "intermittent
  obedience" under several hypotheses (timing, device index, command id) before the pilot's own
  hypothesis — "DCS acts on an axis only when its value changes" — was tested directly and
  confirmed (flicker 18/18 steps obeyed, constant 3/10). A tiny invisible per-frame dither
  (0.6°/8 Hz here) or flicker (±1e-5…1e-3 unit) written on top of the real setpoint keeps the axis
  "live" without a visible effect, and this reclassified a whole prior plan's "intermittent
  obedience" defect as expected behaviour of an edge-triggered axis, not a bug to chase further.
  Worth checking for on any DCS-cockpit axis that appears to only sometimes take a commanded value:
  try a dithered/changing write before assuming a timing or addressing problem.
- **A position-model premise built and reviewed can still be wrong in a way invisible to any of
  its own unit tests, because the axis it reasoned about behaves like a different control
  primitive than assumed.** `BL-B80`'s v1 plan modelled the 9K113 axis as a *position* target
  (874/876 as a position readback, the AI overlay required on) — internally consistent, reviewed,
  security-approved, fully unit-tested — and was overturned wholesale by live probe runs 1–10 once
  flown: the axis is rate/edge-driven, 874/876 echo the *demand* not a position, and the AI overlay
  is not required at all. Nothing in the v1 test suite could have caught this, because every test
  exercised the model's own internals against its own assumptions; only flying the probe against
  the real DCS axis surfaced the mismatch. The whole mechanism (`ShowMenu`, `ai_believed_on`,
  `GYRO_ALIGNMENT_S`, the elevation-conversion functions above) was removed rather than patched.
  When a plan's physical/control-loop model of a DCS system has never been checked against a live
  probe, treat "passes review and all its own tests" as necessary, not sufficient — the probe is
  what the architecture actually depends on, and it belongs before the model is built on, not
  after.
- **A "speak once when a lamp lights" callout written as a one-shot `bool` latch is silently wrong
  for any lamp that can cycle, and the wrongness is invisible on a warm start.** `BL-B80`'s
  960/READY callout (`CrewConsole.drain_guidance_unit_ready`) latched on the first poll the lamp
  ever read lit — which on a warm air start (lamp already lit at the very first sample) fires
  correctly by coincidence, so the bug only shows on a real cold-start power cycle, where the
  latch never resets and a second power-up stays silent. The fix is a previous-observed edge
  (`prev_observed: bool | None`, edge = `previously_observed is False and ready_observed is True`)
  with `None` deliberately not treated as `False`, so a first-ever-lit sample (no prior
  observation) is not an edge either. The general shape: any "announce on this becoming true"
  callout needs the previous *observed* value, not a has-this-ever-fired flag, or it cannot
  distinguish "just became true" from "was already true before we were watching."
- **A nulling call shared by two call sites, only one of which actually needs the null, resumes
  wrong for the other — and only `replace()`-style resume functions downstream expose it.**
  `_start_glance_away` (`BL-B98`) unconditionally nulled the believed sight aim on every entry,
  for both its call sites — but both only ever fire while OBSERV stays on (a scheduled break, not
  OBSERV turning off), so "resume at last position" was only ever true by accident, when the aim
  happened not to have been nulled yet. The resume functions (`_back_to_home`,
  `_enter_binocular_search`) both carry the aim through unchanged rather than re-deriving it, so
  they silently inherited whatever the nulling function left behind. Found by a test that assumed
  the documented behaviour and failed against the real code, not by reading the nulling function
  in isolation — a function's own correctness ("nulls the aim, as documented") said nothing about
  whether nulling was the right thing to do at *this* call site.
- **A field reused across three independent per-poll clock mechanisms (the sight's per-target look
  clock, the idle 3-leg search cycle's per-leg clock, and — once added — the bounded `look
  <o'clock>` sweep's own clock) is a silent coupling hazard every time a new mechanism is added
  to share it**, not just the first time. `look_started_sim`'s existing two consumers were already
  documented; the Stage 2 apply block that cleared it for "any superseding command" treated the
  field as private to the new bounded-look mechanism, and clobbered an unrelated, in-progress
  sight look whenever almost any other command fired mid-look (`follow`, `select_target`,
  `engage`, `cancel_task`, …). Caught by a Reviewer mutation test, not by reading the diff — the
  fix scopes the reset to "a bounded look was actually involved" rather than "any transition that
  happens to touch this shared field." Same pattern this topic already tracks for shared belief
  fields (the per-optic-cap/readback-field entry above); worth grepping every reader of a shared
  per-poll clock/state field whenever a new writer is added to it, not just when the field is
  first introduced.
- **Stopping writing a `SetCommand` axis is not the same as commanding it to zero, and this is a
  separate failure from the dither finding above.** The dither note above is about DCS *ignoring*
  a per-frame write whose value never changes; this is about what happens when the writes *stop
  entirely* — the AI axis (`CMD_AI_AZ`/`CMD_AI_ELEV`, 9K113) simply holds whatever was last
  commanded, indefinitely, with no decay or self-reset. `run_sight_servo`'s OBSERV-off path reset
  its own software state on OBSERV going off but never re-touched the axis itself, so a dither/
  tracking value written the frame before OBSERV went off stayed commanded for the rest of the
  sortie — reported as "the ASP-17 mark still moving" (`docs/acceptance/2026-10-24-sortie-feedback.md`
  F1, fixed on `fix/observ-off-axis-zero`, `[[BL-B80]]`). The general shape: on any DCS axis that
  latches, "stop driving it" and "command it to a safe/neutral value" are two different actions,
  and ending a control loop without the second leaves whatever the loop was doing at that instant
  frozen in place rather than cleared.
- **Occurrence 5 of the recurring field-of-regard-enforcement defect** (occurrences 1-4:
  `.claude/agent-memory/dod/project_recurring_field_of_regard_enforcement_gap.md`) — v3's
  `run_sight_servo` gate (`setpoint_inside_field`) checked the **setpoint** against the sight's
  ±60°/+20°/−15° gimbal limits, not the **mark's own raw reading** against the ASP-17's own
  ~±4.3° readable window, so a simulated direction anywhere up to ~58° off boresight read as
  "valid" and the closed loop's unsaturated error term drove the real sight hard against (or past)
  its own clip. The first occurrence where the bound was checked against the **wrong magnitude**
  (a ±60° check standing in for a ~±4.3° one), not just the wrong frame (occurrence 4's shape,
  ground-relative vs. boresight-relative) — and the first of the five to produce a **user-visible,
  flight-observed symptom** (the pilot's own 2026-10-26 report) rather than being caught by review
  or security first. The fix (`sight_mark_is_clipped` against the mark's own raw value, the loop
  always steering toward `field_target` — the setpoint radially projected onto the inset field —
  rather than the raw setpoint) closes this sight's last remaining field-of-regard-shaped check;
  every other one on this subsystem (the gimbal clamp, intent's ±60° azimuth cap) was already
  checked against its own correct frame/magnitude before this pass.
- **`run_sight_servo` in `Export.lua` is at Lua 5.1's 60-upvalue-per-closure ceiling** — confirmed
  live by `luac5.1 -p`: adding a single `if SIGHT_HANDS_OFF then return end` at the top of the
  function fails the syntax check outright ("function at line 1581/1583 has more than 60
  upvalues"), not a runtime symptom. The 2026-10-30 hands-off-switch feature had to move its check
  into a new wrapper function (`sight_servo_tick`, called from `LuaExportAfterNextFrame` in
  `run_sight_servo`'s place) rather than add one more `if` inside it. Any future change to this
  function that references one more upvalue needs the same move, not a straightforward edit —
  there is essentially zero headroom left (`plans/9k113-hands-off-switch/implementation.md`,
  independently reproduced in `review.md`).
- **One observation of a sight/mark mismatch cannot separate a scale error from a boresight
  error.** Both shift a reading in the same direction for a single depression angle; only a second,
  different depression angle (or a direct, no-feedback-loop measurement) disambiguates them. This
  is why the 2026-10-30 sortie feedback on a low ATGM mark led to a hands-off calibration switch
  (hand-slew the real 9K113 to two known angles with Petrovich's own servo write suppressed)
  rather than another single-point correction to `MARK_BORESIGHT_EL`/`MARK_DEG_PER_UNIT_EL` — the
  same ambiguity the 2026-10-28 scale-vs-boresight entry above already carried, recurring on the
  very next flight (`[[BL-B80]]`).
