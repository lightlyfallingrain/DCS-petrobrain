# Todo

**Milestone status, backlog, and deferred items live in `../ROADMAP.md` (cross-subproject) and
each subproject's own `ROADMAP.md`** — not here. **Take the subproject list from root `ROADMAP.md`'s
status table, never from a list written in this file**: three were named here long after six
existed, which is the same enumeration defect root `CLAUDE.md` warns about and which has now
recurred four times in this repo. This file only holds User priority tasks and cross-cutting
items that don't yet belong to one subproject's roadmap. See root `ROADMAP.md`'s "Keeping this
current" note for how staleness is prevented: the `/merge` skill and the DoD agent both require
the relevant roadmap to be updated in the same push as any merge.

## User priority tasks
Prioritize any open task here over any other task in this file or roadmap files.

### Sortie 2026-09-28 — user-flown, two findings

Flown on `main` with the brain wired to Ollama (the user's own `run-scripts/` edits: `--decider
ollama`, `--brain-client http`). **The confirm-band fix was not in this flight** — it is unmerged
on `fix/confirm-band-affirmatives`.

- [ ] **Grouping is the priority: every unit gets its own callout and it is far too much noise.**
  User's words: *"we badly need grouping, currently all units get single call outs and it's way too
  much noise. Fixing this is priority."* This is **X-B6** (`todo/backlog.md`), diagnosed
  2026-09-25 from a `--belief-truth-log` and never fixed — an outpost fragmenting into 18 contacts,
  the same *"ground, 11 o'clock, 1 kilometre"* heard four times. Full analysis:
  `plans/contact-fragmentation-at-range/debug.md`.

  **The diagnosis is counter-intuitive and worth not re-deriving**: it is not clustering (the
  contacts are founded across different polls, so per-poll clustering never sees them together) and
  the association gate is not too *tight* at range but too **loose** — `naked_eye_sigma_m` scales
  with range, so at 4 km the 3-sigma gate accepts a ~2.9 km down-range discrepancy, several
  existing contacts pass, `ingest`'s anti-guessing rule reads "2+ candidates" as ambiguous and
  founds a *new* contact, which makes the next look ambiguous against one more candidate. A
  recurrence of `plans/contact-duplication-ambiguity-runaway/`'s runaway with a new trigger.

  **CORRECTION, same day, from reading the actual log** (`plans/contact-fragmentation-at-range/
  2026-09-28-log-analysis.md`): **this is not X-B6.** The attribution above was made before anyone
  opened `~/dcs-belief-truth.jsonl` and it is wrong. In the longest run, **3 of 52 contacts were
  ever plural**, and two other runs had none at all — against 62 distinct real objects, which is
  close to 1:1 and the *opposite* of X-B6's one-outpost-becomes-18 signature. Clustering and
  cardinality are working; they are correctly concluding that vehicles tens of metres apart at
  2 km are individually resolvable.

  The noise is the **callout policy**: one resolvable vehicle produces one callout, roughly one
  every eleven seconds for half an hour, and 4310 of 5996 belief rows sit at `PRESENCE`/
  `OP_GROUPSOMETHING`, so nearly every line is the same words. Speech-time aggregation exists
  (`belief.callouts.group_candidates`) but needs members pending *simultaneously* and sharing the
  same range *word* — detections trickle in one per poll, and `"2 kilometres"` versus
  `"2.5 kilometres"` are different buckets, so it almost never fires.

  So the lever is how long Petrovich waits before speaking and how coarse the buckets are, not the
  association gate. **X-B6 stays open and unfixed** — a genuinely separate defect from a different
  sortie shape, whose 3 → 5 mitigation was never re-flown — but it is not what made this flight
  loud.

  **Needs the user's judgement before any plan**: what a crew member should *say* when sixteen
  individually-resolvable vehicles sit in one sector. The 2026-09-19 vocabulary decisions do not
  cover it — they assumed the plural case arrives as one plural contact, not as sixteen singular
  ones.

- [ ] **Free text reaches the brain and comes back "Unable, no such command."** User's words:
  *"'free text' is escalated to brain, but it comes back to 'unable, no such command'. While brain
  may work, we do not have sufficient command vocabulary -> no sensible speech from brain."*

  **This is the closed-set design working as specified, not a bug** — `brain-layer/src/decider.py`
  classifies against a fixed command vocabulary and returns `NO_SUCH_COMMAND` when nothing in it
  matches, and `speech.py` renders that as "Unable, no such command." So the ceiling is the
  vocabulary, exactly as the user diagnosed: the model can only ever say what the closed set lets
  it say, and a pilot speaking freely is mostly outside it.

  **DECIDED (user, 2026-09-28): let the brain answer questions about what he believes, without
  commanding anything.** Chosen over widening the command set or merely making the refusal honest.
  The tool API this needs already exists and has been frozen since BL-6 (15 tools,
  `belief/tools.py`), and the brain already holds a body-side trust boundary that re-validates every
  model reply against body-owned data (D10) — so this is a new *intent class* through machinery
  that is built, not new machinery. Not started; read `plans/brain-layer/plan.md` D11 (the closed
  reason set) and D4 (contact reference resolution) before scoping, since a question about a
  contact has to resolve which contact it is about, and that resolver is the same one `follow` uses.

  Worth naming the boundary while scoping: a question answered from belief must be answerable
  *wrongly* when belief is wrong. "How many trucks?" gets the believed count, not the true one —
  the no-omniscience invariant applies to answers exactly as it applies to callouts.

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
  own follow-on needing an `/explore` pass, see `body-layer/BACKLOG.md` (BL-B20).
- [~] **The confirm band asks a question nothing can answer.** *me "cancel" -> P "cancel everything,
  confirm?" -> me "yes"/"confirm" -> P "no such command".*

  **The diagnosis written here on 2026-09-26 was wrong and is kept for the record**: it said "the
  vocabulary has no affirmative token at all — so the confirm band is unreachable by design". It
  is not. `belief/voice_commands.py` already had `_AFFIRM_WORDS = {affirm, affirmative, yes,
  roger}`, `PendingConfirmation` already held the command between turns, and
  `handle_transcript` already checked both before anything else. Writing that from reading the
  symptom rather than the code cost a day of the item reading as bigger than it was — the
  project's own "verify state, not the account of it" rule, applied to a defect report.

  What was actually wrong (fixed on `fix/confirm-band-affirmatives`, 2026-09-28, unflown):

  1. **The question asks for a word the answer set rejected.** `render_confirm_request` renders
     "<X>, confirm?" and `"confirm"` was not an affirmative — the pilot's own report is
     *"yes"/"confirm"*, and echoing the operative word back is the most natural answer there is.
     Widened to include `confirm`/`confirmed`/`correct`/`yeah`/`yep`/`ok`/`okay`, and the
     negatives to include `nope`/`belay`. **Widening the set took four review rounds to make
     safe, and the lesson is worth more than the fix.** Each round produced one plausible rule
     that was right about the case motivating it and broke something the previous one had right:

     - *first word is an answer word* → swallowed `"okay watch that truck at three o'clock"`;
     - *every word is an answer word* → rejected `"yes do it"`, and a rejected answer inside the
       window does not say "say again", it **silently discards the pending command** — so the
       cancel simply would not happen, worse than the original defect;
     - *`verb_anchored`* (the matcher's verdict) → broke bare `"roger"` and `"negative"`, which
       had worked before this branch existed: `VERB_FLOOR` is 0.5 fuzzy, so `roger` anchors
       against `report` at 0.55, and `disregard` *is* the `cancel_nevermind` phrasing at 1.00;
     - *the anchor for multi-word utterances* → still broke `"roger wilco"` and `"negative hold
       off"`, because the anchor is computed from the **first word alone**, so an answer word
       that anchors intercepts the whole utterance whatever follows it.

     What is in the code is the union, ordered: (1) whole transcript is answer words → that
     answer, consulting nothing else; (2) else the matcher resolved a real command **token** →
     not an answer; (3) else first word is an answer word and ≤ 4 words → that answer. Every
     round was found the same way — by running the real matcher end to end rather than trusting
     a test that supplied its own default for the parameter under scrutiny.
  2. **`CONFIRM_WINDOW_S` was 8.0 s, measured from when the question was *decided*, not heard.**
     The round trip it has to cover is TTS synthesis + playback of the question + the pilot
     hearing, deciding, holding PTT and speaking + Whisper `small.en` (p90 1.46 s) + one 1.0 s
     body poll ≈ 6.5–7.5 s with nothing going wrong. Raised to 15.0 s. Still not measured end to
     end — a sortie should set it.
  3. **A late yes/no escalated to the brain**, which is literally where *"Unable, no such
     command."* came from (`decider.py`'s `NO_SUCH_COMMAND`). That wording says the *command* was
     rejected when in fact the *answer* was late. A yes/no word within `CONFIRM_LATE_ANSWER_
     GRACE_S` (20 s) of expiry now draws "Say again?" instead, which prompts the retry that works.

  `cancel` always routes to the confirm band whatever its match ratio, so this hit every single
  cancel. Leave this open until a sortie confirms "cancel" → "confirm" → the task actually stops.
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

### Where the state of play lives — not here

**A dated "state of play" narrative used to sit in this spot, headed "read this first after a
context clear". It was removed 2026-09-27 because it had gone wrong in every particular**, while
still instructing a cleared session to trust it first: it named `main` at `c912478` (~30 commits
behind), called three milestones unflown and pointed at
`docs/acceptance/2026-09-23-eyes-and-voice-sortie.md` as the outstanding card — root `ROADMAP.md`
records all three as flown and closed 2026-09-25 — and said the brain layer was "the only component
with no plan file" after `plans/brain-layer/plan.md` landed and BR-1 Stages 1–2 merged.

That is not an update that was forgotten; it is a second source of truth, which drifts by
construction. Root `ROADMAP.md`'s own "Keeping this current" note already says a disagreement
between a roadmap and this file is a bug in the update discipline, not ambiguity to guess through.
The 2026-09-10 restructure removed one of these narratives for the same reason; this was the second.

**So after a context clear, follow `CLAUDE.md`'s Session Start protocol** — the subproject
`ROADMAP.md` files for status, this file for User priority tasks, `todo/backlog.md` for
cross-cutting items, and `git branch -v --sort=-committerdate` plus `git worktree list` for what is
actually underway. Nothing in this file is a substitute for that last step.


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
