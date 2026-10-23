# Explore notes — configurable cockpit effector sequences (BL-B90)

2026-10-21, main loop with the user. Concept: `docs/concept/configurable-cockpit-effector.md`
(the user's, "concept, not final truth").

## Ordering

- The BL-B66 Stage 5 sortie flies on the **current hard-coded** build — *"I'll test the current
  BL-B66 implementation as it is, that is valuable info already. But the sequences would then be
  moved from hard coded to sequence file."*
- **The slew stays code**: *"The really important part of BL-B66 is the sight slewing and that
  *will not* move to sequence file, that is code only."* Slewing now lives in `[[BL-B80]]` (split
  2026-10-17), so this entry goes before BL-B80.

## Decisions

1. **Named effectors in one registry file** — *"very good, yes"*. Sequence files reference
   effector names and named values (`sight-power` = `on`); device / command / arg numbers live only
   in the registry. Reason: a write needs device + command, a readback needs the arg number, and
   the numbers are positional (an ED patch can shift them) — one file to fix.
2. **First-cut scope: replace BL-B66's hard-coded sequences only** — *"yes, BL-B66 first, expand
   later"*. Triggers `takeoff` (four-switch power-up), `observ-on`/`observ-off`,
   `weapons-arm`/`weapons-safe`; conditions on effector state; `wait_s`. Deferred: OAT, light
   level, `mission-start`, `taxi`, `land`, `guidance-unit-ready`, `atgm-*`, `target-destroyed`.
3. **Gating and refusals stay in code** — *"keep in code. I may put some logic into those files,
   but most such things are dependent on aircraft state at level we better keep in code. Subject to
   change, but that's a much larger scope for later if ever."* So e.g. "Unable, guidance unit not
   ready" stays where it is; files describe switch moves. A failed row condition skips that row.
4. **Overlapping triggers queue** — *"queue. Better keep state integrity as much as we can."* A
   sequence triggered while another runs waits behind it; nothing cancels a running sequence.
5. **Readback is registry-driven, low frequency** — *"yes. Also, low frequency update is enough
   for non-axis effector reads. If there are exceptions, we'll deal with them separately."*
   Export.lua reads the args the registry names (body-layer sends the list), at a low rate, instead
   of the fixed eight per frame. Needs a Windows redeploy.
6. **Load at startup, fail loudly** — *"restarting body layer is acceptable. I'd rather a check at
   startup and error than finding out in middle of flight. These are not meant to be edited all
   the time, but that will happen quite a bit until the sequences stabilize."* Validation covers:
   unknown effector/value names, unknown trigger, duplicate (aircraft, role, trigger), malformed
   rows. No hot reload.

## 2026-10-23 — after BL-B80 v2 merged (`a2ea382c`); answers to the plan's four decisions

Context: BL-B80 v2 rewrote `sight_effector.py`/`logger.py` after the plan was written —
readiness now comes from the real READY lamp (arg 960), and `GuidanceUnitState` carries the
898/960/962 lamp readbacks that pointing depends on. The user's direction on that:

- *"guidance unit power switch flip can go to sequence file"*
- On "Guidance unit ready" being spoken on the 960 lamp's edge: *"this is correct. For now it can
  be hard coded, but it should really be it's own trigger for a sequence file."* — so the
  `guidance-unit-ready` trigger (deferred in decision 2) is the intended home; hard-coded is
  acceptable in this cut.
- On risk of wrong arg values: *"It's easy to change the arg values in the sequence files. If we
  get the wrong one, the change is trivial. That's a benefit of the sequence files."* — so building
  this before Flight A settles the lamp args is not a blocker.

The plan's "Decisions Requiring User Input":

1. **Queues: per trigger** — *"queues: per trigger"*. (Refines decision 4: queueing is within one
   trigger, not across triggers.)
2. **Takeoff: every takeoff** — *"takeoff: per takeoff, the sequence file will then deal with it
   not being the first takeoff"*. Overturns the plan's one-shot-per-mission recommendation; the
   file's own row conditions handle the already-powered case.
3. **Bad file: log, ignore that file, keep running** — **supersedes decision 6's "fail loudly /
   refuse to start"**. User's words: *"bad file: log error and ignore file. Write a clear and
   obvious error message to console and queue audio error message to play once the intercom is up:
   'System error, bad sequence file, see the logs. Petrobrain will continue, but some functionality
   may not work.'"*
4. **Re-flight: own short card** — *"re-flight: own short card."*

### Readback rate and scope (2026-10-23, after the plan revision)

On the revised plan's R7 (*"BL-B80 already reads all six switches every frame"*), the user:

> *"we'll be reading a lot of args eventually. Better not do it every frame. The axis value
> (BL-B80) are required at max rate, but for switch positions the normal lower frequency poll is
> enough. If possible, query a set of switches when they are needed, not everything. This at DCS
> export level if possible, for performance reasons. Ok to defer to later stage, but will be needed
> soonish. Let's say BL-B90 last step."*

So: axis args stay per-frame (BL-B80). Switch positions move to the lower-rate poll, ideally an
on-demand query of just the needed set, done in `Export.lua`. Deferred, but it is BL-B90's **last
stage** (in scope, not backlog). That reverses the revised plan's "Stage 4 deferred, additive":
it now also moves the six switch args off BL-B80's per-frame push.

On "Guidance unit ready" at spawn on an air start: *"there's already a note somewhere to say it on
*change* to ready. Use that."* (BL-B80 decision 2, *"only on change"*.) Fixed separately on
`fix/guidance-ready-edge` before Flight A, not in BL-B90.

Order of work: *"Start by updating the plan as BL-B80 has made changes. After that first build the
tool for creating the switch list."* (Stage 0, the generator.)

## Carried from the concept, unchanged

- 1 s between effectors (existing tunable `GUIDANCE_UNIT_SWITCH_DELAY_S`); axes excluded.
- Role mismatch → sequence does not run. Only Mi-24P / copilot exist now.
- Triggers are a code enumeration; fire on the transition, not while true.
- Format: proposed TOML registry + markdown-table sequence files (the concept's own shape); user
  accepted the registry, did not object to the markdown sequences. Architect may confirm.
