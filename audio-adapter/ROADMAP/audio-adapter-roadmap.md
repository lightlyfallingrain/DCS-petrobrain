# Audio Adapter — Roadmap

The process that turns Petrovich's text into sound the player actually hears. Everything audio
lives here: TTS synthesis, delivery to a playback target, and (next) injection into DCS-SRS's
intercom. Body-layer and the brain deal in text only and never see audio bytes — the split
`docs/concept/division-or-responsibility.md` settled and `plans/tts-voice-output/plan.md`
Decision 1 confirmed.

**Renamed from `srs-adapter` on 2026-09-20** — DCS-SRS was dropped as a planned dependency for
outbound audio (Slice 1 already ships over `winsound` via the aircraft-layer collector, never a
DCS-SRS call), so the subproject name now matches what it actually does. See `CLAUDE.md`'s own
note for the full rationale; AA-4 (Slice 3, inbound speech) is unaffected — that is
still the plan for the real DCS-SRS product.

Why a separate subproject rather than part of aircraft-layer or body-layer: aircraft-layer's
contract is DCS I/O and body-layer's is belief state; neither should grow a TTS dependency. The
seam is HTTP end to end (body-layer → audio-adapter → aircraft-layer), so no new in-process
cross-subproject import exists — the body-layer↔world-model one remains the sole sanctioned
exception (root `CLAUDE.md`).

This subproject is BL-10's non-body half. See `body-layer/ROADMAP.md`'s BL-10 entry for the
body-side view and the slice numbering both files share.

This is the pointer's index — see `docs/DOC_CONVENTIONS.md` for the directory layout, ID scheme
and link form it follows. The index carries links and titles only; status lives on each entry.

## Status

- [[AA-1]] — Slice 1 — outbound TTS
  - [[AA-1.1]] — Stage 1 — synthesis + local playback
  - [[AA-1.2]] — Stage 2 — aircraft-layer playback channel
  - [[AA-1.3]] — Stage 3 — `--target aircraft-layer`
  - [[AA-1.4]] — Stage 4 — body-layer wiring
  - [[AA-1.5]] — Stage 5 — live Windows verification
  - [[AA-1.6]] — Stage 6 — live sortie acceptance
- [[AA-2]] — Hardening: per-source `--poll-hz` default + `Content-Length` guard
- [[AA-3]] — Slice 2 — cockpit state drives the audio (SPU-8 intercom) — carries an unresolved
  acceptance-vs-debt contradiction, see the entry itself
- [[AA-4]] — Slice 3 — inbound speech (STT + PTT)
  - [[AA-4.1]] — Stage 1 — the recognition bench
  - [[AA-4.2]] — Stage 2 — the matcher and the command path
  - [[AA-4.3]] — Stage 3 — recognition as a service, body-layer's inbound wiring
  - [[AA-4.4]] — Stage 4 — capture
  - [[AA-4.5]] — Stage 5 — real PTT through DCS
  - [[AA-4.6]] — The ~0.14 s device-open gap
  - [[AA-4.7]] — Press-to-readback latency
  - [[AA-4.8]] — Stage 6 — live sortie acceptance
- [[AA-5]] — `silence` command phrase wiring

## Live acceptance debt

A few entries above carry a verified behaviour with no in-cockpit observable or dedicated sortie
yet (`#needs-flight`): [[AA-2]] (poll-rate halving), [[AA-5]] (silence command phrase wiring, via
the body-layer dispatcher). `grep -rl '#needs-flight' audio-adapter/ROADMAP/` finds this
subproject's own set mechanically rather than by a hand-kept list; the repo-wide form, which is the
one to use when asking what a sortie could clear, is in `docs/TAGS.md` — see
`plans/obsidian-links-and-tags/plan.md`, "Trustworthy grep negatives over tags".

[[AA-3]] is a related but different case — not debt, but an unresolved *contradiction* about
whether debt exists at all for that entry. See the entry.

## Backlog

Items here are `AA-B<n>`. A new one takes the next unused number; numbers are never reused or
renumbered, done items included (root `CLAUDE.md`, "Backlog Management").

- [[AA-B1]] — Voice character — accent and prosody
- [[AA-B2]] — Process supervision
- [[AA-B3]] — `POST /audio/play` has no request-size cap

## Keeping this current

Same discipline as the sibling subprojects: this index is the source of truth for this
subproject's milestone status, and a merge is not finished until it reflects what merged (see
`.claude/skills/merge/SKILL.md` and the root `ROADMAP.md`). Status lives on each entry file, not
here — update the entry, not this list, when a milestone's state changes; this file only needs a
new row when an entry is added or removed.
