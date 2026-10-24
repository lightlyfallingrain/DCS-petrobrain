# 2026-10-24 — sortie feedback

Captured verbatim the moment it arrived, before any diagnosis or fix (root `CLAUDE.md`, "Flight
feedback is captured, then explored, then planned"). Arrived in the same message as the instruction
to merge BL-B90 to `main`, so which branch was flown is not yet stated.

## F1 — slew axis must be zero while OBSERV is off

> *"when observ is OFF, the slew axis values must be 0. We don't slew a sight that is off."*

**Unexplored.** One pointer for the explore, not a diagnosis: `Export.lua`'s `run_sight_servo` resets
its own goal and state and **returns early** when arg 886 reads off. Whether that early return also
leaves the last axis value written (latched), rather than writing zero, is not yet checked.

**Explored, 2026-10-24.** Asked what was seen: *"i saw the ASP-17 mark moving."* The user's
direction, verbatim:

> *"do this: when observ is turned OFF, either by Petrovich or by DCS AI or by player, then write 0
> to both axis, but only once. Then stop writing the axis values. We should only write axis values
> when observ is ON."*

So the rule has three parts:

1. On the OBSERV on→off transition, whoever moved the switch, write 0 to both slew axes **once**.
2. While OBSERV is off, write nothing.
3. Axis values are written only while OBSERV is on.

Fixed on `fix/observ-off-axis-zero`, merged to `main` 2026-10-24 (`e1d16037`). DoD: fixture-verified (21/21 `test_sight_servo_lua.py`
against the real `run_sight_servo`, 619/619 full aircraft-layer suite, format/lint/`mypy --strict`/
`luac5.1 -p`/own-helper-leak scan all clean); Reviewer and Security both APPROVED, no required
fixes. `#needs-flight` — no fixture can confirm that `SetCommand(..., 0.0)` actually recentres the
real ASP-17 mark rather than merely halting further motion from wherever it was; see the flight
check below.

**Flight check** (card: https://claude.ai/artifact/Cwgypqi7oLswCVoZwLfPrN, branch
`fix/observ-off-axis-zero`):

1. **Setup.** OBSERV on, slew the sight with Petrovich active (voice/F10 `Watch`/`Scan` command, or
   just let his autonomous scan run) so the mark is visibly off-centre and moving.
2. **Do**: turn OBSERV off **by Petrovich command** (e.g. `Cancel Task` while he is watching/scanning,
   or whatever currently drives his own OBSERV-off path). **Expect**: the mark stops moving within
   one frame of OBSERV going off. **Record**: does it stop where it was, or snap/drift to centre?
3. **Do**: turn OBSERV off **by hand** (the cockpit switch/keybind). **Expect**: same — stops, does
   not keep wandering. **Record**: same question — stop-in-place or recentre?
4. **Do**: turn OBSERV off **via the DCS AI** (let a hard manoeuvre trigger DCS's own auto-OBSERV-off,
   per `[[BL-B80]]`'s "home_phase" note) if one can be provoked, otherwise skip and say so. **Expect**:
   same stop behaviour. **Record**: same question, plus whether this path was reachable at all this
   sortie.
5. **Bring back**: for each of the three causes exercised, did the mark *stop in place* or *snap to
   centre*? (The fix commands `(0.0, 0.0)` once, which is the servo's own zero/centre convention —
   `debug.md`'s own open question is whether DCS's gimbal interprets that as "go to centre" or "stop
   wherever you are.") Anything that surprised you is worth more than this list.

## F2 — "eyes on" for an attack-run target behind a mountain

> *"during attack run I got "eyes on, 9 o'clock" for target that was certainly behind a montain. It
> did cleart cockpit mask then, but should not have been seen."*

**Unexplored.** "Eyes on, …" is BL-B70 §10's regaining-sight line (`belief/attack_run.py`, the
`regaining_sight` branch). It is keyed on the cause changing away from `"too_far"`, not on line of
sight. BL-B76 notes that a terrain-blocked live LOS verdict never reaches belief. The two may be
related; that is not yet checked. The logs and the branch flown are not yet in hand.

**Explored, 2026-10-24.** Answers, verbatim:

- **"Eyes on" means he sees it.** *"if there is no LOS, there is no eyes on. That's the whole
  meaning of eyes on, that he *sees* it."*
- **Wording: option C.** Shown three mocks: A, silence until he really sees it; B, *"Lost it behind
  the ridge, 9 o'clock"*; C, *"Behind the ridge, 9 o'clock"* said once, when the target leaves the
  cockpit-frame mask but terrain still hides it. The user: *"option C, because I still get info on
  where it's believed to be"*. Asked whether "ridge" can be said truthfully for any terrain:
  *"ridge/hill/any terrrain -> "ridge""*. So it is always "ridge".
- **History.** *"yes, had visual, lost when I turned away and flew mehind ridge, a minute or so"*.
- **Logs.** The detection trace is *"a 200 MB detection trace, too large"*, so this is diagnosed
  from code without it.

## F3 — new command: "where is it?" during an attack run

> *"Add command "where is it?" that gives me an update during an attack run based on A) seeing the
> target B) current belief*
> *- use the standard attack run guidance phrase, just trigger it on that command. Nothing else
> needed."*

**Plan decisions, 2026-10-24** (on `plans/attack-run-los/plan.md`, verbatim):

- **Outside an attack run.** The plan proposed *"Unable, no attack run."* The user: *"if target is
  set, then answer. If no target (and therefore no attack run either) then say "No target""*.
- **Behind the ridge is held until he sees it again.** The main loop proposed that a fresh
  terrain-blocked verdict keeps the target "behind the ridge" until a real look, rather than
  decaying to silent "unknown". The user: *"agreed"*.
- **Command surface.** *"voice only"*.

Fixed on `feature/attack-run-los` (`plans/attack-run-los/plan.md`): the loss/regain register
re-keyed from `cause == "too_far"` to `tier != 1` (F2), a `terrain_blocked_held` flag holding a
genuine `"obstructed"` verdict's consequence across its own freshness-window staleness (Decision
2), and a voice-only `"where is it?"` command (F3). DoD: fixture-verified (body-layer 2663
passed/4 xfailed, audio-adapter 349 passed/2 skipped, both subprojects' format/lint/`mypy --strict`
clean; two independent mutation reversions confirm the register actually depends on the new
keying). Reviewer APPROVED, no required fixes. Security plan review/performance/security deep
analysis all waived by the user for this change. `#needs-flight` (`[[BL-B97]]`) — nothing here can
confirm the new wording lands at a moment that actually helps during a live run, or that "where is
it?" behaves correctly against DCS's own timing rather than the unit suite's synthetic ticks; see
the flight check below.

