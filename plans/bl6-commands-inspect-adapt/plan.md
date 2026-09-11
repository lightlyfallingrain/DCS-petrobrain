### Goal

Give body-layer a mechanism-agnostic `PendingIntent` command lifecycle (`scan_area` /
`get_task_status` / `cancel_task`) that biases perception toward a named area and reports task
outcome from belief state, while leaving the actual DCS-side effector (whether Petrovich's
scan behavior can be driven at all) as a pluggable, separately-gated piece whose feasibility is
still unresolved.

### Investigator findings this plan depends on

Invoked before finalizing this plan, per the process — `plans/body-layer/plan.md` §7 flags
"whether Petrovich's scan behavior can be influenced at all" as BL-6's entire premise and
blocking. Findings written to
`aircraft-layer/research/2026-09-10-bl6-petrovich-command-feasibility.md`:

- `Export.LoSetCommand(commandID[, value])` is a real, historically-documented command-injection
  API callable directly from `Export.lua`'s own state (no new Hook script needed) — but
  forum-claim-unverified, and one ED thread title itself asks "deprecated?" for modern modules.
- A shipped, first-class in-cockpit command UI exists and is literally namespaced `Petrovich`:
  `Cockpit/Scripts/HelperAI/AI_Wheel/*` (+ a dedicated `Input/Mi_24P_AI_Menu/` keybind profile),
  and a second candidate `Cockpit/Scripts/AI/ControlPanel/g_panel*.lua` / `AI_Gunners.lua`.
  File **paths** confirmed to exist in the installed tree; file **contents** — i.e. whether the
  wheel offers anything resembling "scan this area/bearing" versus only combat-mode commands
  (attack/hold-fire/cover) — are unread. This is the single biggest open question.
- No confirmed read-side signal exists for "Petrovich is scanning" vs "found N" vs "idle".
  `list_indication(6)`'s target list is gated by weapon-selection/attack mode per prior research,
  not an ambient scan-state flag; `HelperAI_sound.lua`'s aptly-named events
  (`observ_on`/`target_acq`/`still_searching`) are audio-trigger-only with no confirmed
  Lua-readable mirror.
- A concrete, cheap live-DCS probe is specified in the findings file (read ~7 named Lua files,
  then try `LoSetCommand` candidate IDs against a live mission and watch for visible
  sight-slew/behavior change and any `list_indication`/callout change). **Not yet run** — per this
  project's execution-boundary rule, the user runs it, not an agent.

**Consequence for this plan:** whether DCS-side commanding is possible, and what it would look
like, is a genuine two/three-way fork (`LoSetCommand`, keypress/joystick-injection fallback, or
"no real lever exists") that only the live probe resolves. The design below is deliberately built
so the parts buildable *now* do not depend on that answer, and the parts that do are isolated,
optional, and explicitly gated.

### Architectural note

