# Aircraft Layer — Roadmap

Live, LAN-reachable DCS I/O pipeline: `Export.lua` → Windows collector → LAN API, plus one narrow
write-back channel (`POST /text/push`) for in-cockpit text display. See `CLAUDE.md` for stack/API
details and `WORKFLOW.md` for the cross-machine deploy/run workflow. Full design/stage history:
`plans/aircraft-layer/plan.md`, `plans/aircraft-layer/implementation.md`.

## Status

- [x] **Core telemetry pipeline — done, merged 2026-09-07** (`feature/aircraft-layer-telemetry`).
  `Export.lua` → collector → `/telemetry/latest`. Live-tested against cockpit instruments
  (bank/IAS/heading/alt all match). 5 Hz export-rate bug found and fixed. `altitude_radar_m` stays
  null (deprioritized — `altitude_agl_m` is equivalent). `/telemetry/since` dropped as unneeded
  scope — no delta/ring-buffer endpoint exists; a consumer needs a concrete gap-free-history need
  before that's reconsidered.
- [x] **`/world_objects/latest`** — `LoGetWorldObjects`'s raw, unfiltered ground truth, feeding
  body-layer's `HybridPerceptionSource`/`NakedEyePerceptionSource` association. Each object carries
  `is_ownship` (PB-2 Stage -1, 2026-09-09), replacing an earlier 50 m proximity heuristic that had
  a false-negative window during troop insertion/close formation.
- [x] **`/petrovich_indication/latest`** — `list_indication(HELPERAI_DEVICE_ID)`'s parsed
  classification text, the scope channel's detection-existence gate.
- [x] **Text-overlay write channel — done, merged as part of BL-2.5, 2026-09-09.**
  `POST /text/push` → collector → loopback UDP → a DCS Hook-state overlay
  (`Saved Games/DCS/Scripts/Hooks/`), modeled on SRS's overlay pattern. First write path in an
  otherwise read-only layer; reframed `CLAUDE.md` from "read-only" to "read-mostly with narrow
  write channels." See `body-layer/ROADMAP.md` BL-2.5 for the body-layer side.
- [x] **F10 command inbound channel — done, merged 2026-09-13 (`eacc45c`).** First Hook→collector
  direction: `petrobrain-f10-commands-hook.lua` registers F10 menu items through
  `net.dostring_in("scripting", ...)` and forwards selections over loopback UDP 7794 to
  `F10CommandReceiver` (three allowed tokens only), served once via `GET /f10_commands/poll`.
  Needs `autoexec.cfg` `net.allow_dostring_in = { "scripting" }`. Wall-clock provenance only.
  See `body-layer/ROADMAP.md` "F10 radio-menu command input" and `plans/f10-crew-commands/`.

- [x] **Unit-velocity channel — implemented 2026-09-22, ACCEPTED live 2026-09-23** on the five-fix sortie (`docs/acceptance/2026-09-22-five-fixes-sortie.md`): movement callouts were produced in flight, which exercises the whole transport end to end. Originally:
  (`plans/movement-detection/plan.md` Stage 1). Second Hook→collector direction, alongside the F10
  channel above: `petrobrain-mission-telemetry-hook.lua` polls `Object.getVelocity()` for every unit
  and static object at 1 Hz via `net.dostring_in("scripting", ...)` (the same bridge the F10 hook
  already proved live), stamping sim time **inside the scripting state** via `timer.getTime()`
  (never `DCS.getRealTime()` — the replay-determinism risk the plan flags as sharpest), and forwards
  one JSON datagram per poll over loopback UDP 7795 to `UnitVelocityReceiver`, served via
  `GET /unit_velocity/latest`. `Export.lua` gains `unit_name` (`LoGetWorldObjects`'s `UnitName`) on
  every world-object entry — the join key body-layer's `perception.motion` uses to pair a candidate
  with its velocity sample; wire-format version bumped (`EXPORT_SCRIPT_VERSION`/
  `EXPECTED_EXPORT_VERSION` → `2026-09-22b`) accordingly. Needs the same `autoexec.cfg`
  `net.allow_dostring_in = { "scripting" }` opt-in as the F10 channel. Self-measures its own cost
  (`unit_count`/`bridge_call_ms`, logged to `dcs.log` every poll) since the in-state `O(N)`
  `getVelocity()` loop's per-call cost cannot be measured off a live DCS session.
- [x] **Hardening: bounded audio queue + guarded collector `accept()` -- done 2026-09-26**
  (`feature/aircraft-layer-hardening`, no plan.md -- scoped directly from the two 2026-09-26
  whole-subproject reviews, `aircraft-layer/research/2026-09-26-security-review.md` and
  `-performance-review.md`). `AudioPlaybackSender`'s queue is now bounded at 64 (mirroring
  `F10CommandQueue`), dropping the oldest queued `.wav` on overflow rather than blocking the HTTP
  thread. `CollectorServer.serve_forever`'s `accept()` is guarded so a dead ingestion thread stops
  being invisible, logging loudly and retrying after a backoff instead of dying silently.
  Went through two rounds: the first `accept()` guard classified shutdown by re-reading
  `self._socket`, which raced `close()`'s own two-statement teardown and produced a false
  "unexpected failure" ERROR on 161/~230 real shutdowns -- the reviewer measured this, not just
  read it. Fixed with an explicit `self._shutting_down` flag set before the socket is actually
  closed, so the flag-write happens-before the racy syscall. Both fixes are latent hardening with
  no observed live trigger; no acceptance card, per DoD judgment (neither changes anything
  perceivable in the cockpit). **Does not change what's next** -- these were pre-existing
  RECOMMENDED findings, not new information; the export-throttle split and the
  `LoGetWorldObjects` FPS measurement below remain correctly deferred pending an actual
  measurement, which this work did not take.

