# BL-B42 — The LOS sightline cap binds over a dense city

- [ ] **BL-B42 — Over a dense city the LOS sightline cap binds. The population is now identified,
  and it is all worth seeing.** #status/open Found during the user's 2026-10-08 test flight of `fix/los-hook-statics`
  (`docs/acceptance/2026-10-08-los-statics-sortie-feedback.md` item 2), on first flight of the
  [[BL-11]] Stage 4 statics enumeration.

  Measured over Damascus: `objects_in_bubble=~200+`, `objects_in_wedge=~200+`, `cap_hit=1` against
  the 128-candidate cap — nearest-first sort, so the dropped candidates are the farthest, the right
  failure direction but a real truncation. The user's reading, **not yet measured**: *"those are
  buildings, I believe. We don't really need buildings in objects that we track, especially we
  don't need to LOS them."*

  **RESOLVED 2026-10-08, and the answer removes the filtering premise.** The user supplied the
  Damascus scan line and the mission itself (`win-mac-sync/from-windows/MI24-outpost-M03.miz`):

  ```
  objects_in_bubble=238 statics_in_bubble=182 objects_in_wedge=152 statics_in_wedge=113
  candidates=152 sightlines_computed=128 max_sightlines=128 cap_hit=1
  LOS cap bit: sightlines_computed=128 of objects_in_wedge=152 (dropped=24 farthest candidates)
  ```

  The mission's 388 statics, counted from its own `mission` Lua by category:

  | count | type |
  |---|---|
  | 120 | Soldier M4 GRG (infantry) |
  | 65 | tanks — 31 T-55, 19 T-72B, 15 T-72B3 |
  | 70 | APCs — 25 Tigr_233036, 23 BTR-80, 22 BMP-2 |
  | 8 | ZSU-23-4 Shilka |
  | 60 | parked aircraft — MiG-21Bis, SA342L, Mi-24P, MiG-29A |
  | 21 | `big_smoke` |
  | ~12 | carrier deck crew, misc |

  **Zero buildings.** `coalition.getStaticObjects` behaved exactly as documented — DCS scenery
  buildings are terrain objects with no coalition and never appeared. The user's in-flight reading
  (*"those are buildings, I believe"*) was mistaken, and filtering on it would have blinded
  Petrovich to 120 infantry, 65 tanks, 70 APCs and 8 Shilkas — the contacts the copilot exists to
  call. This is the second time this session the statics-are-decorative assumption was overturned by
  looking at the actual inventory; the first was the 2026-10-05 reversal in
  `docs/acceptance/2026-10-05-sortie-feedback.md`.

  `big_smoke` was proposed as the one droppable class (21 slots, against 24 dropped at the cap — it
  would have recovered almost exactly the deficit). **The user rejected that too, and the reason is
  domain knowledge worth recording:**

  > *"Big smoke can actually be usefull. In same way as signal smoke and signal flares, they work as
  > landmarks for referencing."*

  So smoke is a *referenceable feature* — something Petrovich can see and name to locate a contact —
  not scenery. It stays.

  **Net: nothing in this population should be filtered.** The item is therefore not "which objects
  to exclude" but **"the 128 cap is too small for a dense city"**. Still open: whether the cap rises,
  whether the budget becomes time-based rather than count-based, and whether the nearest-first sort
  plus a cap is already an acceptable answer given the dropped 24 were the farthest. The per-poll
  cost does **not** currently argue for urgency — see the cost note below.

  **Measured cost, and it decides the shape of the fix.** `bridge_call_ms` is ~2 ms over semi-open
  terrain, ~5 ms over Damascus, and **27 ms at the measured maximum** (confirmed: `sort -n | tail -3`
  gives `26.00 26.00 27.00`). An earlier reading of `max 2026` as a 2-second stall was the log line's
  **year** — `2026-10-08` leads every line. Nothing stalls.

  That maximum is the useful number. 27 ms across 128 sightlines is **~0.21 ms per sightline** (two
  engine calls each: `world.searchObjects`/`SEGMENT` plus `land.isVisible`). At 60 fps a frame is
  16.7 ms, so:

  | sightlines | est. cost | frames |
  |---|---|---|
  | 128 (today's cap) | 27 ms | ~1.6 |
  | 152 (this sortie's full wedge) | ~32 ms | ~1.9 |
  | 256 | ~54 ms | ~3.2 |

  **So the cap must not simply rise** — it is already above a one-frame budget, and covering the full
  city wedge in one poll would make the poll itself the hitch that this sortie proved it currently is
  not.

  **Proposed shape instead: amortise, don't enlarge.** Hold a per-poll budget near one frame, keep the
  nearest candidates checked every poll, and carry a **rotating offset** through the far tail so it is
  covered over successive polls rather than discarded. Far contacts gain eventual coverage at flat
  per-poll cost — strictly better than both today's truncation and a larger cap. At 1 Hz the whole
  152-candidate wedge would be covered within ~2 polls. Not yet designed or decided; this is the
  direction the cost data points at, and it needs `/explore` before an Architect pass.

  **The 5 s stutter is RESOLVED 2026-10-08: a probe Hook left deployed.** The user found it:

  > *"I think the 5s interval micro stutter may have been caused by
  > petrobrain-unit-id-join-probe-hook.lua that I had forgotten to remove. Now that I removed it, no
  > stutter."*

  Removing it ended the stutter. Worth recording honestly: that probe polls at **1 Hz**
  (`POLL_INTERVAL_S = 1.0`), not 5 s, so the felt period did not match its interval — but it does far
  more work per poll than the LOS Hook (a full unit enumeration plus `getObjectID` per unit), which
  fits a heavier, less regular hitch. The empirical result is the evidence; the period was an
  estimate.

  **The process gap is the finding, not the probe.** A probe Hook stays in
  `Saved Games/DCS/Scripts/Hooks/` until someone remembers to delete it, and while it is there it
  taxes every sortie and contaminates exactly the performance measurements a sortie is flown to take.
  Three hypotheses were tested against the real cause sitting in the Hooks directory the whole time.
  Filed as **`AC-B5`**.

  The refuted-hypothesis record below is kept, because the reasoning still holds for the LOS Hook
  itself and the measurements are the ones that cleared it.

  **What was ruled out, and why it stayed ruled out.** The user reported *"a small stutter every
  5 s"*. A full gap scan of the scan-line cadence over the whole sortie finds exactly
  **two** gaps — 7.62 s at `16:04:24.954` and 2.65 s at `16:26:56.273` — against an otherwise
  metronomic 1.004 s. Two isolated events 22 minutes apart are not a 5 s period.

  Three hypotheses tested and refuted:

  | hypothesis | refuted by |
  |---|---|
  | `Export.lua` reconnect (`RECONNECT_INTERVAL_S = 5.0`, blocking 200 ms connect) | `grep "connect failed"` empty — collector connected throughout |
  | LOS poll cost | `bridge_call_ms` max 27 ms; nothing above 100 ms all sortie |
  | LOS poll cadence | only two gaps in the sortie, neither periodic |

  Nothing in the *shipped* set injects a 5 s period (LOS Hook 1 Hz, F10 Hook 1 Hz, `Export.lua` 5 Hz)
  and nothing in it is slow — all three conclusions stand. The gap the reasoning had was that the
  deployed set was assumed to be the shipped set, and a leftover probe Hook was in it. **The lesson is
  to enumerate what is actually in the Hooks directory before reasoning about what runs on the DCS
  thread**, rather than reasoning from the repository.

  The two cadence gaps remain unattributed and are not worth chasing: two events 22 minutes apart,
  with the periodic symptom now explained.

  **Explicitly not a blocker on [[BL-11]] Stage 4's statics fix** — the fix under that stage is the
  enumeration itself, and this is a consequence to design for separately. Per root `CLAUDE.md`'s
  "flight feedback is captured, then explored, then planned," this goes to `/explore` with the user
  before any Architect or Implementer pass.
