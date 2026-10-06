# AA-3 — Slice 2 — cockpit state drives the audio

- [x] **Slice 2 — cockpit state drives the audio. FLOWN, TESTED AND ACCEPTED 2026-10-05** #status/done (user:
*"SPU-8 feature works, tested and accepted."*). Merged `be12734`. Un-deferred the same day the
user wrote the behaviour out in full (the user wrote the
behaviour out in full; it was `todo/SPUU-8.md`, folded in here and the loose file deleted).
Replaces the original SRS ICS injection, which is cancelled with the SRS dependency itself.

**Built, merged and accepted on 2026-10-05 — the whole slice inside one day.** Architect →
Implementer (both cross-machine, on the Windows box) → full gate sequence here → flown by the
user → accepted. **The acceptance flight also clears the two uncalibrated constants**
(`ON_GROUND_AGL_THRESHOLD_M = 10.0`, `MISSION_START_ICS_DELAY_S = 5.0`) and Performance's one
unmeasurable item, the three added per-frame cockpit reads in `Export.lua` — the user flew it
and accepted, so no stutter was reported. All five stages below (telemetry, capture gating,
playback gating + volume, mission-start ICS write, on-ground silent default) are implemented
against this entry's own spec, with Architect/Implementer having run cross-machine ahead of any
gate, a Security `NEEDS FIXES` (unguarded `ValueError` that could permanently kill the audio
worker thread — fixed and re-approved) and a Performance `APPROVED — MONITOR` (the one
unmeasurable item: three added per-frame cockpit reads in `Export.lua`, reasoned as the same cost
class as the existing PTT read but needing a live sortie to confirm no stutter). Full record:
`plans/spu8-intercom/{plan.md, implementation.md, review.md, security-deep-analysis.md,
performance.md, dod-check.md}`. **Live acceptance is tracked as debt, not waived** — see
`body-layer/ROADMAP.md`'s "Live acceptance debt" list and the acceptance card,
`docs/acceptance/2026-10-05-spu8-intercom-sortie.md`. Two constants shipped as guesses pending
that flight: `ON_GROUND_AGL_THRESHOLD_M = 10.0`, `MISSION_START_ICS_DELAY_S = 5.0`.