**Flight check** (card: https://claude.ai/artifact/BxG7nojsxP5tBA1YCk4Mob, branch `main`, once this
merges — or `feature/attack-run-los` directly before then):

1. **Setup.** Select an attack target, engage an attack run, and get Petrovich's naked eye to a
   genuine tier-1 look (he must actually be looking at and resolving it, not just within acquisition
   range) so he says `"Eyes on, ..."` once.
2. **Do**: turn away and fly behind terrain (a ridge, hill, or any mask) for long enough that the
   old bug's ~1.5 s/2.0 s freshness windows would have lapsed — at least 15–20 s, matching the
   reported "a minute or so." **Expect**: no further `"Eyes on, ..."` while still behind the mask.
   The first qualifier spoken on losing sight should be `"Behind the ridge, <o'clock>."` if a fresh
   terrain-blocked verdict was seen, said once — not repeated every tick. **Record**: was any
   `"Eyes on"` heard while the target was still genuinely hidden? Did `"Behind the ridge"` fire, and
   only once?
3. **Do**: continue the turn until the target is genuinely back in naked-eye view (no mask, no
   terrain, in FOV and range). **Expect**: `"Eyes on, <o'clock>"` fires now, on the real re-look.
   **Record**: did it fire at the moment of genuine re-acquisition, not before?
4. **Do**: during the run, before any sighting this sortie, say `"where is it?"` with a target set
   but the run not yet engaged. **Expect**: the standard guidance phrase, from whatever belief is
   currently held (not a refusal). **Record**: what was actually said.
5. **Do**: say `"where is it?"` with no target selected at all. **Expect**: `"No target."`
   **Record**: exact wording heard.
6. **Do**: say `"where is it?"` again while behind terrain, after step 2's "Behind the ridge" has
   fired. **Expect**: the held qualifier still shows up in the answer (not silently reset to bare
   guidance). **Record**: what was said.
7. **Bring back**: anything the wording did that did not match "he only claims to see it when he
   genuinely does" — a false "Eyes on", a missing "Behind the ridge", a "where is it?" answer that
   felt stale or wrong. Anything that surprised you is worth more than this list.
