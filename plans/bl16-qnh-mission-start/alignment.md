## Plan check — 2026-11-16

**No goal-aligner pass on file.** Per the dispatching brief, the main loop skipped it because the
pilot stated the goal and its why verbatim. Expectations below are reconstructed straight from the
pilot's own words in `docs/acceptance/2026-11-16-bl16-batch-a-feedback.md` ("The barometric bug"
and "Explore — the pilot's answers"), labelled as reconstructed, not derived by this role.

**Verdict: CONCERNS**

| expectation | stage | status |
|---|---|---|
| E1 — set the operator altimeter to the mission's QNH ("Petrovich must set altimeter pressure setting to the actual pressure value from weather or briefing"; "use QNH for copilot") | Stage 3 (`_maybe_start_altimeter_qnh_sync`) | met |
| E2 — fires at both ground start and air start ("set at mission start, both ground start and air start") | Stage 3 (both `_maybe_switch_theatre` call sites, no `on_ground` branch) | met |
| E3 — the knob is actually driven until the window reads the target, not fired-and-forgotten ("must set"; gain unmeasured so it has to be closed-loop) | Stage 2 (`advance_altimeter_qnh_sync` secant loop) + Stage 3 (poll-loop wiring) | met |
| E4 — no probe flight first; the first live flight is the test, and must be legible ("Skip the probe, just build setting QNH") | Stage 4 (the card), design throughout | met |
| E5 — a non-responding knob (e.g. written from the pilot seat) is detected, stopped, and told to the pilot once — never silent, never retried forever | Stage 2 (`failed_no_response`/`failed_timeout`, bounded iterations/duration) + Stage 3 (`altimeter_qnh_failed_pending`/`drain_altimeter_qnh_failed`, "unable, …" line) | met |
| E6 — does not interfere with the takeover fix or with the pilot flying | "The closed loop" (non-blocking per poll) + "Risks & Unknowns"/"Second-order effect" (additive, no shared state) | met |
| E7 — the goal itself targets the right physical quantity (QNH vs QFE) | *none* | **missing** |
| E8 — dynamic-weather missions, where `qnh` may not be meaningful, are handled rather than silently producing a wrong reading | "Risks & Unknowns" (named, not resolved, no tracked ID) | missing (disclosed as prose risk, no `[[ID]]`/Stage target — per the "deferred must name a home" rule this is not a valid deferral) |

### Findings

1. **The plan's own cited research contains an unresolved doubt about the goal parameter, and the plan drops it rather than carrying it forward.** — lens: grounded in / findings that change direction
   - `aircraft-layer/research/2026-11-16-mi24p-operator-altimeter-recon.md` section E, "QFE versus
     QNH — raised for the pilot": the 670–790 mmHg window fits QFE at elevated airfields (standard
     Soviet practice), the in-cockpit checklist item reads "QFE ON ALTIMETERS — SET", and
     `Hint_localizer.lua` names the knob itself "Baro pressure **QFE** knob" — and the note states
     plainly, **"The pilot chose QNH (2026-11-16) before this was found."** If ED's AI reads the
     operator gauge as height above the departure field rather than above sea level, QFE — not
     QNH — is the value that actually fixes the wild-barometric-target bug this feature exists for.
   - `plans/bl16-qnh-mission-start/plan.md`'s "Why, and what is already known" and "Risks &
     Unknowns" sections summarise the same research note's other findings (the knob's gain, the
     no-response risk, the dynamic-weather caveat) but never mention QFE at all — not as a risk, not
     as a settled-and-rejected alternative, not as a question. A reader of the plan alone has no way
     to know the doubt exists.
   - The pilot's later "Skip the probe, just build setting QNH" came after the research note
     existed, so this may already be a reconfirmation — but the note's own wording ("raised for the
     pilot") reads as flagged, not yet put to the pilot as a direct question, and the plan had the
     chance to re-surface it and did not. This is the retro's own failure shape in miniature: a real
     finding, on file, that never reached the one place (the plan, then the pilot) that would act on
     it.
   - **In the sim:** if the bug's true cause is a QFE/QNH mismatch and this feature sets QNH instead,
     the wild barometric target may persist in some fraction of missions (those where field elevation
     is large enough for the QFE/QNH gap to matter) even after this ships, and the symptom would look
     like "the fix didn't work" rather than "wrong physical quantity" — expensive to diagnose a second
     time once this is believed closed.

2. **The dynamic-weather caveat is disclosed but has no tracked home.** — lens: deferred-must-name-a-home
   - The plan's own words: *"this plan reads whatever numeric value the mission reports and acts on
     it at face value; if dynamic weather turns out to report a nonsensical static `qnh`... that
     surfaces as a wrong cockpit reading... worth a dedicated research note the first time it is
     observed, not solved speculatively here."* This is a real, named risk — but it names no
     `[[ID]]` and no stage, only "the first time it is observed." Per the retro lesson this role
     exists to prevent, an expectation (or here, a risk) with no tracked home is the one that gets
     quietly dropped, because nothing downstream re-reads this file. Lower severity than Finding 1
     (it is at least on the record), but the same shape.

3. **U1/U2 serve the pilot.** — lens: the pilot would see
   - **U1 (silent on success):** matches the existing mission-start sequence convention (mostly
     empty `petrovich-says` cells) and is cheap to reverse if a live sortie shows the pilot wants
     confirmation. No concern.
   - **U2 (two sorties, ground + air):** directly required by E2 ("both ground start and air
     start" is the pilot's own wording) — a ground-only card would leave the air-start path, the one
     that matters most for the takeover fix, unverified. No concern.

### Questions for the user

1. The Windows recon found the operator altimeter's in-cockpit hint/checklist text names it a
   **QFE** knob, and the 670–790 mmHg window fits QFE better at elevated fields than QNH — raised
   after you'd already picked QNH. Do you want to proceed with QNH as planned, or should this
   target QFE (≈ QNH − elevation / ~11 m per mmHg) instead, before it ships?
2. Should a dynamic-weather mission (`atmosphere_type = 1`) be handled explicitly here (skip the
   sync, or flag it distinctly), or is "wrong reading on a dynamic-weather flight, investigated the
   first time it's seen" — as the plan currently has it — good enough for now?