**OPEN — unresolved contradiction, carried forward verbatim, not settled by this conversion
(`plans/obsidian-links-and-tags/plan.md`, "Decisions requiring user input" #1, AA-3):** this entry
asserts both *"FLOWN, TESTED AND ACCEPTED 2026-10-05"* above and *"Live acceptance is tracked as
debt, not waived"* immediately below. One of those two sentences has to go. If accepted, the debt
sentence should be deleted; if debt is real, this entry needs `#needs-flight` and the acceptance
claim needs qualifying. This is a correctness question about what was actually flown, not a
convention question, and it needs the user — not quietly resolved here.

**What it would do.** The intercom switch gates the crew channel in **both directions** — off
means he cannot hear you and you cannot hear him, which is what the real switch does — and the
SPU-8 volume knob sets how loud he is. One physical control turning Petrovich on and off, which
is the cockpit-adjustable volume the SRS route was wanted for, reached by reading the controls
instead of adding a dependency.

### The behaviour, in the user's own terms (2026-10-05)

**Gating — both switches, either one closes the channel.**

> *"When pilot intercom 1 switch is OFF **OR** co-pilot ICS switch is OFF -> no audio in either
> direction. If player keys the ICS PTT, no audio capture. If Petrovich speaks (audio stream from
> another layer), no playback, just silent ignore."*

Note the shape of the second half: a line that arrives with the intercom off is **dropped
silently, not queued**. It is not deferred speech waiting for the switch — the crew member simply
was not on the channel when it was said. Do not add a replay buffer.

This also resolves the operator-panel problem recorded below: the gate is the **conjunction** of
the pilot's own switch and the co-pilot's, so arg 664 (operator intercom power, unreachable to a
player flying as pilot) is read, not set by the player — and the automatic behaviour below is
what puts it in the right state.

**Volume — at playback, and nowhere else.**

> *"SPUU-8 intercom volume control sets Petrovich audio playback volume. This should be done at
> audio playback, no other layer needs to know volume setting. Either set playback volume, if
> supported, or modify the audio waveform for volume. Volume affecting the next playback is
> acceptable tradeoff, if volume for current playback is challenging."*

That last sentence is a real scope reduction worth taking: a knob turned mid-utterance may apply
from the next line rather than ramping the one in flight. It removes any need to stream or
re-chunk audio already handed to the sink.

**Automatic behaviour — two defaults, both about not having to fiddle with switches.**

> *"When mission starts, wait 5 s, then set co-pilot ICS switch ON. If on ground, default to
> 'silent mode'. (Contact reports not needed when not even airborne yet, let's just use the
> silent mode to suppress them for now.)"*

- **Setting the co-pilot ICS switch is a cockpit write, and the mechanism for that is already
  shipping — only the cross-seat case is open.** An earlier draft of this entry claimed the
  project had never written a clickable cockpit control; that was wrong, and is corrected here
  rather than quietly edited away. `aircraft-layer/dcs-export/Export.lua` has driven Petrovich's
  AI wheel with `GetDevice(30):performClickableAction(cmd, value)` since BL-6 (lines 519-530),
  and early Petrobrain moved the ASP-17 the same way. So the question is **not** whether a write
  is possible.

  **The cross-seat case is settled too — flown 2026-10-05, and it works.** SPU-8 is device 55;
  arg 664 is `CMD_SPU8_O_ICS` (cmd 3015) and carries `crew_member_access = {1}`, the operator's
  seat. From the **pilot** seat, `GetDevice(55):performClickableAction(3015, v)` moved 664 0→1
  and back 1→0, held both times, **and the user saw the switch physically move in the cockpit**.
  So that flag gates mouse clickspots, not dispatched commands — as the static recon inferred,
  now demonstrated. The "wait 5 s, set co-pilot ICS ON" step is buildable as specified and the
  hand-flip fallback is not needed.

  **Observed values, from the same probe — build against these, not against the declared
  ranges:**

  | Arg | Reads | Note |
  |---|---|---|
  | 377 | 0 / 1 | **animates through intermediate values (0.32, 0.64) for ~0.1 s.** A reader must threshold at 0.5, never test equality — this is the one that will silently misbehave if ignored |
  | 457 | continuous 0..1 | pilot SPU-8 volume, as declared |
  | 664 | starts 0 | co-pilot ICS, writable from the pilot seat per above |
  | 456 | 0.000 throughout | **not a finding** — the user confirms it was simply never clicked during the probe |

  **The gate is `377 AND 664`, not the `456 + 376/377` this entry's own table note below
  speculates.** The switch the spec calls "pilot intercom 1" is **arg 377** (NET-1 ON/OFF), user-
  confirmed by clicking it and watching 377 toggle 0→1→0. Treat the table note as superseded on
  that point.

  Recon, raw log and probe script: `aircraft-layer/research/2026-10-05-spu8-intercom-write-path-recon.md`,
  `docs/acceptance/2026-10-05-spu8-intercom-probe.md` and `aircraft-layer/dcs-export/Export.probe-spu8.lua`,
  on branch `investigate/spu8-intercom-write-path` (`40f0173`) — **not yet in this clone**, so
  every figure above is relayed from the Windows-box session rather than read here.
- **On-ground silent mode reuses the shipped `silence` command** (`crew_console.silenced`), not a
  new suppression path. It is absolute silence including urgent calls, per the same user
  direction that built it, and **any subsequent command ends it** — so a player who wants him
  talking on the ramp just says something. Worth confirming by ear that automatic entry does not
  make him feel broken at mission start.

**Still open in this slice, and needing the user rather than code:** whether leaving the ground
should automatically *end* silent mode, or whether the existing any-command-ends-it rule is
enough. The quoted direction says only how it starts.

**Two design notes worth keeping, so they are not re-derived:**
- **`winsound` has no volume control.** `PlaySound` cannot attenuate, so the knob cannot be
  applied at playback — it has to scale the PCM samples before the WAV is played. That decides
  where it lives: the **collector**, which already holds the live cockpit state. The adapter
  should not need to know about knobs.
- **Gating capture in the collector, not downstream.** With the intercom off, a push-to-talk press
  should not produce a clip at all, so neither the adapter nor the body layer has to reason about
  it.

~~**Blocked on nothing but a decision to resume** — it needs device argument numbers for the
switch and the knob, the same way push-to-talk needed arg 738, which is an investigator pass plus
a probe on the Windows box.~~ **The investigator pass is done (2026-09-20, read from
`clickabledata.lua` on the Windows box), and the slice is no longer deferred (2026-10-05).** What
remains before implementation is the live probe named at the end of this entry, plus the
can-we-write-a-cockpit-argument question above.

| Arg | Control | Seat |
|---|---|---|
| 456 | Radio/ICS switch | pilot |
| 457 | SPU-8 main volume knob (axis 0-1, step 0.05) | pilot |
| 453 | SPU-8 radio volume knob | pilot |
| 455 | Radio source selector, 6 pos at 1/5 | pilot |
| 452 / 454 | Network 1/2 switch, circular call button | pilot |
| 376 / 377 | SPU-8 NET-2 / NET-1 ON-OFF | pilot |
| 738 | stick trigger: **1.0 = RADIO (LMB), 0.5 = ICS (RMB)**, 0.0 released | pilot |
| 656-661 | operator mirror of 452-457 | operator |
| **664** | **SPU-8 intercom power ON/OFF** | operator |
| 856 | operator stick trigger, same 1.0/0.5 encoding | operator |

**One thing to know before designing "intercom off means he cannot hear you": 664 is the only
actual intercom *power* switch, and it is on the operator's panel** (`crew_member_access = 1`) —
the player flying as pilot cannot reach it. The pilot's equivalent gating is 456 (Radio/ICS
select) plus the 376/377 network switches, which is a different thing. Source and the full
extraction: `aircraft-layer/research/2026-09-20-dcs-install-detection-deep-read.md` finding 11.

Still genuinely needing a live probe: the *values* these args report in flight (the table gives
their declared ranges, not what `get_argument_value` returns mid-sortie).

The original SRS groundwork is preserved in `research/2026-09-17-tts-audio-transport-recon.md`
(read its two addenda, which correct the main body) — it established that stock SRS declares an
Intercom radio for the Mi-24P at 100.0 MHz modulation 2. That finding stands as a record; it is
simply no longer the route.
