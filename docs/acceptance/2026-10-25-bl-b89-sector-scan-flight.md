# BL-B89 acceptance — 9K113 scan + point procedure (Stage 1 + BL-B98 fix + Stage 2)

Source of truth for the published card (the artifact at the link below is republished from this
file — do not fly from a copy, fly from whatever the card links back to here).

**Card:** https://claude.ai/artifact/M9jAnsomghXnV1bSyds9Mj

**Branch:** `main`, after the merge of `feature/9k113-scan-procedure` (merge commit named in
`plans/9k113-scan-procedure/dod-check.md`'s whole-feature pass) — `git checkout main && git pull`
in your own repo root, not a worktree. DoD has passed for the whole feature (Stage 1, the `BL-B98`
fix, and Stage 2) and the user authorised merging on DoD pass without waiting for this flight
(2026-10-25: *"When ready DoD BL-B89 as a whole and merge"*) — this flight is the one thing that
has not run yet, and it runs on `main`, not on the now-deleted feature branch.

**Player in the PILOT seat.** Petrovich operates the opposite seat (CPG) for this feature — you
are watching *his* sight scan, not flying it from the CPG seat yourself.

**Air start, straight and level** — the 9K113 is a warm unit by the time you take the controls
(`project_probes_flown_air_start`); no cold power-up sequence needed for these checks, but the
power-up ("Observ on" after MISSILE POWER / CPLR DISTR / Sight Power / ЩО PWR) still gates the
sight, same as every other 9K113 sortie.

## What this tests

**Stage 1** of BL-B89: the sight's idle search cycles three legs (`wide_near` 1.5-4 km,
`wide_far` 4-8 km, `narrow_far_sweep` 8-13.6 km) over the sectors you described — `ahead`
alternating two 40°-wide windows, `left`/`right` spanning the whole left/right half of the
sight's own ±60° regard, a commanded o'clock hour its own 30° wedge — and closes every lap with a
mandatory naked-eye pause, not just the pre-existing time-based one. Also folded in: the `BL-B98`
fix for the sight's resume position after a glance-away or OBSERV off (Block 4).

**Stage 2** (new this pass, Blocks 5-9 below): `look`/`sight`/`what is [at] <where>` — an explicit
request for the 9K113, distinct from `scan` (which still lets Petrovich pick eyes/binoculars/
9K113 on its own). `look left`/`look right` reuse the same left/right sector `scan` already does.
`look <o'clock>`/`look <compass>` sweep that 30°/45° wedge near-to-far, twice, then say
"<where>, clear." and resume whatever was running before. A spoken distance narrows the sweep to
a band around it. OBSERV off defers via the existing confirm band; an attack run refuses the
command outright; a later `scan`/`look`/task-changing command supersedes a running or pending
look.

## What this does NOT test (deferred, not a gap)

- **The "quick position check" for a known, unmoved contact.** Flagged as an open Decision in
  `plans/9k113-scan-procedure/plan.md` ("how short, how often" are new judgement calls the plan's
  source material does not answer) — left as the current "simply don't re-look until it moves or
  the stall cooldown lapses" behaviour. No new action to observe.
- **Anything above ~2000 m AGL.** Out of the stated operating envelope; not built, not tested.
- **The exact band-edge numbers past the 1.5 km near edge** (4/8/13.6 km), and
  `POINT_SWEEP_COUNT`/`POINT_DISTANCE_BAND_HALF_KM`'s default values. All tunable via
  `config/tuning.toml`, not fixed truths to verify against.
- **Landmarks, waypoints, player-set marks as a `look`/`scan` target.** Out of scope for this
  item; o'clock/compass/relative only.

## Acceptance boundary — what no fixture here could reach

