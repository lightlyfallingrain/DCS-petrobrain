# BL-B89 Stage 1 acceptance — 9K113 sector scan flight

Source of truth for the published card (the main loop publishes the artifact from this file — do
not fly from a copy, fly from whatever the card links back to here).

**Card:** https://claude.ai/artifact/M9jAnsomghXnV1bSyds9Mj

**Branch:** `feature/9k113-scan-procedure` (tip `7611888cbbf5808828d59b0d742e5aede1c225d8`) —
`git checkout feature/9k113-scan-procedure`, in your own repo root, not a worktree. Not yet
merged — DoD's mechanical checks, Reviewer, Security and Performance Reviewer have all passed;
this flight is the one thing that has not run yet.

**Player in the PILOT seat.** Petrovich operates the opposite seat (CPG) for this feature — you
are watching *his* sight scan, not flying it from the CPG seat yourself.

**Air start, straight and level** — the 9K113 is a warm unit by the time you take the controls
(`project_probes_flown_air_start`); no cold power-up sequence needed for these checks, but the
power-up ("Observ on" after MISSILE POWER / CPLR DISTR / Sight Power / ЩО PWR) still gates the
sight, same as every other 9K113 sortie.

## What this tests

Stage 1 of BL-B89: the sight's idle search now cycles three legs (`wide_near` 1.5-4 km,
`wide_far` 4-8 km, `narrow_far_sweep` 8-13.6 km) over the sectors you described — `ahead`
alternating two 40°-wide windows, `left`/`right` spanning the whole left/right half of the
sight's own ±60° regard, a commanded o'clock hour its own 30° wedge — and closes every lap with a
mandatory naked-eye pause, not just the pre-existing time-based one. Stage 2 (pointing the sight
at a named place) is designed but **not built** — do not expect a `point` command to exist yet.

## What this does NOT test (deferred, not a gap)

- **Stage 2 (pointing at a named o'clock/bearing).** Not built this round.
- **The "quick position check" for a known, unmoved contact.** Left as the current
  "simply don't re-look until it moves or the stall cooldown lapses" behaviour — no new action to
  observe.
- **Anything above ~2000 m AGL.** Out of the stated operating envelope; not built, not tested.
- **The exact band-edge numbers past the 1.5 km near edge** (4/8/13.6 km). Only the near edge is
  the user's own correction — the rest are the explore mock's placeholders, tunable via
  `config/tuning.toml`, not fixed truths to verify against.

## Acceptance boundary — what no fixture here could reach

Every unit test in this stage drives the state machine directly with synthetic altitude/attitude/
contact inputs. That proves the mechanism never stalls and the geometry matches the spec on
paper. It cannot show whether the scan **looks and feels** like the procedure you described from
the cockpit: whether the ahead-window alternation is noticeable without being distracting,
whether the mandatory per-lap naked-eye pause reads as a natural beat or as the sight visibly
"stuttering" (the plan's own flagged risk, since the lap-completion pause and the old
`SIGHT_MAX_DWELL_S` clock can now fire in close succession), and whether `BL-B98`'s dead-ahead
resume (see below) is jarring to watch happen or unremarkable. None of that is testable from a
unit test; all of it is what this flight is for.

## Setup — UNVERIFIED on the live box

I ran the Mac-side mechanical checks (format/lint/mypy/pytest, defaults.toml regeneration) myself
and they all pass — see `plans/9k113-scan-procedure/dod-check.md`. I cannot run any DCS-side step
from here; every step below is labelled UNVERIFIED and is the standard power-up/launch sequence
already used on prior 9K113 sorties, unchanged by this feature.

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

### Block 4 — the dead-ahead resume (BL-B98, observation only — not a pass/fail for this card)

**Do:** during any of the naked-eye pauses above (Block 2's lap-completion pause, or an ordinary
30-second `SIGHT_MAX_DWELL_S` break if you see one happen first), watch where the sight points
when it resumes.
**Expect (known, filed as `BL-B98`, not a defect of this stage):** the sight resumes pointing
dead ahead `(0°, 0°)`, not at wherever it last was pointed before the pause.
**Record:** does this read as a visible "snap to center" that looks wrong in the cockpit, or is it
unremarkable because the sight was already roughly central? This is the information `BL-B98`
needs before anyone decides whether to fix it — note what you actually see, not whether you think
it's correct.

## Bring back

- Block 1: did `ahead`'s two windows, `left`/`right`'s full-half-regard width, and a commanded
  o'clock hour's narrow wedge all look like what you described originally?
- Block 2: did the near edge look like ~1.5 km, and did the per-lap pause actually happen once per
  lap?
- Block 3: at 800 m/10° nose-up and 1500 m level, did the degraded search still look purposeful,
  or did it look broken/stuck?
- Block 4: how did the dead-ahead resume look — a problem worth prioritizing, or genuinely minor?
- **Anything that surprises you is worth more than anything on this list.**

## Results

(not yet flown)
