---
name: feedback_check_for_an_existing_general_mechanism_before_scoping_a_new_one
description: When asked to judge where a requested new delay/gate/constant belongs, grep for whether a general mechanism already produces most of the asked-for effect before recommending new attack-run-local (or feature-local) machinery.
metadata:
  type: feedback
---

On BL-14's Stage 4-5 fix review (`plans/attack-run/review.md`, "Stage 4-5 fix review"), the user
asked mid-review whether a newly-requested "wait 1s after the readback before guidance speaks"
belonged as attack-run-local machinery or in the general occupancy model. Before answering from
first principles, grepping `callouts.py` surfaced that `CalloutScheduler.note_reply` already
extends `busy_until_sim` by `estimate_speech_duration_s(text) + INTER_UTTERANCE_GAP_S` (0.75s) for
**every** reply, including `engage`'s own readback — and `drain_attack_run`'s existing
`now_sim >= busy_until_sim` gate already waits for exactly that. The "new required change" was
~80% already built; the only real gap was a constant (0.75 -> 1.0), not new mechanism.

**Why:** A request phrased as "add X" reads as "X does not exist yet." On a codebase with this
one's density of named, documented constants (`INTER_UTTERANCE_GAP_S`, `SPEECH_RATE_WPS`,
`MIN_UTTERANCE_S`, `WATCH_REPORT_MIN_GAP_S`, `CALLOUT_MAX_AGE_S` all live in one file,
`callouts.py`, each with a provenance comment), the general case is already covered more often
than it first appears from inside the one feature module under review. Recommending new
feature-local mechanism without that grep risks (a) duplicating an existing gap/pacing concept
under a second name, and (b) misjudging where a constant belongs — a scheduling/pacing constant
filed in `attack_run.py` beside its three geometry constants would blur a module boundary
`docs/STRUCTURE.md` draws deliberately.

**How to apply:** Before answering "does this need new code, and where does it go," grep the
module that already owns the general version of the concept (here: the speech/occupancy module,
`callouts.py`) for constants and call sites that already touch the same axis (timing, gating,
pacing) as the request. If a general mechanism already produces most of the effect, recommend
bumping its existing constant over inventing a feature-local one — consistent with this project's
"mechanism and calibration never share a commit" invariant, since a constant bump is calibration-
only and a new mechanism is not. Only recommend new local machinery when the general mechanism
cannot carry the distinction being asked for (here: the scheduler's `busy_until_sim` has no
way to distinguish "busy because of a reply" from "busy for any other reason," which is the one
case that would force new mechanism rather than a bigger number).
