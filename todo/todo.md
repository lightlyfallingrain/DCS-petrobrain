# Todo

**Milestone status, backlog, and deferred items live in `../ROADMAP.md` (cross-subproject) and
each subproject's own `ROADMAP.md`** (`world-model/ROADMAP.md`, `aircraft-layer/ROADMAP.md`,
`body-layer/ROADMAP.md`) — not here. This file only holds User priority tasks and cross-cutting
items that don't yet belong to one subproject's roadmap. See root `ROADMAP.md`'s "Keeping this
current" note for how staleness is prevented: the `/merge` skill and the DoD agent both require
the relevant roadmap to be updated in the same push as any merge.

## User priority tasks
Prioritize any open task here over any other task in this file or roadmap files.

### Sortie 2026-09-26 — crew behaviour findings (user-flown, unfixed)

Flown on `main` after the audio-adapter hardening merge (`1a8795d`). **Passed:** scan-is-not-watch,
cancel-means-cancel, orange-means-watched. **Not testable:** free speech — the decider is still a
stub, so there is nothing that could answer; untestable before LLM wiring, not a defect.

Four findings, in the user's own words plus what each implies:

- [~] **Crossings are announced for contacts he cannot see.** *"Crossings say which way -> yes, but
  also says it for contacts outside FOV also contacts masked by cockpit."* This is a
  **no-omniscience violation**, the project's core invariant, not a wording bug: the direction-of-
  crossing callout fires off belief state without re-checking that the contact is currently visible
  (in FOV and not cockpit-masked). Highest priority of the four. **Fix merged (`fix/sortie-2026-
  09-26`, Fix A) — an observability gate with a grace window, DoD PASSED on fixtures/console.
  Awaiting the sortie that clears it**, tracked on `body-layer/ROADMAP.md`'s live-acceptance-debt
  list; leave this checkbox open until that flight confirms it.
- [~] **Binoculars are barely used.** *"Mostly using naked eyesight, even when should pick
  binoculars (automatically) to classify and identify contacts. Not even for watched. I did see the
  blue binocular cone in the debug tool a couple of times, but generally it was not used."* The
  binocular optic merged 2026-09-24 (`c398675`) and this is its first flown verdict: **fail**. The
  optic exists and is occasionally selected, so this is a policy/trigger defect rather than a
  missing capability. **Fix merged (`fix/sortie-2026-09-26`, Fix B1/B2) — an interrupted look no
  longer burns the retry budget, and time-based re-eligibility unlocks a watched/orbited contact
  held at constant range. DoD PASSED on fixtures/console; awaiting the sortie**, same
  live-acceptance-debt entry as above. **Sector coverage (all contacts in a scanned sector
  eventually get looked at, Decision 2a) is explicitly not part of this fix** — staged out as its
  own follow-on needing an `/explore` pass, see `body-layer/ROADMAP.md` Backlog.
- [ ] **The confirm band asks a question nothing can answer.** *me "cancel" -> P "cancel everything,
  confirm?" -> me "yes"/"confirm" -> P "no such command".* `render_confirm_request` (
  `body-layer/src/belief/speech.py`) emits "<X>, confirm?", but the vocabulary has no affirmative
  token at all — so the confirm band is unreachable by design, not mis-tuned. Needs an affirmative
  (and presumably a negative) token plus whatever holds the pending command between turns.
- [x] **"full scan" vs "scan full" — no defect, closed 2026-09-26.** *"I noticed myself saying
  'full scan', but the recognized format is 'scan full'. Both would be good."* Both already work.
  Ran the matcher directly: `"full scan"`, `"scan full"` and `"scan all around"` each resolve to
  `scan_full` at `match_ratio=1.0`, verb-anchored (`full` is in `VERB_ANCHOR_WORDS`, derived from
  `PHRASES` rather than hand-listed, which is why it came for free). The impression comes from the
  **F10 menu's own shape** — `petrobrain-f10-commands-hook.lua:156` nests it as Scan → "Full", and
  `crew_console.py:183` labels the token `"full"` — so the menu reads as "scan full" and nothing
  else advertises the alternatives. Nothing to change in the recogniser; if anything is worth doing
  it is making the spoken phrasings discoverable somewhere, which belongs with BL-10/SRS free
  speech, not here.

### State of play — end of 2026-09-24 (read this first after a context clear)

`main` is at `c912478`, clean and pushed. `feature/binocular-optic` merged today (`c398675`) and
the local branch still exists, unneeded.

**Three milestones are merged and unflown**, by the user's deliberate decision to merge before
flying — so any correction the sortie produces now lands on `main`, not a branch:
binocular optic, voice command completeness, precise position belief. The outstanding card is
`docs/acceptance/2026-09-23-eyes-and-voice-sortie.md`. **Name that card and that state whenever
asking the user to test.** Two things changed after it was written and are worth repeating to them:
the speech log now writes by default to `body-layer/logs/speech.jsonl` (every utterance, including
unrecognised ones, `t_wall` stamped — so garbling data accumulates with no flag to remember), and
belief now carries a fused covariance rather than quantised buckets, so ranges that feel *wrong but
consistent* are the new error model working, not a bug.

**Mission Interpreter passed its first real acceptance** (three missions the user built, Syria).
Verdict: tested and passed with notes. Both notes are deferred to the brain layer, deliberately —
building either now would stand up a second hand-rolled judgement layer the brain would replace.

**The brain layer is the bottleneck, and it is the only component with no plan file.** Four
already-built things now wait on it: free-text commands, BL-7's mission-phase relevance, MI-5's
question set, and anything conversational in BL-8's kneeboard. Its seams already exist and sit
idle — `BrainClient` has an `awaiting_reply_id` round trip designed in, `EscalationPayload` already
carries `partial_parse` and `situational_header`, and the tool API has been frozen at 15
deterministic tools since BL-6. Every free-text utterance already arrives correctly formed at
`NullBrainClient` and is dropped. So this is not an integration project; it is a model loop plugged
into an interface that has been waiting for it.