## Backlog

- [x] **Push-to-talk channel — implemented and ACCEPTED live 2026-09-23** (the voice sortie: the trigger works, and a radio call stays out of it).
  (`feature/inbound-speech-stage4`, `plans/inbound-speech/plan.md` Stage 5). `Export.lua` publishes
  the pilot stick trigger (arg 738) as its own line kind; `PttSample`/`PttCache`/`GET /ptt/state`
  carry it to the capture process. Wire version bumped to `2026-09-23a`.

  **Edge-driven at frame rate, not on the 5 Hz telemetry line.** A press behind that throttle could
  lose up to 200 ms off the front of an utterance, and the front is where the verb is. Sending only
  on change keeps a real trigger to two lines per press.

  **This layer decides nothing.** It reports the raw value; the predicates (`intercom`, `radio`)
  are conveniences on the sample, and the debounce that makes them usable lives in the consumer —
  because a full press *transits* the intercom stop for 19-32 ms, and a threshold that has to be
  tuned should not require copying a file into Saved Games to change.

- [ ] **Regenerate `research/mi24p-command-surface.md` with a parser that handles raw table
  literals.** Found 2026-09-20 on the Windows box: the dump enumerates the
  `default_2_position_tumb(…)`-style helper forms only, so **13 of `clickabledata.lua`'s 749
  elements are missing** — and the missing set is biased, because a control needs the raw form
  precisely when it has more than one action. Both push-to-talk triggers (args 738 and 856), both
  collectives, the ASP-17V sight reflector handle and the PKI control are all absent. This is what
  made arg 738 look untraceable in `2026-09-19-ptt-gate-feasibility.md` when it was sitting in the
  source file all along. The 13 are now listed by hand in a warning box at the top of that
  reference, which stops the gap misleading a reader but does not survive the next DCS update —
  the generator is the real fix. Full detail:
  `research/2026-09-20-dcs-install-detection-deep-read.md` finding 11.

- [ ] **Split the export throttle** so `LoGetWorldObjects`/HelperAI can poll slower than self-data.
  `Export.lua`'s `EXPORT_INTERVAL_S = 0.2` (5 Hz) is one shared throttle gating all three feeds
  together. Ground units don't need 5 Hz; self-data (and any future threat-reaction signal) may
  want to stay fast. Fix: two independent interval constants. Not urgent — no measured FPS cost yet
  to react to (see next item). BL-2's contact-decay timescales (30s/120s) are ~2 orders of
  magnitude slower than either 5 Hz or a candidate 2 Hz, so this is a pure export-cost/latency
  tradeoff, not a belief-quality one. Raised 2026-09-09.
- [ ] **Measure `LoGetWorldObjects` FPS cost live** before tuning its poll rate. No confirmed,
  quantified per-call cost exists at realistic unit counts (~50–200) — only qualitative
  forum/Tacview-wiki folklore. Fly with world-objects export on/off at 5/2/1 Hz and diff
  FPS/frame-time. Also worth checking whether "being fired at" is even served by this poll rate at
  all (nothing currently reads it for threat/launch detection) — the urgent-callout-latency case
  may want its own dedicated signal later (e.g. RWR export) instead. Raised 2026-09-09, kept
  separate from the throttle-split item above since this is measurement that should land first.
