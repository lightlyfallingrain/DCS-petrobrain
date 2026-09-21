# Petrobrain — Roadmap

## Goal

Make DCS World Mi-24P/Petrovich operations feel like a real crew, not disconnected game systems.
Petrovich must never be omniscient — his knowledge is bounded by what he could actually perceive.
Guiding principle: **code owns truth, models own interpretation and language.** Full rationale:
`docs/concept/PETROBRAIN_SYSTEM.md`.

## Architecture

Three layers, each a separate subproject with an explicit interface:

1. **World Model** (`world-model/`) — persistent geographic knowledge of a DCS theatre (roads,
   settlements, terrain, elevation), built offline from DCS-derived data + external DEM/OSM
   augmentation. DCS geometry is always authoritative.
2. **Mission Interpreter** (`mission-interpreter/`) — understands one specific mission (`.miz` +
   briefing + world model + player intent), offline/pre-mission. MI-0–MI-6 done, the last planned
   stage; no BL-7 consumer wired up yet.
3. **Body Layer / Petrobrain Runtime** (`body-layer/`, fed by `aircraft-layer/`) — low-latency
   runtime crew cognition: perception, episodic/working memory, attention, dialogue. Memory is
   explicit application state, never LLM chat history.

Plus one supporting sibling, added 2026-09-17: **Audio Adapter** (`audio-adapter/`) — everything
audio. Text-to-speech, delivery to a playback target, and (next) injection into DCS-SRS's
intercom. It exists so neither the body layer nor the aircraft layer grows a TTS dependency:
body and brain deal in text only and never see audio bytes. Renamed from `srs-adapter` on
2026-09-20 once DCS-SRS was dropped as a planned dependency — see `audio-adapter/CLAUDE.md`'s
"Renamed from srs-adapter" note.

Per-layer design docs (status: draft/provisional): `docs/concept/WORLD_MODEL_BUILDER.md`,
`docs/concept/MISSION_INTERPRETER.md`, `docs/concept/PETROBRAIN_RUNTIME.md`.

## Status by subproject

