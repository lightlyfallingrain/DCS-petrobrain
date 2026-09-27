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

- [ ] **Crossings are announced for contacts he cannot see.** *"Crossings say which way -> yes, but
  also says it for contacts outside FOV also contacts masked by cockpit."* This is a
  **no-omniscience violation**, the project's core invariant, not a wording bug: the direction-of-
  crossing callout fires off belief state without re-checking that the contact is currently visible
  (in FOV and not cockpit-masked). Highest priority of the four.
- [ ] **Binoculars are barely used.** *"Mostly using naked eyesight, even when should pick
  binoculars (automatically) to classify and identify contacts. Not even for watched. I did see the
  blue binocular cone in the debug tool a couple of times, but generally it was not used."* The
  binocular optic merged 2026-09-24 (`c398675`) and this is its first flown verdict: **fail**. The
  optic exists and is occasionally selected, so this is a policy/trigger defect rather than a
  missing capability.
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

**Moved to `todo/backlog.md` on 2026-09-27** — items keep their `X-B<n>` ids. This file stays the
source of truth for User priority tasks and session-scoped notes. The two changed on different
rhythms and shared one knowledge-graph cache entry, so each edit re-extracted the other.
