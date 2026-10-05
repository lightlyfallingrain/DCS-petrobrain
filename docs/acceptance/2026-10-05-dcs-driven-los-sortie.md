# DCS-driven line of sight sortie

**Cockpit card (published):** https://claude.ai/artifact/2teqLyVQQEDQPxRF2JfpLp — the same content
below, laid out for reading in glances. This file stays the source of truth.

**Branch: `feature/dcs-driven-los`** (not merged as of this card — Reviewer, Security plan review,
Security deep analysis, Performance and DoD mechanical checks have all passed; this flight is the
only thing still outstanding):

```sh
git checkout feature/dcs-driven-los && git pull
```

If you are flying after it has merged, check out `main` instead — same setup and test items apply.

## This flight stands alone — do not combine it with the contact/terrain sortie

There is already a pending sortie on `main` for `fix/contact-report-flood` /
`fix/redundant-group-disclosure` / `feature/terrain-callout-stages-345` — all three change *what
Petrovich says* about a contact. This branch changes *what he can see* (a DCS-driven LOS verdict
replacing an SRTM approximation, plus building occlusion for the first time). Flying both changes
on one sortie would make a detection miss and a phrasing problem indistinguishable — if a contact
goes unreported, you wouldn't know whether LOS wrongly blocked it or speech wrongly suppressed it.
Fly this one on its own.

## Blocks before anything here works

**1 — Deploy the new Hook script. Nothing below works without this.**

```
copy aircraft-layer\dcs-export\petrobrain-line-of-sight-hook.lua "Saved Games\DCS\Scripts\Hooks\"
```

Needs the same `autoexec.cfg` opt-in the other `dostring_in` Hook scripts already use
(`net.allow_dostring_in = { "scripting" }` and `net.sanitizeModule('os')` left alone) — if you've
already flown the F10/velocity Hook scripts, this is already set. UNVERIFIED beyond that: whether
this specific new script loads cleanly is one of tonight's own questions, not something checkable
without DCS.

**2 — Redeploy `Export.lua`.** This branch doesn't bump the wire-format version, but the collector
process itself gained two new ports (line-of-sight receiver, look-direction sender) baked into
defaults, so a stale collector binary won't have them even if `Export.lua` is unchanged. Rebuild/
redeploy the collector the normal way (`WORKFLOW.md`).

**3 — Start the usual processes, Mac side:**

```sh
cd run-scripts
./run-audio-adapter.sh
./run-brain.sh --decider ollama
./run-crew-text.sh --detection-trace ~/dcs-detection-trace.jsonl
```

Windows side, collector:

```sh
cd run-scripts
./run-collector.sh
```

## Do / expect / record

**1 — `dcs.log` on mission start.**
- *Do:* tail `dcs.log` right after mission start.
- *Expect:* `PetrobrainLineOfSight` lines appearing on a poll cadence, each with
  `bridge_call_ms=...` and a result summary. Also `look direction set: hour=... fov_half_deg=...`
  lines, changing as Petrobrain's commanded gaze cycles through its scan.
- *Record:* did both line kinds appear? Did the look-direction line actually change value over the
  flight, or did it stick at one value the whole time?

**2 — Fly past a building with a known vehicle or AAA behind it.**
- *Do:* find a built-up area, position a target (or use a mission that already has one) so a
  building sits between you and it, close enough that terrain alone would read clear.
- *Expect:* the target reads occluded while the building blocks it, and clear once you have an
  unobstructed angle on it. This is the single new capability this feature claims — nothing in this
  project has ever occluded behind a building before.
- *Record:* did it actually occlude? If it didn't, was that because the building truly didn't block
  the geometry you flew, or because nothing changed at all?

**3 — Re-fly the missed-AAA geometry.**
- *Do:* fly the attack-pass geometry from `plans/missed-aaa-detection/debug.md` (the insurgent AAA
  position the 12 m terrain tolerance was built to fix) past the same position, boresight on it the
  way you did the day that defect was found.
- *Expect:* Petrovich calls it out, and `dcs-detection-trace.jsonl`'s entry for that object shows
  `live_los_clear=true` — meaning the live path resolved it directly, not via the 12 m tolerance
  (check `building_clear`/`terrain_clear` are both present and `true` on the same row).