Every unit test in this feature drives the state machine directly with synthetic altitude/
attitude/contact inputs and synthetic transcripts. That proves the mechanism never stalls and the
geometry matches the spec on paper. It cannot show whether the scan **looks and feels** like the
procedure you described from the cockpit: whether the ahead-window alternation is noticeable
without being distracting, whether the mandatory per-lap naked-eye pause reads as a natural beat
or as the sight visibly "stuttering", whether the `BL-B98` fix's resume-at-last-position (Block 4)
actually reads correctly — a believed aim is not itself observable, only the simulated sight's own
slewing back to it is — or whether a spoken `look <o'clock>`/`look <compass>` actually sounds and
times like a real request when you say it with your own voice, cadence and microphone, rather than
a scripted transcript fed straight to the matcher. None of that is testable from a unit test; all
of it is what this flight is for.

## Setup — UNVERIFIED on the live box

I ran the Mac-side mechanical checks (format/lint/mypy/pytest, defaults.toml regeneration) myself,
and ran every spoken-command utterance in this card through the real matcher
(`audio-adapter/src/command_matcher.py::match_transcript`) myself — see
`plans/9k113-scan-procedure/dod-check.md` for both. I cannot run any DCS-side step from here; every
step below is labelled UNVERIFIED and is the standard power-up/launch sequence already used on
prior 9K113 sorties, unchanged by this feature.