**`watch-reporting` is done, merged 2026-09-24** (`feature/watch-reporting`, all five stages) —
`plans/watch-reporting/plan.md`/`implementation.md`, `body-layer/ROADMAP.md`'s Status entry. Adds
`belief/threat.py` (the module BL-8's Stages 3/5 sit underneath) and threat.py's provenance data
is now committed. **Unflown**, same "merge before flying" posture as the three milestones above —
add it to the next acceptance card.

**Recommended next move: `/explore` the brain layer with the user before any architect pass.**
This project's repeated pattern is that the decisive constraint arrives *after* implementation
starts and reverses it. `plans/bl8-memory/plan.md` is also ready, decisions resolved, and is now
unblocked on `threat.py` existing.

**Done 2026-09-24, no longer gated:** re-enabled `performance-reviewer` and `security`, running
**once per whole feature, before DoD, not mid-feature** (user, 2026-09-24). Scoping in the user's
own terms: single-user, LAN-only, under active development; deeper effort once brain and memory are
done. The root `CLAUDE.md` "Agents" edit is made; it also records why the old blanket skip outlived
its premise (no lapse condition, while the project grew a live 5 Hz DCS pipeline, a LAN HTTP
surface and inbound speech capture).


- [x] Route crew-text speech callouts ("tank, 12 o'clock, 3 km" style contact reports, from
  `body-layer/src/belief/speech.py`'s `render_contact_report`/`route_event`) to the in-game
  Petrobrain overlay (`aircraft-layer`'s `POST /text/push` channel, `--overlay` flag). **Done
  2026-09-12, merged to main:** routing mechanism (`_print` sink, `"!! "` urgent prefix);
  lifecycle-content fix (proper unit type/clock/range/enrichment instead of raw classification
  enum); a third live-test round made crew-text output terser per pilot-usability feedback — no
  contact ids, `CONTACT_LOST` unreported, `CONTACT_CLASSIFICATION_CHANGED` gained a
  position-bearing line, `"UNKNOWN"` coalition placeholder dropped, range/enrichment distance
  rounded; `OP_GROUPSOMETHING` (ED's unclassified-unit fallback) mapped to `"group"`. All rounds
  live-acceptance-tested and confirmed by the user. Full history: `plans/overlay-speech-callouts/`.
- [x] Create integrity audit skill, see instructions @todo/integrity-audit-skill.md — `.claude/skills/integrity-audit/SKILL.md` created 2026-09-08. 6-phase diagnostic audit (inventory → cross-file consistency → staleness → genericity leaks → duplication/dead mechanisms → memory hygiene → classify+report); never self-edits config, writes dated report to `audits/system-integrity/`.
- [x] claude workflow changes — `AGENTS.md` updated 2026-09-08: new "Auto-Advance" section (proceed through Architect → Implementer → Reviewer → (loop) → DoD without stopping between stages) and Escalation Rules extended with the local/reversible/non-material autonomy criterion. Existing `UserPromptSubmit` hook already injects "apply automatically, no user input needed" each turn — left as-is per user decision to observe first; hook mirror-update deferred unless AGENTS.md alone proves insufficient.
    - [x] move automatically to next stage in worklfows: architecht -> implementor -> reviewer -> (loop back to implementer if fixes are needed) -> DoD. If there is genuine ambiguity or need for user input/verification/perception, stop and hand to user. In normal cases, proceed to next step in workflow.
    - [x] If multiple reasonable technical approaches exist, choose one when the tradeoff is local, reversible, and does not materially affect product behavior, future architecture, dependencies, cost or risk. Escalate consequential or difficult-to-reverse decisions or where there is ambiguosity about expected behaviour.
- [x] Roadmap restructure (2026-09-10): split milestone/backlog narrative out of this file into
  root `ROADMAP.md` plus per-subproject `world-model/ROADMAP.md` / `aircraft-layer/ROADMAP.md` /
  `body-layer/ROADMAP.md`. Reason: an integrity check found this file had drifted — three merged
  milestones (BL-3, BL-4, BL-5) and one merged feature (`overlay-clock-range-summary`) were
  missing entirely, because the "update the backlog" step was easy to skip and not enforced at
  merge time. Fix applied at the process level, not just the data level: `.claude/skills/merge/SKILL.md`
  and `.claude/agents/dod.md` now both require the relevant `ROADMAP.md` to be updated *in the
  same push* as any merge — see root `ROADMAP.md`'s "Keeping this current" note.
- [x] **Enable `performance-reviewer` and `security` in the default role sequence, once per whole
  feature before DoD (not mid-feature). DONE 2026-09-24** — gate cleared when
  `feature/binocular-optic` merged (`c398675`); root `CLAUDE.md`'s "Agents" section now states the
  once-per-feature-before-DoD rule, the user's scoping, and why the old blanket skip outlived its
  premise. Original text follows.
  User decision from the 2026-09-22→2026-09-25 retro (retro finding 1). Scoping, as the user
  stated it: this is for now a single-user, LAN-only project under active development; deeper
  security and performance effort comes once the important milestones (brain and memory) are
  complete — this is not "turn both roles fully on everywhere now," it's one pass per feature, and
  only starting after the named merge. Requires editing root `CLAUDE.md`'s "Agents" section, which
  currently says to skip both roles outright with no stated lapse condition — that missing lapse
  condition is exactly the gap this retro found. **Do not make that `CLAUDE.md` edit until
  `feature/binocular-optic` has merged** — this item is gated on the merge, not actionable yet.


### Model the 9K113 sight as an optic (deferred, 2026-09-20)

- [>] **Model the 9K113 Raduga-Sh as a selectable optic.** Deferred by the user while cones slice 1
  ships the naked eye and binoculars only. Not blocked on research — the groundwork is already done:
  - **Figures are recorded** in `body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`,
    by confidence class. Field of regard ±60° lateral, +20°/−15° vertical (sourced, English manual
    §3.4). Magnification ×3.3 wide / ×10 narrow, switchable in flight (`LCtrl+X`). Fields of view
    11.5° / 6.0° (user-supplied, unverified — and the pair is internally inconsistent, so 6.0° is
    the figure to doubt first).
  - **Calibration ground truth already exists.** `body-layer/tests/fixtures/vision_calibration.json`
    grades `9k113_wide` and `9k113_narrow` at all nine ranges alongside `naked_eye` and `binocular`.
    No sortie is needed to calibrate this — the screenshots were taken with all four columns.
  - **Three things the eventual slice must get right**, each already argued out: two optic entries
    rather than one plus a zoom state (magnification is switched in flight, and either mode can use
    either field); field of view and field of regard as *separate* fields (they differ by an order
    of magnitude — a few degrees seen at a time, anywhere within a 120°-wide arc); and the doors as
    real state (`НАБЛ.` opens the outer doors, needs hydraulic pressure, closing runs inner then
    outer — so "Observ off" means the sight genuinely cannot see, not merely that it is unselected).
  - **Depends on mode selection**, which is cones slice 2. An optic nothing can select is table data
    nothing reads — the reason the 9K113 entries were cut from slice 1 in the first place.
  - **`plans/watch-reporting/plan.md` Stage 4 (merged 2026-09-24) makes the strongest case yet for
    revisiting this deferral, and it is a different argument than the one that shelved it.** The
    9K113 was deferred as *more detail* — a third optic when two already worked. The case now is
    *identify the thing before it can shoot you*: class-level recognition (`recognition_extent_m /
    MEDRES_ANGULAR_RADIUS_RAD × optic.class_range_mult`) against a ZSU-23-4's own 2 NM (3,704 m)
    envelope resolves at 500 m unaided (13% of the way in) and 1,750 m through binoculars (47% in
    — already inside engagement range either way), but **3,500 m through the 9K113 wide field** —
    the envelope's own edge. It is the only optic in the table whose class-range multiplier
    reaches a SHORAD envelope's edge rather than deep inside it, and its multipliers (wide
    3.55/7.00/6.50) are already measured and sitting in `perception/optics.py`'s module docstring,
    waiting for a slice that wires them. Full arithmetic: `plans/watch-reporting/plan.md` Decision
    4d.
  - Also recorded there and relevant: the operator commands an angular **rate**, not a position, so
    pointing the sight costs time proportional to angular distance; the gyro-stabilised head needs
    **~3 minutes** from power-on before it is ready; and launch entry requires the sight line within
    0.86° of the airframe axis, which is a *firing* constraint and not a *seeing* one.


### Probe the mission-sandbox bridge (Investigator + Windows box)

- [x] **~~Probe whether `net.dostring_in` into the DCS mission scripting sandbox is reachable~~ — ALREADY ANSWERED, closed 2026-09-22.** It has been in production since 2026-09-13 (`petrobrain-f10-commands-hook.lua`, `net.dostring_in("scripting", …)` at 1 Hz). Closed as already-answered rather than as done — no work was performed. See `aircraft-layer/research/2026-09-22-mission-bridge-already-shipping.md`. Original text follows.

  **Probe whether `net.dostring_in` into the DCS mission scripting sandbox is reachable** from
  this project's `Export.lua`/Hook setup in single-player, and what it costs per poll. Raised
  2026-09-21. **This one probe unblocks two parked items**, which is why it is worth its own entry
  rather than sitting inside either:
  - **Unit velocity** for movement detection — `Object.getVelocity()` lives in the mission scripting
    environment and returns a vec3 per unit (`aircraft-layer/research/
    2026-09-21-unit-velocity-via-mission-scripting.md`). With the bridge, movement detection gets an
    exact `v⊥` instead of differencing two samples of a 5 Hz position feed.
  - **Fog and visibility state** — "detection under real world conditions", factor 3. The
    2026-09-20 deep read found Export carries no fog at all and named this bridge as the only
    candidate route.
  Deliverables: does it work in single-player; per-poll cost; whether results can be returned
  synchronously or must be pushed back through a side channel. **Do not design against the bridge
  before this is answered** — differencing positions remains the fallback for movement.


### Scan geometry: drop the invented radius (user direction, 2026-09-21)

- [x] **Remove `F10_SCAN_RADIUS_M` and make a sector scan unbounded. DONE, merged 2026-09-21.** User direction: *"get
  everything visible within a sector"* instead of a made-up cutoff. `belief/crew_console.py`'s
  `F10_SCAN_RADIUS_M = 3000.0` exists only because an F10 button carries no geometry the way the
  typed `scan-area <bearing> <range> <radius> <reason>` does, so the code had to invent a number.

  **The real objection is not that 3000 m is the wrong value — it is that the radius is a second,
  arbitrary limit layered on top of the real one.** What should bound a sector scan is what
  Petrovich can actually see. Measured against the current naked-eye envelope the constant is
  *non-binding for every ground unit* (armour 2333 m, Ural 2000 m, infantry 600 m are all inside
  3 km) and *wrongly binding* for the one thing that beats it — the S-300 mast at 8000 m, which a
  3 km area would have excluded from a scan that should have found it. A cutoff that does nothing
  except in the cases where it does the wrong thing is worse than no cutoff.

  Shape: `AttentionArea.radius_m` becomes `float | None`, `None` meaning unbounded, and
  `area_contains` skips the range test for it. The wedge still applies. The typed `scan-area`/
  `watch-area` console commands keep supplying a real radius — nothing about explicit geometry
  changes. Touches `belief/attention.py`, `tools.py`, `crew_console.py` and the task store, so it
  is a small data-model change rather than a constant deletion.

  Note it composes with the open "Scan commands should drive naked-eye perception" item: once a
  scan steers perception, "unbounded" means "as far as the optics and conditions allow", which is
  the honest answer and needs no constant at all.

- [>] **Anchored limited scan — "scan around that landmark / that unit" — deferred to the brain
  layer.** The other half of the same user direction: *"on purpose command a limited scan, probably
  around a landmark or another known unit."* A radius is genuinely meaningful there, and it comes
  from the thing being scanned rather than from a constant — a landmark's own extent, or a
  contact's position uncertainty.

  **This needs the brain layer, not merely voice** (user, 2026-09-21). An earlier draft of this
  entry deferred it to the voice era on the F10-scoping precedent — that richer command forms belong
  to BL-10/SRS, since a dynamically rebuilt contact list means collector-to-Hook menu pushes and
  `removeItemForGroup` traffic mid-flight for a menu the player still clicks through. That reasoning
  holds for the *input channel* but understates the requirement.

  Resolving *"that landmark"* or *"that unit"* is not transcription, it is **reference resolution
  against shared crew context** — which of the things we have both seen, and talked about, does
  "that" mean. That is the runtime cognition layer's job (`docs/concept/PETROBRAIN_RUNTIME.md`), not
  the transport's. A perfect transcript of "scan around that ridge" still leaves the hard part
  undone.

  `find_place` (`belief/tools.py`, backed by `query.search.find_place_by_name`) already resolves
  names to positions, so *name → place* is not the blocker. *Deixis → referent* is.


### Cones 2C sortie findings (flown 2026-09-21)

First flight of the o'clock scan loop. Six findings; two share a root cause.

- [x] **Show where Petrovich is looking. DONE, merged 2026-09-22 (`4f89fc8`)** — the overlay now
  names the cone he is looking at, which is what made the rest of this list judgeable.
  **Originally:** it gated the other judgements. The pilot
  could not evaluate two of the card's four blocks: *"very difficult to judge when I don't visually
  see where Petrovich is looking"*. The scan loop, the dwell, and whether a 16 s flank revisit feels
  attentive are all unjudgeable without it. An overlay line naming the current gaze o'clock
  (`gaze_at(t_sim, plan)` is pure, so this is a read, not new state) would make the next sortie
  evaluable instead of impressionistic. Cheap, and everything else waits behind it.

- [x] **Scan and Watch must be standing modes, not one-shot tasks. DONE** — the mode semantics
  merged with 2C (`4f89fc8`), and `watch_nearest`'s missing `PendingIntent` (flagged open at that
  merge, so `Cancel Task` still had nothing to find) closed in `32346a0`. Cancel now ends every
  governing kind and names each. Root cause of two findings.
  `belief/tasks.py`'s `tick` marks a task `succeeded` **the moment any contact is found in its
  area**, and `logger._active_gaze` only honours `status == "pending"` — so a commanded scan reverts
  to free scan on first contact, silently.
  - Observed: *"commanded scan left, still got reports from 12 o'clock"* — free scan visits 12
    twice per 16 s cycle.
  - Observed: `watch closest` → flew past and back → `cancel task` → *"nothing to stop"*. The task
    had already succeeded.
  - Pilot's expectation, and it matches `docs/concept/STATE_TRANSITIONS.md` where Scan and Watch are
    **modes**: *"should have been watching target and scanning forward"*. A mode persists until
    cancelled or replaced; a task completes.
  - `DEFAULT_SCAN_DEADLINE_S = 60.0` is secondary — it only bites when nothing is found. Do not tune
    it as a fix; the semantics are the defect.
  - Note the shape: the code is correct for what it was designed as. The design was wrong.

- [x] **Callouts must not be backlogged. DONE, merged 2026-09-22 (`bba090c`)** — nothing is
  rendered until the moment it is spoken, so a bearing cannot be stale by the time it is heard. Observed: *"I got callouts for unit at 12 o'clock when I
  had already flown past it several seconds ago."* A queue built ahead of time plays out stale.
  Pilot's own statement of the fix, and it is the right one: **"when a message ends, then determine
  what to say next."** Decide at speech time, from current belief — not at detection time.

- [x] **Aggregate repetitive callouts. DONE, merged 2026-09-22 (`bba090c`)** — the seven observed
  lines render as four in the fixture. Identification lines are never aggregated, which is what
  stops a BTR-70 disappearing into "three infantry". Seven lines observed where two would do:
  ```
  infantry, 12 o'clock, 0.5 kilometres.
  infantry, 1 o'clock, 0.5 kilometres.
  infantry, 12 o'clock, 0.5 kilometres.
  unit at 1 o'clock, very close is BTR-70.
  infantry, 2 o'clock, very close.
  infantry, 2 o'clock, very close.
  unit at 12 o'clock, very close is truck.
  ```
  Each line is *technically correct* — different units — which is why this is not a bug report but a
  model gap: three infantry at 0.5 km across 12–1 o'clock is **one group**, and the crew layer
  should say so. Interacts with the group-contact work (stage 4b/5) and with 2A.5's group intake
  cap, which already established that co-located units are one perceptual event.

- [ ] **No identification on a very close pass.** Observed: *"flying so close by a unit that I could
  clearly identify it, brought no identification."* Most likely the 30° focus cone missing it during
  a fast pass — a real crewman tracks a thing he has noticed. This is the attention-capture/dwell
  gap (2D, plus the peripheral channel that has no triggers). Confirm against a BL-9 trace before
  designing: if the unit never entered the cone, this is dwell; if it did and still did not reach
  the type tier, it is calibration.

- [ ] **16 s flank revisit — provisionally accepted, needs another look.** Pilot: *"seemed alright,
  needs more testing and fine tuning later."* Re-judge once gaze is visible.


## Cross-cutting / unscoped backlog

Items here are `X-B<n>`. A new one takes the next unused number; numbers are never reused or
renumbered, `[x]` items included (root `CLAUDE.md`, "Backlog Management").

### Added 2026-09-26

- [ ] **X-B1 — Make an unhandled thread exception fail the test suite, not just warn it.**
  `pyproject.toml` declares no `filterwarnings`, so `PytestUnhandledThreadExceptionWarning`
  warns and the run still reports "178 passed". Raised by the reviewer on
  `feature/aircraft-layer-hardening`, twice, and it is worth doing because **that warning is
  the mechanism that caught the original bug** on that branch: a background thread died with
  an `AttributeError`, every assertion in the test still passed, and only the warning said
  otherwise. A dead daemon thread that leaves a green suite is exactly the failure this
  project keeps meeting in the air. Affects every subproject's test config, not one file —
  which is why it is here rather than on a branch.

- [ ] **X-B2 — `CollectorServer.open()` never resets `self._shutting_down` to `False`.** Latent, not
  live: `__main__.py` opens once and closes once at exit, and no test reuses an instance
  across a cycle, so nothing exercises it today. But if an instance is ever reopened it would
  **permanently swallow real `accept()` failures** — turning the loud-failure guard back into
  the silent death it was built to prevent. One line in `open()`. Flagged non-blocking by the
  reviewer on 2026-09-26; worth taking the next time that file is touched.

- [ ] **X-B3 — `test_unexpected_accept_error_is_logged_loudly_and_the_loop_recovers` simulates
  shutdown by poking `server._socket = None` rather than calling `close()`**, so it never
  sets `_shutting_down` and its simulated-shutdown branch now exercises a dead code path.
  Harmless today (the assertion is `any(...)`, not an exact count) and purely cosmetic drift —
  worth fixing only if that test is edited for another reason.

### Added 2026-09-25 (user)

- [ ] **X-B4 — Probe whether DCS's own `land.isVisible` / `land.getIP` tests trees, and what a call costs.**
  User direction, 2026-09-25, arising from the vegetation-model decision recorded in
  `body-layer/ROADMAP.md` ("Detection under real world conditions", factor 1). **Gates the 9K113
  half of that decision and nothing else** — the statistical model for naked eye and binoculars
  does not depend on the answer, so this probe blocks one channel, not the work.

  **The question, precisely.** `Scripts/AI/Detection.lua` sets `trees_LOS_test_T4 = true` and every
  installed theatre is Terrain-4, so **ED's AI detection** samples tree geometry for line of sight.
  That is *not* the same claim as **the scripting API** doing so. Our own
  `query.line_of_sight.line_of_sight_clear` samples the bare terrain mesh, which makes us strictly
  more permissive through forest than the engine — so if `isVisible` does see trees, it closes a
  known gap for the one channel that can afford to call it.

  **Deliverables:**
  - Does `land.isVisible(from, to)` account for trees, or terrain only? A vehicle in dense forest,
    ray passing through canopy, is the discriminating case.
  - Does `land.getIP` return the blocking point, and is it more useful? It distinguishes "a ridge"
    from "the treeline 200 m short of the target", which the sight channel would want to *say*, not
    merely know.
  - Per-call cost, at realistic candidate counts.
  - Can a result return synchronously, or must it come back through a side channel? **This one was
    left open when the mission-bridge probe item was closed** — it was never the blocker there
    (velocity is a push), and it is the blocker here (LOS is a question).

  **The transport is not in question.** `net.dostring_in("scripting", …)` has been in production
  since 2026-09-13 (`petrobrain-f10-commands-hook.lua`, 1 Hz). This probe is about what the
  function answers and what it costs, not about reaching it.

  **Two weather questions ride the same bridge and should be probed in the same session** (user,
  2026-09-26, from the condition measurements):
  - **Can meteorological visibility be read?** It is a *ceiling* on detection for every instrument,
    not a per-optic multiplier — the user's own framing, and the measurements show it: in rain 2 the
    9K113 wide and narrow fields both detect at exactly 3.7 km despite very different magnification.
    `Export.lua` has no fog or weather getter (confirmed by reading the shipped file), so this
    bridge is the only candidate. `world.weather.getFogThickness()` is the named target. ED's own
    representation is a **time series** (`fog2.manual = {{time, visibility, thickness}, …}`), so
    whatever is built samples rather than reads once.
  - **Can *where* it rains be read?** *"Rain and clouds are not uniform in DCS. Moving will get you
    in and out of rain."* Whether any API exposes the spatial distribution is open, and it is the
    harder question: an ownship-local visibility figure is sampled in the right place but says
    nothing about whether the target sits under a squall. If nothing exposes it, the fallback is an
    ownship-local reading applied scene-wide, with the limitation stated rather than hidden.

  Investigator pass plus a probe on the Windows box. **Run it before the 9K113 slice is scoped, not
  during it** — if the answer is terrain-only, that slice's LOS design collapses and the
  statistical model has to cover every channel instead.

- [ ] **X-B5 — Run Reviewer, Performance Reviewer and Security on this repo's Claude configuration
  itself.** User direction, 2026-09-25. The config is treated as prose nobody reviews, while it is
  in fact the thing that decides how every agent behaves — and a defect in it is executed rather
  than read.

  Scope: `CLAUDE.md` (root and every subproject's), `AGENTS.md`, `docs/AGENT_ROLES.md`,
  `docs/PROCESS.md`, `.claude/agents/*.md`, `.claude/skills/*/SKILL.md`, `.claude/settings.json`
  hooks and its deny list, `.claude/scripts/`. Each role reads it as its own kind of artifact:
  **Reviewer** for contradiction between files and instructions that cannot be followed as written;
  **Performance Reviewer** for what the configuration costs per session and per agent — context
  loaded on every turn, hook latency on every tool call, agents spawned where one would do;
  **Security** for the hooks and scripts as executable surface, the deny list's actual coverage, and
  what an agent is permitted to do without asking.

  **Seed material already found, 2026-09-25, not yet acted on** — the skill-file sweep (`a5fd5ef`)
  surfaced these in files it was told not to edit:
  - Root `CLAUDE.md` hardcodes three subprojects in four separate sections (Current priority,
    Subprojects, Milestone Completion, Verification). There are six — `git ls-files '*/pyproject.toml'`.
    `brain-layer` has shipped code and is named in none of them. The same class of defect made
    `/check`, `/compile`, `/test` and `/dod-check` capable of reporting PASS while never looking at
    half the repo.
  - **A live contradiction**: root `CLAUDE.md`'s "Knowledge graph" says the graph is built from the
    `graphify-corpus/` mirror; `.claude/skills/graph-refresh/SKILL.md` says that mirror was removed
    because it broke cache lookups and leaked `graphify_corpus_*` into the graph's vocabulary, and
    that it must not be reintroduced. One of the two is wrong and the skill is the newer.
  - Root `CLAUDE.md`'s "Subprojects" sends readers to `todo/todo.md` "Current Focus" for BL-x
    status, which the same file's "Current priority" section says no longer holds milestone
    narrative. There is no "Current Focus" heading in this file.
  - Root `CLAUDE.md`'s "Agents" asserts a role count and that all roles use one model, immediately
    followed by its own dated exception — the shape that goes stale silently.
  - `AGENTS.md`'s "Roles (one-liners)" lists seven and omits `investigator`, which root `CLAUDE.md`
    describes at length. Its "Recommended Role Sequences" still points at a possible exemption of
    security/performance-reviewer that `CLAUDE.md` replaced on 2026-09-24 with a cadence.
  - `AGENTS.md`'s rule 2 still says "trial this before relying on it" inside a section headed
    "Status: all three rules in force".

  Note the precedent this sits on: the skill sweep was worth running because three of its findings
  were *already wrong at the time of the audit*, not merely aging. The same is likely here, and the
  blast radius is larger — `CLAUDE.md` is loaded into every session, so a wrong line there is
  believed by every agent from its first turn. Do not let the roles edit the config themselves;
  `integrity-audit` is deliberately diagnostic-only and this should keep that posture — report,
  then apply with the user in the loop.

- [ ] **X-B6 — An outpost fragments into 18 contacts at range — diagnosed, not fixed.** Found in a real
  sortie 2026-09-25 from `--belief-truth-log`; full analysis in
  `plans/contact-fragmentation-at-range/debug.md`. The user heard the same callout four times
  (*"ground, 11 o'clock, 1 kilometre."*) and asked why they did not collapse into a group.

  **It is not clustering** — the contacts were founded across ten different polls, so per-poll
  clustering never saw them together. It is association over time, and it is a **recurrence of
  `plans/contact-duplication-ambiguity-runaway/`'s runaway with a new trigger**.

  The counter-intuitive part, and the reason it took a log to see: the association gate is not too
  *tight* at range, it is too **loose**. `naked_eye_sigma_m` scales with range, so at 4 km the
  3-sigma gate accepts a 2.9 km down-range discrepancy. In a dense outpost several existing
  contacts therefore pass, `ingest`'s deliberate anti-guessing rule reads "2+ candidates" as
  ambiguous and founds a *new* contact, and that new contact makes the next look ambiguous against
  one more candidate. Object-permanence continuity is the existing protection and still correct,
  but it needs stable cluster membership, which a sweeping gaze, a marginal gate and
  `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL = 3` all churn.

  Four directions are listed in the debug note, none chosen — the anti-guessing rule is
  load-bearing and this needs a decision rather than a patch. Note also that contacts drift between
  real objects over a sortie, so any fix validated against the belief-truth join must account for
  the join re-resolving, or it measures itself.


- [x] **X-B7 — A real-time ASCII view of what Petrovich is looking at, and with what. Built 2026-09-25 (`feature/eyesight-view`) — `--eyesight-view`, plus `--belief-truth-log` below.** User, 2026-09-25:
  *"it'd help if I could visually see where Petrovich is looking and with what. A realtime ascii
  graphic would do just fine."* Shape, as he described it:
  - **Ownship at bottom centre**, because the rear hemisphere is not visible anyway — so the
    drawing is a forward arc, not a full circle.
  - **A cone or line drawn where he is looking**, coloured by optic: **green = naked eye, blue =
    binocular**.
  - **A one- or two-letter id per contact**: `AA` air defence, `AR` armour, `TR` truck, `G` group,
    `U` unknown.

  **What already exists, so this is not built from nothing** — and checking this first is the
  point of writing it down here:
  - `perception.gaze.gaze_at(t_sim, plan)` is **pure**, so the current gaze is a read, not new
    state. The cones 2C sortie already added an overlay *line* naming the gaze o'clock
    (`logger._push_gaze_line`) for exactly this need — the user's own words then were *"very
    difficult to judge when I don't visually see where Petrovich is looking"*. This item is the
    spatial version of that same complaint.
  - `--detection-trace` (BL-9) already records, per poll and per candidate, which visibility gate
    decided its fate, at what true range and bearing, plus the optic and the contact it folded
    into. `body-layer/tools/summarize_detection_trace.py` reduces it after a flight. **The data
    this view needs is already being written** — what is missing is a live rendering of it.
  - `perception.optics` carries the optic in use, so green/blue needs no new state either.

  So the likely shape is a reader, not a new subsystem: a terminal view fed from the same per-poll
  state the trace writer already sees. Worth confirming that read before designing anything.

  **Settled by the user, 2026-09-25: this is a debug, testing and calibration tool, and it may show
  ground truth.** His words: *"it's a debug and testing tool. Can break no-omniscience boundary
  because the whole purpose is testing, debugging and calibration."* So it draws what is really
  there alongside what Petrovich believes — that contrast *is* the instrument. A view restricted to
  belief could not answer the question it exists to answer, which is why he could not see something
  he should have.

  **The invariant that still applies, and it is a different one: the view must be read-only and
  one-directional.** No-omniscience constrains what *Petrovich* knows, not what the developer sees
  — but nothing this view reads may flow back into belief. `detection_trace_writer.py` is the
  precedent and the model: it is deliberately allowed to hold ground truth and belief at once, and
  it never calls anything that mutates `ContactStore`, and no ground-truth field it touches is ever
  passed into `ingest`/`Percept`/`Contact`. Build this the same way, and say so in its module
  docstring, because the next reader will otherwise assume the boundary was simply forgotten.

  Worth noting the same tension was already resolved this way once: `--detection-trace` holds both
  and is trusted precisely because the direction of flow is enforced structurally rather than by
  remembering.

- [ ] **X-B8 — Per-module performance review, findings written to a document, and that document becomes a
  backlog item.** User, 2026-09-25. Each subproject reviewed in its own right —
  `world-model/`, `aircraft-layer/`, `body-layer/`, `audio-adapter/`, `brain-layer/`,
  `mission-interpreter/` — rather than only the per-feature passes that have run since
  2026-09-24. Those per-feature passes found real things (LOS sampled before the range gate; a
  wedged-brain poll costing 5015 ms every cycle), but they only ever look at what one branch
  touched.

- [ ] **X-B9 — Per-module security review, same shape: findings to a document, document becomes a backlog
  item.** User, 2026-09-25. Same reasoning and same module list. Note the standing scoping the
  user set when re-enabling the role: single-user, LAN-only, under active development — so this is
  a survey for real exposure, not a hardening audit. The per-feature pass has already found one
  genuine item this way (a service binding all interfaces for no benefit), which is the argument
  for doing it systematically.

- [ ] **X-B10 — End-to-end latency measurement: where the time actually goes, and what would buy the most.**
  User, 2026-09-25: *"what are the latencies what are the bottle necks, what would bring greatest
  improvements?"* The whole chain, not one hop — PTT to recognised transcript, transcript to
  dispatched command, perception poll to spoken callout, escalation to brain reply. **This has
  never been measured end to end**; what exists is scattered and single-hop (whisper's own bench,
  the brain-layer model measurements, `describe_position`'s p99, the 5 Hz poll budget).

  The deliverable the user asked for is specifically the *ranking* — not a table of numbers but
  which single change would buy the most. Worth stating because a measurement pass that produces
  only numbers answers a different question than the one asked.

- [ ] **X-B11 — The knowledge graph was rebuilt under the OLD graphify node-ID format — the next rebuild
  needs `graphify extract --force`.** Added 2026-09-24, and this will fail silently if missed.
  The `/graph-refresh` on 2026-09-24 (3287 nodes, 5829 edges) used the extraction spec's
  *immediate-parent* ID format (`auth_session_validatetoken`). The installed skill's
  `references/extraction-spec.md` changed during that same session to a **full-repo-relative-path**
  format (`src_auth_session_validatetoken`), explicitly to keep same-named files in different
  directories distinct. The two formats produce different IDs for the same symbol, so the next
  incremental extraction will create **orphan ghost-duplicate nodes** alongside the existing ones
  rather than updating them — the spec names this outcome itself and prescribes
  `graphify extract --force` to rebuild cleanly. Nothing warns about it; the graph just quietly
  grows two of everything it touches. Do the forced rebuild *before* trusting any query after the
  next doc change.

  Also noticed then: the installed graphify skill is 0.8.41 against package 0.9.64
  (`graphify install --platform claude` updates it). Probably the same root cause as the spec
  change — worth updating in the same pass.


- [>] **X-B12 — Re-enable the performance-reviewer and security roles, and run a catch-up audit of what
  shipped while they were exempt. Deferred until Stage 4b of the group contact model is done**
  (user, 2026-09-19) — not because the finding is weak, but because interrupting the current run
  to re-audit would cost more than the risk carries today.

  **Both exempted roles independently reported their own exemption has gone stale**
  (`/retro`, 2026-09-18). `CLAUDE.md` says: *"Skip performance-reviewer and security for now — this
  phase is an offline single-user local pipeline with no hot path and no untrusted-input surface
  yet."* That was written for the World Model Builder's offline phase. It no longer describes where
  the work happens.

  **Performance reviewer's case:** this week's changes landed in `aircraft-layer` and `body-layer`,
  which are live runtime paths, not the offline pipeline the exemption describes. Two specific
  candidates: `AudioPlaybackSender`'s worker thread and queue, which carries an explicit
  interrupt-*timing* correctness requirement, and `perception.clustering`'s O(n²) single-link pass
  running **every poll**. Its recommendation is to narrow the exemption's scope to `world-model/`
  explicitly, so runtime subprojects stop being swept under a phase description they have left.

  **Security's case, which contradicts a judgement already recorded elsewhere:** `POST /audio/play`
  was merged with the framing *"same severity class as what already exists, not a new category"*
  (`plans/tts-voice-output/plan.md` Decision 6, relayed to the user as settled). Security disagrees,
  and the disagreement is about the right axis: the existing unauthenticated endpoints push overlay
  text and trigger in-sim commands, with effects confined to the **DCS process**. Audio playback
  reaches the **host OS** — arbitrary content from any LAN device reaching the user's speakers — and
  audio-play primitives have a history of path/codec-confusion and resource-exhaustion issues that
  text overlays do not. Its reading is that this crosses the exemption's own stated line, *"no
  untrusted-input surface yet"*, because the LAN is now an input surface. The earlier framing
  reasoned about authentication being unchanged; severity is determined by blast radius, which
  changed.

  **When picked up:** narrow or lift the `CLAUDE.md` exemption, restore both roles to the sequences
  in `AGENTS.md`, and run a Mode-2 deep analysis on `POST /audio/play` plus a performance pass on
  the two candidates above. Note the exemption is a *phase* decision — the lesson worth carrying is
  that it needed a re-scope trigger and had none, which is the same failure shape the retro found
  in four roles' memory files.


- [ ] **X-B13 — `console.py`'s typed `scan-area` still drives the 9K113.** Found by review 2026-09-17,
  while checking the F10-path fix (`89b8b1d`). `body-layer/src/belief/console.py:548` calls
  `aircraft_client.trigger_petrovich_search("forward")` under the name "Scan" — the identical
  semantic mismatch just removed from `crew_console._handle_scan`, where *Scan* is naked-eye
  perception and *Observ* is the 9K113 (`docs/concept/state-transitions.jpg`'s glossary).

  Left out of `89b8b1d` deliberately: it is pre-existing, `--console`-only (a developer debug
  tool), and no crew or F10 path reaches it, so folding it in would have expanded a reviewed
  commit's scope for no in-flight benefit. But it is not merely mechanical either — `scan-area`
  is the *typed* command that takes explicit geometry, so "what should it trigger instead" has a
  real answer to pick: nothing at all (matching the F10 path), or a future `Observ` once that
  verb exists. Decide that when `console.py` is next touched, rather than copying the F10 fix
  blindly.

  Until then the repo contains two paths named "scan" that do different things, which is exactly
  the kind of contradictory precedent a future reader would follow in the wrong direction.


- [x] **X-B14 — Scan commands should drive naked-eye perception.** Raised 2026-09-16 from the first live
  F10 test of `f10-command-vocabulary`; narrowed 2026-09-17 once `cockpit-visibility` shipped.
  **Closed 2026-09-21 by cones slice 2B** (`plans/detection-cones-slice2/plan.md`): a pending
  `scan_area` task's relative sector now resolves to a `perception.gaze.Gaze` each poll
  (`logger.py`'s `_active_gaze`/`_apply_active_gaze`) and filters `NakedEyePerceptionSource`'s
  candidates via a new gate ahead of the cockpit mask, so "scan left" now changes which contacts
  Petrovich can detect, not just which he is attending to. The "full version" (dwell time,
  naked-eye-vs-binocular tier varying with time-looking) below is 2C/2D's job, not this one's.

  **A scan changes attention, not perception.** `perception/visibility.py`'s naked-eye gate uses a
  fixed cockpit occlusion mask (`perception.cockpit_mask`, `plans/cockpit-visibility/plan.md`) that
  no command steers, so "scan left" registers an `AttentionArea` and a `PendingIntent` but does not
  change which contacts are detected. It raises attention on things the fixed mask already found.
  The 9K113 trigger removed on 2026-09-16 (`fix/scan-naked-eye-not-9k113`) was the only observable
  effect a scan had, and it was the wrong organ — so scan is now honest but perceptually inert
  until this is built.

  The mask's own mis-sourcing is now fixed — `NAKED_EYE_FOV_HALF_WIDTH_DEG` (the 9K113's angular
  limit, not a human-through-glass figure) is gone, replaced by a body-relative
  depression-per-azimuth mask derived from real co-pilot cockpit screenshots
  (`plans/cockpit-visibility/plan.md` D7 — still uncalibrated, ±10-15° at best, same debt class as
  `visibility.py`'s own tier constants, but at least sourced from the right thing now).

  What the full version looks like, per the spec diagram: a steered *sub-window* within that mask
  that follows the commanded sector for the task's duration, plus the diagram's default-state sweep
  (`ahead → left → ahead → right`), dwell time per sector, and naked-eye vs binocular tier varying
  with how long Petrovich has been looking somewhere. That needs a dwell/attention scheduler that
  does not exist. Composes with, not duplicates, the static mask (`plans/cockpit-visibility/plan.md`
  D4): the mask is what the airframe permits him to see at all, always applies; scan steering is
  where he is currently looking within that, dynamic. Effective visibility is the intersection.

  Deliberately deferred by user direction 2026-09-16 ("write entry in backlog for full pattern
  simulation, but for now simply remove 9K113 trigger").

  **Compass/absolute scans still never reach `_active_gaze` — measured again 2026-09-23 while
  scoping `plans/voice-command-completeness/plan.md`.** `_active_gaze` only ever converts a
  `scan_area` task's `relative_sector` field into a `perception.gaze.Gaze` (cones slice 2B, above);
  a compass scan sets `area.sector` instead, so `scan north`/the quantised `scan_bearing_deg`
  fall through to `FREE_SCAN_PLAN` exactly as before that slice landed. A pilot who hears
  `"Scanning northwest."` and gets free-scan behaviour reads it as broken. Named explicitly, not
  silently reopened, by `voice-command-completeness`'s own Decision 5/Risks section, and deferred
  to that plan's Stage 5 alongside the item below (both land together: the clean fix is
  `_active_gaze` converting an absolute `area.sector` into relative o'clock legs per tick using
  current heading, the same generalisation the o'clock-scan item needs anyway).

  **Closed by Stage 5** (`plans/voice-command-completeness/plan.md`, `logger._active_gaze`):
  a `sector`-only task now also resolves, converted to `ScanPlan.commanded_legs` every poll via
  the new `perception.gaze.legs_within_wedge`, using that poll's own ownship heading — `scan north`
  now steers `NakedEyePerceptionSource`, not just an `AttentionArea`. **Unflown as of merge.**

- [x] **X-B15 — Ownship-relative o'clock scan tokens — deferred to Stage 5 of `plans/
  voice-command-completeness/plan.md`, user direction 2026-09-23.** The command vocabulary has two
  frames and only one has fine granularity: absolute (`north`/`315 degrees`, coarse and fine both)
  vs. ownship-relative (`left`/`right`/`ahead`/`full`, coarse only — `left` spans a 90° wedge, three
  o'clock hours). *"'scan 1 o'clock' directs scan at a narrow sector that is own ship relative.
  That is needed"* (user). Nine new tokens (`scan_clock_1..12`, matching the report family's own
  nine forward hours), **unbenched** — no recordings exist for them, same cost that kept
  `cancel_scan`/`cancel_watch` off voice until 2026-09-23; cheapest when the corpus is next
  re-recorded. The real cost is geometry, not vocabulary: a single o'clock hour is not expressible
  as a `RelativeSector` today (`perception.gaze._SECTOR_LEGS` only has `ahead`/`left`/`right`/
  `full`), so the clean generalisation is `ScanPlan` carrying legs directly (an o'clock command is a
  one-leg plan, exactly like `ahead` already is) rather than widening the `RelativeSector` literal
  and rippling through `_RELATIVE_SECTOR_WEDGE_DEG`/`belief.attention`'s re-export/the label
  tables — the same generalisation that would also fix the compass-scan-gaze gap immediately above,
  which is why the two items are sequenced to land in the same stage.

  **Closed by Stage 5**: `scan_clock_1..12` dispatch through `CrewConsole._handle_scan`'s new
  `relative_clock_hour` parameter, registering a one-leg `ScanPlan.commanded_legs`; the nine
  tokens are unbenched, as flagged above — next corpus recording's job. **Unflown as of merge.**


- [ ] **X-B16 — Stage 5 road junctions: pathological single-chunk stalls — CONFIRMED DATA-DEPENDENT.** Raised
  2026-09-16 from the `syria-full` build log validating `osm-landcover-optimization`. Stage 5 took
  2885 s, and a large share of that sat in a handful of chunks: chunk 13867→13868 took 331 s and
  chunk 14017→14018 took 337 s (one chunk each), with two further ~330-350 s near-stalls around
  them — roughly 28 of the 48 minutes in a few chunks. This is exactly the gap `b260ee7`
  (road-junction progress logging) named as remaining: *"nothing is logged during a single slow
  chunk."* Confirmed in the wild, plus a second symptom — the ETA swings badly during a stall
  (495 s → 1657 s remaining), so the estimate actively misleads. Two separable pieces of work:
  (a) log progress *within* a chunk, or at least emit a "chunk N still running, Xs elapsed"
  heartbeat so a stall is distinguishable from a hang; (b) find out why those specific chunks are
  so expensive (dense urban road clusters? a union-find degenerate case?) — the fix may be a
  chunk-splitting heuristic rather than better logging. Not scoped to a milestone; `world-model`.

  **Update 2026-09-16 — reproduced on a second machine, at the identical chunk indices.** A Mac
  `syria-full` build hit exactly the same four chunks (13867, 13868, 14017, 14018) that stalled on
  Windows, at ~170 s each versus Windows' ~330 s. Same indices, different OS and different CPU, so
  this is a property of the *data in those chunks*, not of the machine — which makes (b) tractable:
  those four chunk bounding boxes can be extracted and profiled directly rather than hunted for.
  They cost ~680 s of the Mac run's 1,038 s total, so fixing them is most of Stage 5's wall-clock.
  Stage 5 overall was much faster on the Mac (1,038 s vs 2,885 s), as were roadnet (444 s vs 670 s)
  and SRTM (4.4 s vs 11.3 s).

  Unrelated caveat when reading `world-model/syria-full-build.log`: it contains a 2.5-hour wall-clock
  gap mid-Stage-5 that is **not** a stall. The host slept. The progress lines' own `elapsed` counter
  advanced only 201 s across it, because `ingest_junctions`/`roadnet.routes` both use
  `time.monotonic()`, which on macOS does not tick during system sleep. Wall-clock timestamps and
  logged elapsed disagree by design there.

- [ ] **X-B17 — `syria-full` pipeline logs only 6 of 8 stages.** Raised 2026-09-16 from the same build log.
  Output goes `[6/8] SRTM elevation grid: done` straight to `Built ...` — `[7/8]` and `[8/8]` never
  appear. `probe: skipped (probe_output_path not given or not found)` accounts for at most one of
  them. Either the remaining stages are silent (no `starting`/`done` lines, unlike stages 1-6) or
  `_TOTAL_STAGES` overcounts. Cosmetic but misleading during a ~1 h build. `world-model`.

- [ ] **X-B18 — SRTM: 131 tiles staged, `tiles_used=79`; 7.4% of points void-or-uncovered.** Raised
  2026-09-16 from the same build log. The pipeline header reports `SRTM elevation grid (131
  tile(s))` but `SrtmIngestStats` reports `tiles_used=79` — 52 staged tiles contributed nothing.
  Separately `points_void_or_uncovered=47484` of `points_expected=639216` (7.4%). The M7 entry
  already records 92.6% coverage as an accepted result, so this is likely the known gap rather
  than a regression, but the 131-vs-79 discrepancy is unexplained and worth one look: if the 52
  unused tiles are outside the region bbox that is fine and the header should say so; if they
  overlap it, coverage is being lost. `world-model`.

- [ ] **X-B19 — Pin `CLASSIFIER_VERSION` bump discipline with a test.** Raised 2026-09-16. The comment
  above `CLASSIFIER_VERSION` (`world-model/src/build/ingest_osm.py`) lists the conditions that
  force a bump; `638239a` met two of them and landed without one, and was caught only by reading a
  build log weeks later. Nothing mechanically enforces the rule. Options: hash the relevant
  functions'/dataclass' source and assert the digest matches a pinned value alongside the version
  (fails loudly on any edit, forcing a conscious bump), or derive the cache key from such a digest
  instead of a hand-maintained integer. The second is the real fix but changes the invalidation
  key's shape. `world-model`.


- [ ] **X-B20 — Landmark references must be LOS- and knowledge-gated, not ground-truth.** Raised
  2026-09-13, while scoping world-model tactical-landmark enrichment (ridges/valleys,
  settlements, road intersections, other aerial landmarks — see
  `plans/world-model-tactical-landmarks/plan.md` once it lands). World-model can compute
  "this unit is 500m from a road intersection, south of a large building," but per this
  project's no-omniscience invariant, Petrovich/the brain must never speak a landmark
  reference the crew has no actual basis for knowing. Two independent gates, both needed:
  1. **Line-of-sight**: can we (or Petrovich) actually see the landmark itself right now, using
     the generalized A↔B LOS primitive (`plans/world-model-los-generalization/plan.md`,
     `query.line_of_sight.line_of_sight_clear`) applied ownship/Petrovich → landmark position,
     not just ownship → contact.
  2. **Knowledge**: do we have a standing memory of that landmark (a prior perception/
     observation of it — this is squarely BL-8's future territory), or does the Mission
     Understanding / briefing (Mission Interpreter's schema, `plans/mission-interpreter/
     plan.md`) name it explicitly? If neither, the landmark is not known and must not be
     referenced, even if world-model's query layer can compute its existence and position from
     ground truth.
  **Not scoped to a milestone yet** — spans world-model (landmark data + LOS query),
  mission-interpreter (briefing-named landmarks as a knowledge source), and body-layer
  (the actual gating logic before a landmark reference reaches speech output, likely a
  `belief/` concern parallel to `percept.py`'s existing DCS-truth-stripping boundary). Revisit
  once world-model's landmark enrichment and a first Mission Understanding schema both exist.

- [>] **X-B21 — "Wingman brain" — a much later, far-future direction.** Raised 2026-09-13, deliberately
  deferred, not scoped. Combines observation + flight control + world perception from a
  *non-player-position* aircraft — i.e. an AI-controlled wingman with its own Petrobrain-style
  cognition, not just Petrovich riding along in the player's own cockpit. A materially different
  architecture from everything built so far: today's aircraft-layer/body-layer split assumes
  perception is anchored to the player's own ownship telemetry throughout (`OwnshipState`,
  `perception/geometry.py`'s bearing/range math, `aircraft_client`'s `/telemetry/latest`). A
  wingman brain would need perception/state for an aircraft that isn't the player's — a new
  telemetry source, not a reuse of the existing one. Do not start scoping this until the current
  three-layer architecture (world model, mission interpreter, body/brain layer) is mature and
  proven for the single-player-aircraft case first.