- *Record:* did it call out? Does the trace actually show `live_los_clear` populated for that
  object, or did it fall back to the offline primitive (see item 6 below)?

**4 — This flight's prize measurement: the read-back numbers.**
- *Do:* after landing, grep `dcs.log` for the `PetrobrainLineOfSight` lines and pull
  `units_in_bubble`, `units_in_wedge`, `sightlines_computed`, `bridge_call_ms`.
- *Expect:* nothing specific — this is the one thing nobody can predict from the plan's own
  arithmetic, because every wedge-population figure in the plan beyond ~10/poll (Stage 0's own
  measured figure) is a uniform-azimuth extrapolation the plan itself says not to trust.
- *Record:* the actual numbers, across a few different moments in the flight (over open terrain,
  over a town, near a cluster of units). This replaces estimate with measurement for whatever comes
  next in this line of work.

**5 — Any felt stutter, independent of the 1 Hz LOS poll.**
- *Do:* fly normally, paying attention to frame smoothness, separately from the LOS feature itself
  — Performance's own review could not measure this (no DCS-side Lua profiler available) and asked
  specifically for a flown answer.
- *Expect:* nothing — this is the open question.
- *Record:* any stutter, when, and whether it correlates with anything you can tell (busy area,
  mission start, a specific moment).

**6 — Watch for silent fallback — nothing currently alerts on this.**
- *Do:* during the flight, watch `dcs-detection-trace.jsonl` (or ask for `--detection-trace`'s
  summary afterward) for `hour_used`/`fov_half_deg_used` — confirm they're populated, not null, for
  entries during normal flight.
- *Expect:* populated values whenever the Hook script and look-direction channel are both working.
  If the Hook script fails to load, or the `autoexec.cfg` opt-in is missing, every unit silently
  falls back to the old SRTM-tolerance primitive with no alert anywhere except a human reading
  `dcs.log` — a whole sortie could run on the fallback unnoticed.
- *Record:* were `hour_used`/`fov_half_deg_used` populated throughout, or did you see gaps?

**7 — Pause-state check.** This Hook-script family has a history of export-rate bugs invisible to
in-flight-only testing (`aircraft-layer/CLAUDE.md`'s own testing note).
- *Do:* pause the mission mid-flight, wait a few seconds, unpause.
- *Expect:* `PetrobrainLineOfSight` lines keep appearing (or cleanly stop and resume) rather than
  silently going stale while the rest of the sim clock stops.
- *Record:* what you saw in `dcs.log` across the pause.

**8 — Engagement danger/safe calls track the live verdict.**
- *Do:* watch a contact engage and disengage from behind cover.
- *Expect:* the danger/safe calls track the live building/terrain verdicts now feeding the
  engagement term (the "safe from" utterance itself stays deferred — unrelated to this plan,
  already shipped that way).
- *Record:* anything that felt wrong-timed or wrong-direction.

## What this flight is not testing

- The `atan2` heading/bearing convention inside the Hook script's `LOS_CODE` string against DCS's
  own Mission Scripting Engine convention — if it's wrong, the symptom is a wedge that silently
  doesn't track where you're actually looking (a coverage *loss*, not a wrong detection). Items 1-3
  above are the indirect test of this; there's no direct instrument for it.
- `tonumber("nan")`/`tonumber("inf")` behaviour on DCS's bundled Lua/CRT — the clamp is written to
  be correct either way, but nothing here exercises it directly; a crash or a stuck value in the
  look-direction line (item 1) would be the visible symptom if this were wrong.
- World-model's offline LOS primitive and the 12 m tolerance it still carries for its narrower,
  fallback-only role — that's `WM-B8`/fixture work, not a live-flight question.

## Bring back

- Did a building actually occlude something it shouldn't have, or fail to occlude something it
  should have?
- Did the missed-AAA geometry resolve, and via the live path or a fallback?
- The `units_in_bubble`/`units_in_wedge`/`sightlines_computed`/`bridge_call_ms` numbers, at a few
  different moments.
- Any stutter, and when.
- Anything that surprised you — that's worth more than anything on this list.