This milestone designs a new DCS write channel and forks on an unresolved DCS-internals question
inside a live-sim domain (async task lifecycles that must tolerate real-world timing, a new
inbound path into a system that's been read-mostly since project start). Per this role's own
guidance, I'd recommend re-invoking Architect with an opus model override if the user wants this
plan re-derived at higher reasoning depth before Security's plan review — I judged the design
below tractable at default depth because the mechanism-agnostic split (below) keeps the genuinely
uncertain part small and isolated, but flagging per instruction rather than silently proceeding.

### Affected Modules / Files

**body-layer (buildable now, independent of probe outcome):**

- `body-layer/src/belief/tasks.py` *(new)* — `PendingIntent` dataclass (`task_id`, `kind`
  currently only `"scan_area"`, `area: AttentionArea`, `deadline_sim: float`,
  `status: Literal["pending", "succeeded", "failed", "cancelled"]`, `created_sim: float`,
  `reason: str`, `result_contact_ids: list[str]`), a `TaskStore` (mint ids the same way
  `ContactStore._new_event_id`/`_areas` do — sequential, store-owned, not caller-supplied) and
  `tick(now_sim)` — the supervisor step: for each `pending` task, check `ContactStore` for any
  contact whose `last_position` falls inside `task.area` and whose most recent observation
  arrived *after* `task.created_sim`; if found, mark `succeeded` and record the contact id(s); if
  `now_sim >= task.deadline_sim` with nothing found, mark `failed` (timeout, not "confirmed
  nothing there" — see Risks). No DCS I/O in this module at all.
- `body-layer/src/belief/tools.py` — add `scan_area(store, tasks, center, radius_m, reason,
  deadline_s=DEFAULT_SCAN_DEADLINE_S, sector=None)` (registers a `belief.attention.AttentionArea`
  via the existing `store.add_area` at `level="watch"`, then a `PendingIntent` in `tasks` over the
  same area — reuses BL-4's area machinery rather than inventing a second area concept),
  `get_task_status(tasks, task_id)`, `cancel_task(tasks, task_id)` (marks `cancelled`, and — see
  Decision below — also calls `store.remove_area` for the area it registered, since an
  abandoned scan should stop biasing attention).
- `body-layer/src/belief/tool_api.py` — three new `ToolSpec` entries wired to the above,
  descriptions adapted verbatim from `plans/body-layer/plan.md` §3.3.
- `body-layer/src/belief/console.py` — `scan-area <bearing> <range_m> <radius_m> <reason>
  [sector]`, `task-status <id>`, `cancel-task <id>` commands, mirroring the existing
  `watch-area`/`unwatch-area` pattern.
- `body-layer/src/logger.py` — wire `TaskStore.tick()` into the same poll-loop hook point
  `ContactStore.tick()` already runs from (`--console`/`--crew-text`/`--overlay` all drive it).
- `body-layer/tests/test_tasks.py` *(new)* — fixture/replay-style tests: task succeeds when a
  contact appears in-area post-creation, times out when none does, cancel stops future
  succeed-checks and removes the area, ordering/idempotence under repeated `tick(same now_sim)`
  matching `ContactStore.tick`'s own convention.

**aircraft-layer (gated on the live probe; do not implement until the probe resolves which fork
applies — see Decisions):**

- *If `LoSetCommand` + a real wheel/panel command ID is confirmed*: a new `POST
  /command/scan_area` endpoint in `src/api/`, mirroring `POST /text/push`'s existing shape
  (validate body, forward to a new `collector/command_sender.py`), which calls
  `Export.LoSetCommand(<id>[, value])` from `Export.lua`'s own state — no new Hook script needed,
  same loopback-TCP channel as the rest of the collector. Returns `200 {"ok": true}` on "attempted
  the call" only, same fire-and-forget posture as `/text/push` — this endpoint cannot itself
  confirm Petrovich reacted, only that the call was made.
- *If `LoSetCommand` is dead but the AI Wheel keybind is real*: a Windows-side keypress-injection
  helper (stdlib `ctypes`-based `SendInput` equivalent — no new dependency, consistent with
  aircraft-layer's stdlib-only policy) is a materially larger architectural surface (new process
  or new responsibility in the collector, simulating player input rather than calling an export
  function) and needs its own Architect pass, not a subsection of this one, if it comes to that.
- *If neither pans out*: no aircraft-layer change at all. `scan_area` still runs — see below.

### Why the fallback ("virtual scan") is the default behavior, not a degraded afterthought

Whether or not any DCS-side effector ever gets built, `scan_area`'s body-layer half (register an
`AttentionArea` + a `PendingIntent`, verify via belief state) already does something real: it
biases which of the perception pipeline's naturally-arriving detections get treated as "the
answer to this task," and it gives the brain a task-status answer without inventing a fact DCS
never confirmed. This mirrors the investigator's Q4 fallback framing but treats it as the floor
the design stands on, not a contingency bolted on if the probe comes back negative — because the
probe *can't* come back fully positive (no confirmed outcome-verification signal exists either
way, per findings), body always needs this belief-state-driven success check regardless of
whether a real command also fires. Adding a confirmed DCS-side effector later is strictly
additive: it raises the odds a scan actually succeeds, it does not change `PendingIntent`'s shape,
`tools.py`'s signature, or the tool API.

### Implementation Plan

1. **`PendingIntent` + `TaskStore` + `tick()`** (`tasks.py`), pure and DCS-I/O-free, tested against
   synthetic `ContactStore` fixtures the same way `test_contacts.py`/`test_attention.py` already
   do. This is the whole async task-lifecycle machinery D3 (plan.md) already decided on — no new
   design decision here, just building what D3 specified.
2. **`scan_area`/`get_task_status`/`cancel_task` in `tools.py` + `tool_api.py` + `console.py`**,
   composing `TaskStore` with the existing `AttentionArea`/`ContactStore` surface. Console-testable
   end to end with no live DCS, same as every prior BL-x milestone's console-first acceptance
   path.
3. **`logger.py` wiring** — `TaskStore.tick()` alongside `ContactStore.tick()`.
4. **Tests + fixture/replay acceptance.** Deterministic: a scripted `ContactStore` populated via
   `replay.py`-style ingestion, `scan_area` issued, then either a matching contact injected before
   or after the deadline. No live DCS needed for this milestone's DoD — consistent with BL-3/BL-4's
   console/replay-only precedent.
5. **Live probe (user, not this plan's Implementer)** — the seven-file read + `LoSetCommand`
   candidate-ID live test specified in `aircraft-layer/research/
   2026-09-10-bl6-petrovich-command-feasibility.md`'s "Reproducible Test" section. This can happen
   in parallel with Stages 1–4, since nothing in body-layer's implementation blocks on it.
6. **Conditional aircraft-layer stage** — only if Stage 5 confirms a working command mechanism.
   Runs through this milestone's own required Security plan review (root `ROADMAP.md`/`CLAUDE.md`
   gate) before any code lands, since it is a new inbound write path into a live DCS process. If
   Stage 5 is negative or still inconclusive when body-layer work is otherwise done, ship Stages
   1–4 alone as BL-6's full scope and record the aircraft-layer half as future work, not as an
   incomplete milestone — the milestone's stated deliverables (`scan_area`/`get_task_status`/
   `cancel_task`, tool-set freeze) are satisfied by the body-layer half alone under the "virtual
   scan" framing above.