| Subproject | Status | Roadmap |
|---|---|---|
| World Model | **M0–M10 done, all query surfaces (settlement boundaries, road junctions, landcover/coastline, LOS) serving Mission Interpreter via HTTP.** A full `syria-full` rebuild on 2026-09-15/16 completed end to end (~60 min), validating both M10's junctions-streaming-fix (Stage 5 finished, no OOM) and the OSM ingest optimization + landcover split merged 2026-09-16 — OSM now contributes landcover, coastline, water and named places, never roads (DCS `.routes` stays authoritative). Remaining from that run: full-theatre OSM parse time/peak RSS and `describe_position` p99 at scale are still unmeasured (the build hit a warm cache and skipped the parse), and Stage 5 has pathological single-chunk stalls — both backlog, neither a correctness gate. Multi-theatre support (Afghanistan/Caucasus/Kola) is backlog, needed soonish — architecture already generalizes (per-theatre registries), Kola has a real elevation-source gap (SRTM has no coverage above 60°N). | [`world-model/ROADMAP.md`](world-model/ROADMAP.md) |
| Aircraft Layer | **Core done, merged 2026-09-07.** DCS I/O pipeline (telemetry, world objects, Petrovich indication text, text-overlay write channel, F10 radio-menu command input merged 2026-09-13) live and stable. A few small tuning items open. | [`aircraft-layer/ROADMAP.md`](aircraft-layer/ROADMAP.md) |
| Body Layer | **BL-7 done; the group contact model's first five stages merged 2026-09-18 — a contact is now a belief about the occupants of one *resolution cluster*, not one object, and whether two units are one contact or two is an angular question measured at ownship in 3D.** This closed a live defect (twelve real units collapsing into roughly five contacts that never separated) and, in the process, replaced the resolution model twice: a world-space ellipse turned out to be an approximation of the angular reality, and stating it directly *deleted* 144 net lines of `src/`. Two findings paid for that rework — the optic multiplier cancels out of the separability test, and the acuity floor is provably non-binding for anything the channel detected, which removed a planned calibration sortie's main purpose. Behaviour now: twelve units across the line of sight at 9 km resolve individually; the same twelve *along* it are one contact reporting a singular count (correct — he sees one dot); the same layout 800 m higher reports several, because climbing widens the depression-angle spread. Altitude-sensitive counting falls out of geometry with no tuned parameter. Still open and deliberately unresolved: whether composition (Stage 5) is worth building now that the angular model resolves the case that motivated the group model at all. Vision range calibration merged 2026-09-17 — detection ranges are now measured rather than guessed.** `perception/visibility.py`'s recognition-tier constants were recalibrated against a nine-range in-game screenshot ladder (503 m to 8.89 km, four optics per range, F10 ruler ground truth): for a 7 m vehicle, class 3500 -> 2000 m, type 1400 -> 1000 m, presence 6511 -> 9333 m, cap 5000 -> 10000 m. The old values were wrong in both directions at once — over-claiming classification while gating out vehicles plainly visible at 8.89 km. The finding that made it cheap: read as apparent angular size, the unaided and binocular columns land on the same tier thresholds within 2%, so the tiers belong to the eye and the optic only multiplies the angle — three constants, no per-optic model, and the 9K113 columns banked as founding evidence for the deferred detection-cones milestone. One open defect came with it, since diagnosed and reframed: distant clusters were collapsing into too few contacts, not because of `object_id` continuity as first assumed, but because the naked-eye presence tier is class-blind by construction, leaving the spatial gate to decide alone. Fixed narrowly; the real answer is the group contact model (`plans/group-contact-model/plan.md`). F10 crew command vocabulary merged 2026-09-16 (`1a9189c`). BL-0 through BL-7 complete: contact memory, classification, world enrichment, attention/events, the deterministic tool API (frozen since BL-6, 15 tools), text-mode crew interaction, Petrovich command/verification (`scan_area`/`get_task_status`/`cancel_task`, BL-6), and mission-phase tracking/relevance (BL-7, monotonic waypoint sequencing via Mission Interpreter MI-6 output, phase-proximity tie-break within attention tiers). Live-DCS acceptance of BL-6's search effector deferred to user; BL-7's live acceptance (real MI-6 end-to-end) also deferred. F10 radio-menu command input merged 2026-09-13 (mechanism live-accepted; command refinement deferred until the full pipeline works). BL-8 (memory layer interfaces) deliberately last, gated on BL-2..BL-7 real-flight experience. The F10 command vocabulary (2026-09-16) widened the radio menu from three tokens — two of them hollow — to fifteen that produce real belief state, specifically to make that flight informative; its own live acceptance, and the accumulated debt from BL-4/BL-6/BL-7, all clear on the same sortie. Richer command forms are BL-10/audio-adapter's, not F10's (user direction 2026-09-16), which widens BL-10's scope beyond swapping BL-5a's typed stand-ins for a real adapter. | [`body-layer/ROADMAP.md`](body-layer/ROADMAP.md) |
| Audio Adapter | **New subproject, first slice done 2026-09-17: Petrovich is audible.** Outbound TTS works end to end — text in over `POST /speak`, synthesized on the Mac (`say` behind a swappable `TTSEngine` protocol), then either played locally via `afplay` (`--target local`, needs neither Windows nor DCS — the dev path for auditioning voices and wording) or POSTed as WAV to the aircraft-layer collector's new `POST /audio/play` and played there by `winsound` (FIFO queue for routine lines; urgent lines clear the queue and interrupt playback). Body-layer's whole share was one optional field on `CrewConsole`, which is the milestone's own stated test of whether BL-5a drew its interface in the right place — it did. **Unverified pending the user's hardware:** Windows playback and the urgent-interrupt mechanism (no DCS needed), then latency and voice acceptability on a real sortie. **Next:** SRS ICS injection — confirmed reachable (`--modulations INTERCOM --unitId`, and stock SRS does declare an Intercom radio for the Mi-24P), and ICS is the *only* acceptable target since the player must stay on the mission frequency and the SPU-8 selects one source at a time. | [`audio-adapter/ROADMAP.md`](audio-adapter/ROADMAP.md) |
| Mission Interpreter | **MI-0–MI-6 done — the last planned Mission Interpreter stage.** MI-0, MI-1, MI-1.5, MI-2, MI-3, MI-4 (capable-model synthesis with `qwen3:14b`, merged 2026-09-12), MI-5 (player questions, text console MVP, merged 2026-09-12), and MI-6 (runtime compilation into the compact `RuntimeMissionUnderstanding`, 2026-09-12) complete. Consumed by body-layer's BL-7 (mission phase and relevance, merged 2026-09-13). | [`mission-interpreter/ROADMAP.md`](mission-interpreter/ROADMAP.md) |

## Visual status

A rendered view of everything below — subsystem status, the milestone dependency graph, open work,
and what is currently blocked on hardware — lives at `docs/status/`, published as a private
artifact. It is **derived**, never authoritative: if it disagrees with a roadmap file, the page is
the thing that is wrong. See `docs/status/README.md` for how and when to regenerate it.

## Keeping this current

Each subproject's `ROADMAP.md` is the source of truth for that subproject's milestone status —
this file only tracks the cross-subproject picture. `todo/todo.md` no longer duplicates milestone
narrative; it holds only items that don't yet belong to one subproject's roadmap (cross-cutting
backlog, session-scoped notes) and User priority tasks.

The `/merge` skill (`.claude/skills/merge/SKILL.md`) and the DoD agent (`.claude/agents/dod.md`) both
require the relevant `ROADMAP.md` (and, for a cross-subproject change, this file) to be updated
*in the same push* as any merge — a roadmap update is part of finishing a merge, not a follow-up
task. If a roadmap file and `todo/todo.md`/another roadmap ever disagree, treat that as a bug in
the update discipline, not as ambiguity to guess through — fix the stale one immediately.