1. **UNVERIFIED** — Start DCS, take an air start in the Mi-24P, straight and level, 300-500 m AGL
   to begin (you'll go lower and higher for specific checks below).
2. **UNVERIFIED** — Get the 9K113 ready the usual way: after an air start, wait for Petrovich's
   "Guidance unit ready" (or run the power-up yourself if it does not come), then say
   **"Observ on."** Confirm the sight begins its idle search (it should start sweeping
   `wide_near` first).
3. **Verified on the Mac (`--help`), UNVERIFIED in flight** — start body-layer the normal way, on
   the Mac, from the repo root:

   ```sh
   cd run-scripts && ./run-body-layer.sh
   ```

   No new flags for this feature. Since BL-B96 (on `main`, and on this branch) there is no
   `--crew-text`; speech in/out is always on and `--audio-adapter-url` is required, which the
   script already passes.

## Flight blocks

### Block 1 — sector commands and their widths

**Do:** with OBSERV on and nothing commanded (free scan), watch the sight sweep a few laps of
`ahead` on its own.
**Expect:** the sight sweeps a forward window roughly 40° wide, then after about 30 seconds
switches to sweep a different (overlapping) 40° window shifted toward the other side, then back —
this is the ahead-window alternation, not a single fixed cone.
**Record:** did you actually see two different windows, or does it look like one wide sweep the
whole time? Did the switch between them look natural or did it look like a jump/stutter?

**Do:** say **"Scan left."**
**Expect:** the sight sweeps the whole left half of its forward view — from dead ahead out to
about 60° left of the nose — not a narrow slice near 9-11 o'clock.
**Record:** did the sweep reach out to roughly your left wingtip's forward quarter, or did it feel
narrower/wider than that?

**Do:** say **"Scan right."**
**Expect:** mirror of the above, dead ahead to about 60° right.
**Record:** same question, mirrored.

**Do:** say **"Scan one o'clock"** (or any single forward o'clock hour you can command).
**Expect:** the sight points and sweeps a narrow wedge centered on that hour — noticeably
narrower than the left/right sectors above.
**Record:** did the commanded hour look right relative to the nose?

### Block 2 — the near band and the naked-eye pause

**Do:** with a free scan running (nothing commanded) and no contacts nearby to distract the look
mechanism, watch one full lap: `wide_near` → `wide_far` → `narrow_far_sweep` → pause → back to
`wide_near`.
**Expect:** the near leg's own near edge should sit noticeably closer than mid-range — around
1.5 km, not the old ~2.3 km — so the sight starts low/close rather than skipping the near
ground. After the far leg finishes, the sight should pause and do a brief naked-eye-style
all-round look (the sight stops sweeping, Petrovich's own naked-eye attention gets a moment)
before restarting the cycle at `wide_near`.
**Record:** did you see the near edge start close, roughly where you'd expect ~1.5 km to look
from the cockpit? Did a pause actually happen once per lap, or did it only ever happen on what
looked like a fixed clock regardless of where the sight was in its cycle?

### Block 3 — the two degraded-coverage combos

These are the two altitude/attitude combinations the implementer's own testing found empty one or
two of the three legs by pure geometry (the sight physically cannot depress far enough). Neither
should ever stall the search — the question is whether it *looks* useful from the cockpit, not
whether it technically keeps running.

**Do:** climb to about 800 m AGL, pitch the nose up about 10°, hold it, and watch a few laps of
free scan.
**Expect:** `wide_near` should come up effectively empty (the sight can't depress enough to reach
the 1.5 km near band from this attitude) — the sight should visibly skip straight to `wide_far`/
`narrow_far_sweep` rather than hanging on an empty near leg.
**Record:** does the search still look like it's doing something useful, or does it look stuck/
idle? How long is the gap before it moves on?

**Do:** level off at about 1500 m AGL, wings level, no pitch correction, and watch a few laps.
**Expect:** both `wide_near` and `wide_far` may come up empty at this altitude level
(per the implementer's own measurement) — only `narrow_far_sweep` should reliably produce
coverage. Try adding about 8° of nose-down and watch again; the near/mid legs should recover.
**Record:** level, does the search look genuinely degraded (long gaps, little visible activity)
or does `narrow_far_sweep` alone keep it looking purposeful? With 8° nose-down, do the other two
legs visibly come back?

### Block 4 — the sight's resume position, before and after OBSERV (BL-B98, now fixed)

`BL-B98` (the dead-ahead resume after a glance-away) was fixed on this branch after this card was
first written — the sight now holds its last position through a glance-away and resets only on
OBSERV going off. The two cases below replace the old "known defect" observation.

**Do:** during any of the naked-eye pauses above (Block 2's lap-completion pause, or an ordinary
30-second `SIGHT_MAX_DWELL_S` break if you see one happen first), watch where the sight points
when it resumes, and note roughly where it was pointed just before the pause started.
**Expect:** the sight resumes from that same last position, not dead ahead `(0°, 0°)` — unless it
happened to already be near boresight, in which case you will not be able to tell the difference
from this test alone.
**Record:** when the sight resumed, did it pick up roughly where it left off, or did it visibly
snap to dead ahead? Speakable answer: "resumed where it was" / "snapped to center" / "couldn't
tell, it was already pointed roughly ahead."

**Do:** with OBSERV on and the sight pointed well off boresight (e.g. mid-sweep of `scan left` or
`scan right`), say **"Observ off,"** then say **"Observ on"** again.
**Expect:** after OBSERV comes back on, the sight starts its fresh search from boresight
`(0°, 0°)`, not from wherever it was pointed when you switched it off.
**Record:** after turning OBSERV back on, did the sight begin its new search pointed straight
ahead, or did it pick up from its old off-boresight position? Speakable answer: "started straight
ahead" / "picked up from the old position."

**Do (if you can provoke it safely):** with OBSERV on and the sight off boresight, fly a hard
manoeuvre sharp enough to trigger the existing violent-manoeuvre OBSERV-off behaviour, then say
**"Observ on"** again.
**Expect:** same as above — the sight resumes from boresight after this OBSERV-off, not from its
pre-manoeuvre position.
**Record:** did the forced OBSERV-off-then-on also reset to dead ahead, matching the commanded
OBSERV-off case above? Speakable answer: "yes, same reset" / "no, it kept the old position"
(the latter would be a new defect, not `BL-B98`).

### Block 5 — `look left`/`look right`, the 9K113-specific sector request

**Do:** with OBSERV on, say **"Look left."**
**Expect:** same sweep as Block 1's "Scan left" (dead ahead to ~60° left), but Petrovich should
acknowledge with just **"Left."** rather than "Scanning left." — `look` is its own verb, not a
`scan` echo.
**Do:** say **"Look right."**
**Expect:** mirror, acknowledged **"Right."**
**Record:** did both match Block 1's sweep width, and did the readback say "Left."/"Right." rather
than "Scanning left."/"Scanning right."?

### Block 6 — `look <o'clock>`: a 30° wedge, near-to-far, two sweeps, then clear

**Do:** pick a forward o'clock hour with nothing in it (e.g. an empty sky at one o'clock) and say
**"Look two o'clock."** Matcher-checked (below): resolves to the explicit 9K113 point request,
clock slot 2.
**Expect:** Petrovich says **"Two o'clock."**, the sight swings to a ~30° wedge centered on that
hour and sweeps it near-to-far, does this **twice**, then says **"Two o'clock, clear."** and
resumes whatever free scan was running before — not a single pass, and not silence if nothing is
there.
**Record:** did you count two visible sweeps of the wedge before "clear"? Did the sight genuinely
return to its previous scanning afterward?

### Block 7 — `look north`/a compass bearing, and a look with a stated distance

**Do:** say **"Look north."** (or any compass direction).
**Expect:** a ~45° wedge centred on true north (compass-relative, not o'clock-relative), same
two-sweeps-then-clear behaviour as Block 6, readback **"North."**.
**Do:** with a real contact at a known clock/range, say, e.g., **"Sight two o'clock, three
kilometres."**
**Expect:** the sweep narrows to a band around 3 km (roughly 2-4 km) rather than sweeping the
whole wedge near-to-far — it should find the contact faster than an unbounded look would.
**Record:** did the compass wedge look wider than the o'clock wedge from Block 6? Did the
distance-qualified look narrow in on the stated range?

### Block 8 — OBSERV off, attack run, and supersession

**Do:** with OBSERV **off**, say **"Look two o'clock."**
**Expect:** Petrovich says **"Need observ, confirm?"** — he does not refuse outright and does not
start the sight. Say **"Yes."** (or "Confirm," or "Observ on.").
**Expect:** OBSERV comes on, and once the guidance unit is ready the deferred look starts on its
own — you should not need to repeat "Look two o'clock."
**Do (separately):** repeat the above but say **"No."** instead.
**Expect:** the look is dropped silently — no "unable," no further speech, OBSERV stays off.
**Do:** during an attack run (OBSERV on or off), say **"Look two o'clock."**
**Expect:** **"Unable, attack run."** — the sight stays on the run's own target.
**Do:** start a `look <o'clock>`, then before it clears say **"Scan left"** (or any other `look`/
`scan`/`follow`/`select target`/`engage`/etc.).
**Expect:** the new command takes over immediately — the old look does not finish its sweep or
speak "clear."
**Record:** did the confirm/yes/no flow work as described? Did the attack-run refusal use exactly
the words "Unable, attack run"? Did a later command cleanly take over without a leftover "clear"
from the old look?

### Block 9 — a found target during a `look`, then back to scanning

**Do:** command a `look <o'clock>`/`look <compass>` at a sector or bearing where a real contact is
present.
**Expect:** Petrovich interrupts the sweep to look at and report the contact the normal way
(whatever he'd say for any detected/classified contact — target count makes no difference), then
resumes the commanded look afterward rather than abandoning it.
**Record:** did the contact get reported in the usual way, and did the commanded look continue
(not silently vanish) afterward?

## Bring back

- Block 1: did `ahead`'s two windows, `left`/`right`'s full-half-regard width, and a commanded
  o'clock hour's narrow wedge all look like what you described originally?
- Block 2: did the near edge look like ~1.5 km, and did the per-lap pause actually happen once per
  lap?
- Block 3: at 800 m/10° nose-up and 1500 m level, did the degraded search still look purposeful,
  or did it look broken/stuck?
- Block 4: did the sight hold its position through a glance-away, and did it reset to boresight
  only on OBSERV going off (commanded or manoeuvre-forced)?
- Block 5: did "look left"/"look right" sweep the same as "scan left"/"scan right" but with the
  shorter "Left."/"Right." readback?
- Block 6: did "look two o'clock" sweep twice before saying "clear," and resume afterward?
- Block 7: did the compass wedge look wider than the o'clock wedge, and did a stated distance
  narrow the sweep?
- Block 8: did the OBSERV-off confirm/yes/no flow, the attack-run refusal wording, and supersession
  by a later command all behave as described?
- Block 9: did a found target get reported and the look resume afterward, rather than vanishing?
- **Anything that surprises you is worth more than anything on this list.**

## Results

(not yet flown)