### Risks & Unknowns

- **Outcome verification is inherently ambiguous.** A `failed` (timeout) task cannot distinguish
  "Petrovich looked and found nothing" from "nothing was ever attempted" from "something was there
  but outside detection range/LOS." This is not a bug to fix later — it's the same epistemic limit
  a real crew has, and `tools.get_task_status`'s description should say so plainly (`"failed" means
  "nothing confirmed by the deadline," not "confirmed empty"`) so the brain never over-claims
  certainty from it. Flag prominently in the tool description, per the no-omniscience invariant.
  If a stronger DCS-side signal is later found, this can be refined without an API break — the
  status enum can grow a distinguishing value, not change shape.
  This is the same "quality-weighted ladder" shape as the still-open certainty-fusion backlog item
  in `body-layer/ROADMAP.md` — worth a cross-reference if that item is ever picked up, not
  something to solve here.
- **`DEFAULT_SCAN_DEADLINE_S` is a placeholder constant**, like BL-3's confidence table and BL-4's
  cooldown before it — needs live-sortie calibration, not a principled derivation, once any live
  acceptance is run.
- **`scan_area`'s area-registration reuses `watch_area`'s bearing/range-only resolution** (no
  `find_place` integration) — same scope cut BL-5a made for the identical reason; a place-name
  `scan_area("the village")` stays unmatched until `find_place` (BL-5, already merged) is wired
  into whichever grammar calls this tool. Cheap to add later, flagged so it isn't mistaken for
  this milestone's scope.
- **AI_Wheel vs. `g_panel`/`AI_Gunners` relationship is unread and unresolved** — if the probe
  finds the wheel has no scan-equivalent option, the milestone's "scan_area" framing may need
  renaming around whatever real command exists (e.g. "attack area" is the closest real lever) —
  a naming/semantics question for a future revision, not a blocker to Stages 1–4.
- **`cancel_task` removing the task's `AttentionArea` is a judgment call**, not obviously right:
  the player may want the area still watched after cancelling the *task* (e.g. "never mind
  finding something new there, but still tell me if anything shows up"). Flagged below as a
  decision, not silently resolved.
- **If Stage 6 does happen, its new inbound write path is a materially different risk class**
  than `/text/push` (opaque display string) — it can, if `LoSetCommand`'s command-ID space is
  wider than the one scan command wired up, potentially reach unrelated cockpit/AI behavior if a
  wrong ID is ever passed. This is exactly why the milestone's own gate requires Security plan
  review before that stage, not just before merge.

### Decisions Requiring User Input

- **Should `cancel_task` also remove the `AttentionArea` it registered, or leave the area watched
  and only stop the task's own success/timeout bookkeeping?** Both are reasonable; picked no
  default — needs a call before Stage 2 lands the function signature.
- **Is shipping BL-6 as "body-layer half only" (Stages 1–4), with the aircraft-layer effector as
  explicitly deferred future work, acceptable** if the live probe (Stage 5) doesn't resolve in
  time, or should the milestone be held open until Stage 5's answer is in? Leaning toward "ship
  the body-layer half, defer the rest" given the "virtual scan" framing above already makes that
  half a complete, useful deliverable — but this changes what "BL-6 done" means in
  `body-layer/ROADMAP.md`, so flagging rather than deciding unilaterally.
- **Naming**: if the live probe finds no scan-specific AI Wheel/panel command, should the tool
  stay named `scan_area` (documented as "best-effort, may only bias perception") or be renamed to
  something that doesn't imply a command is actually issued? Deferred until Stage 5's answer is
  known — raised here so it isn't forgotten.

### Second-Order Effects

**Unblocks:** this is BL-6's tool-set freeze point per `body-layer/ROADMAP.md` — once
`scan_area`/`get_task_status`/`cancel_task` land, the brain-facing tool API (`docs/concept/
PETROBRAIN_RUNTIME.md` §3.3's full list) is complete, and a brain-layer prototype (PB-6) can be
built against a stable surface for the first time. **Narrows:** if Stage 6 (real DCS effector)
never lands, every future "have Petrovich actually do X" idea (not just scanning) inherits the
same ambiguous-outcome-verification ceiling this plan designs around — worth remembering before
BL-8's memory layer decides how much confidence to persist about task outcomes. **Complicates
none identified beyond what's already flagged above** — the mechanism-agnostic split is
specifically meant to avoid this milestone complicating BL-7 (mission phase) or BL-8 (memory).

### Invariant Check

- **Code owns facts, models interpret:** `get_task_status`'s `"failed"` is never overstated as
  "confirmed empty" — see Risks. The brain gets a status and a fact set, never a claim body can't
  back.
- **DCS authoritative, read-only install:** unaffected in Stages 1–4 (no DCS I/O). Stage 6, if it
  happens, still never modifies the DCS install — it calls an already-existing exported Lua
  function from a script this project already deploys and controls, the same posture as every
  other aircraft-layer write (`/text/push`).
- **Provenance/uncertainty/timestamps:** `PendingIntent` carries `created_sim`/`deadline_sim`
  explicitly; a task's `succeeded` result links back to the contact id(s) that satisfied it, so
  the causal chain (task → belief-state check → outcome) is inspectable, not opaque.
- **Module independence:** no new cross-subproject import; body-layer's Stages 1–4 depend only on
  `belief.attention`/`belief.contacts`, already in-module. Stage 6 (if built) stays inside
  aircraft-layer's existing HTTP boundary to body-layer — no in-process coupling introduced.

---

## Update 2026-09-11 — live install read, probe written

The DCS install became available, so the "unread" half of this plan's dependency is now read.
Full results: `aircraft-layer/research/2026-09-11-command-injection-surface.md`; enumerated
command/indication catalogue: `aircraft-layer/research/mi24p-command-surface.md`.

**Resolved:**

- *"AI_Wheel vs `g_panel`/`AI_Gunners` relationship is unread"* — answered. They are different
  devices, not successor/predecessor: `g_panel` is indicator 8 owned by `devices.WEAP_SYS` (6);
  the wheel is indicator 10 owned by `HELPER_AI` (30).
- *"the single biggest open question: does the wheel offer anything resembling scan this
  area?"* — answered: **no**, not as a named command. Petrovich has 21 commands
  (3001-3021) and the wheel is navigated (`ShowMenu`/`Up`/`Down`/`Left`/`Right`), with dynamic
  contents rendered from compiled code, not declared in Lua.
- *"whether `LoSetCommand` still functions for modern modules"* — documented in this install
  (`Scripts/Export.lua:854`, `API/Sim_ControlAPI.md:538`), so not deprecated as far as shipped
  docs go. But it is the **global** channel; cockpit device commands need a device object, since
  every device's command table restarts at 3001 and an ID alone cannot name a device.

**Changed for Stage 6:** the plan's `POST /command/scan_area` shape survives, but the body should
carry `(device_id, command_id, value)` rather than a single `LoSetCommand` ID, and the call is
`GetDevice(dev):performClickableAction(cmd, val)`. The keypress/`SendInput` fallback is only
needed if the probe's stage C fails.

**New lead, strongest one BL-6 has:** `helperai_commands.DesignateAttackPoint` (3020) may be a
scan-area primitive under an attack-flavoured name — `HelperAI.lua` defines
`scan_rad_around_point = 2500`, a constant that only makes sense if some command designates a
point to scan around. Unverified; stage D of the probe tests it.

**Bearing on this plan's three flagged decisions:**

- *Naming (`scan_area` vs something not implying a command is issued)* — if
  `DesignateAttackPoint` does drive a 2.5 km scan, `scan_area` is an honest name after all.
  Still blocked on the probe.
- *"Is body-layer-only acceptable as BL-6 done?"* — unchanged, still a user call. Nothing found
  weakens the "virtual scan" framing; the belief-state success check is still required either
  way, because no read-side "Petrovich is scanning" signal was found (that conclusion stands).
- *`cancel_task`'s `AttentionArea` handling* — untouched by these findings, still open.

**Stages 1-4 (body-layer) remain unaffected and unblocked**, as designed. The mechanism-agnostic
split held up: nothing learned this session changes `PendingIntent`'s shape, `tools.py`'s
signatures, or the tool API.

**Still blocking Stage 6:** whether `GetDevice`/`performClickableAction` exist in Export.lua's
state. Not documented anywhere in the install; probe written
(`aircraft-layer/dcs-export/Export.probe-commands.lua`) and ready for the user to run.

### Addendum 2026-09-11b — the 9K113 is the better effector than the AI Wheel

User redirected from the ASP-17 to the 9K113 Raduga-Sh operator sight (device 7). That changes
BL-6's Stage 6 options for the better:

- **It has a real read channel** — cockpit draw args **874** (azimuth) / **876** (elevation),
  declared as gauges in `mainpanel_init.lua:1575-1585`. No other optic in the module has one; the
  ASP-17's equivalents were closed out as dead ends in the 2026-09-08 spike. This matters because
  it is the first candidate for *observing* where the crew's optics are actually pointing, rather
  than inferring it.
- **Slew axes are velocity, not position** (`axis_use_velocity = true`), so "point at bearing X"
  is a closed loop against 874/876, not a single write. That is a real design constraint on any
  future `look_at` tool and should be recorded before BL-7/BL-8 assume otherwise.
- **A dedicated AI slew channel exists** — `Command_Intern_SIGHT_{UP_DOWN,LEFT_RIGHT}_AI_AXIS`
  (3060/3061), bound to no input in any `Input/` profile. If Petrovich slews through it, it is a
  more honest effector than driving the player's own axes.
- **Caveat raised by the user:** the 9K113 is its own gameplay mode with its own viewport, and
  player slew commands may not work outside it. Consistent with `SightWithCockpitView = false`
  and the sight's `dedicated_viewport`. Unresolved from files; probe stage E tests player vs. AI
  axis, in and out of the mode.

Nothing here changes Stages 1-4. It changes which effector Stage 6 should target if the probe
comes back positive: **`(device 7, 3060/3061)` with a closed loop on args 874/876**, rather than
the AI Wheel, which has no scan command at all.

---

## Update 2026-09-11c — investigation complete; this plan needs revising

A day of live probing on the DCS box settled every mechanism question this plan
was gated on. **Read
`aircraft-layer/research/2026-09-11-SUMMARY-petrovich-control.md` first** — it
consolidates the findings, with detail in the two dated notes beside it and raw
evidence in `aircraft-layer/research/logs/2026-09-11/`.

**Both premises this plan was built on are now false:**

1. *"Petrovich has no scan command"* — he has `SRCH BRST`, `SRCH FWD`,
   `SRCH PILOT LOS`, plus `DesignateAttackPoint` ("Designate custom AI attack
   point") and `LineUp_EXT` ("Turn to sight heading"). The wheel is fully
   drivable from code.
2. *"There is no outcome signal, so success must be inferred from belief
   state"* — his state machine (`WAITING`/`SEARCHING`/`TRACKING`), his gaze in
   degrees, and his classified contact list are all directly readable, and a
   list longer than the five-row window is fully enumerable.

So the **"virtual scan" framing solves a problem that no longer exists.** The
body-layer half (`PendingIntent`/`TaskStore`, console/replay testing) remains
sound and is unaffected; what needs rethinking is Stage 6 and the success
criteria, which can now be real rather than inferred.

**What an Architect revision should take as input:**

- **Effector:** `GetDevice(7):SetCommand(3061, deg/60)` points the optics —
  positional, linear, single write, settles in 0.25 s. Read back from arg 874.
- **Outcome signal:** `list_indication(10)` for state, `list_indication(6)` for
  classified contacts. Both real; neither needs belief-state inference.
- **The one remaining gap:** there is no confirmed way to make him search a
  *bearing we choose*. `SRCH PILOT LOS` follows the human's head, `SRCH 9K113
  LOS` appears broken, `SRCH FWD`/`BRST` are not aimable. Two candidate routes
  remain — sight-driven detection (probe deployed, result pending) and
  `DesignateAttackPoint` (untested under good conditions). **The shape of
  `scan_area` depends on which, if either, works**, so the revision should wait
  for that answer or branch on it explicitly.

**Two design constraints the investigation surfaced, which the revision must
carry:**

- **Observation and engagement are different acts.** `SELECT TGT` commits
  Petrovich to tracking and, weapons free, to firing. A read-only
  `list_contacts()` must not select or mark.
- **Enumerating the list is not read-only** — it moves his selection, and
  scrolling hands the sight back to him. Also, observation state is *his*:
  he turns it off under hard manoeuvring, and every re-enable costs ~10 s of
  gyro alignment.

**Decisions from the original plan that are now moot or changed:**

- *Naming (`scan_area`)* — depends on which directed-scan route survives.
- *"Is body-layer-only acceptable as BL-6 done?"* — still a user call, but the
  calculus has changed: a real effector and a real outcome signal now exist, so
  shipping the body-layer half alone is a smaller fraction of the achievable
  milestone than it was.
- *`cancel_task`'s `AttentionArea` handling* — untouched by these findings,
  still open.
