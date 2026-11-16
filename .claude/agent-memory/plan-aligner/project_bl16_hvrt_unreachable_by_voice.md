---
name: project_bl16_hvrt_unreachable_by_voice
description: BL-16 Stage P2 vocabulary check — a mode-exclusive voice command can have a token, a mode gate and a readback and still be dead, if nothing ever drives the mode-cycle into the mode it's gated on.
metadata:
  type: project
---

BL-16 Stage P2 ("Stage P2 ready to build", 2026-11-16) gave the HVRT translate vocabulary
("left"/"right"/"forward"/"back", "up"/"down") a token, a state gate (`ai_mode == "HVRT"`), and a
readback — by the plan's own traceability table that reads as complete. It is not: the dispatch
rule drops the command as unmatched when `ai_mode != "HVRT"`, and nothing in the plan ever presses
the short-left cycle to get from HVR into HVRT. The player's only way in is the physical wheel,
which the plan elsewhere (U3) says he shouldn't need to touch. The plan's own sibling actions
(`cbtm_align`, `cbtm_break`) use a "cycle-then-press" shape for the exact same mode-exclusivity
problem; HVRT translate was the one command that didn't get it, with no stated reason.

**Why this was easy to miss**: the vocabulary-table traceability check (token → goal → readback)
is satisfied row by row, so a per-row trace reads as "done." The gap is one level up — not in the
row's own fields, but in whether the *mode the row is gated on* is ever reachable by the same
voice-only path the rest of the plan insists on. A per-row check misses a cross-row mechanism gap.

**How to apply**: when a vocabulary/command table has a mode or state gate, check not just "does
this row have a token/action/readback" but "does anything in this plan ever drive the system into
the gated state by the same input channel (voice) the row itself requires." Compare against the
plan's own other mode-gated actions — if every other one cycles-then-presses and this one doesn't,
that asymmetry is the tell, not something to wave off as "different by design" without the plan
saying so.

Second, smaller finding in the same pass: `mode_blocked` (a control-mechanism failure — the wheel's
own short-left cycle exhausting its attempt bound) was folded into A4's "no callout for a goal not
reached" (a *physical*-limit posture), while the same plan's own still-open U1 recommends a spoken
"unable, not ready" for the identical signal on a sibling action (`cbtm_align`). Check whether a
cited precedent (A4) actually covers the failure mode being justified, not just whether some
precedent exists with similar wording ("no callout") — a mechanism failure and a physical limit
are different failures even when the "no 'unable'" posture sounds the same for both.

See also [[project_bl16_vocabulary_grep_stopped_one_layer_short]] (the sibling case: new tokens
reaching dispatch but not the whisper-bias table) — same shape, one layer further out: here the
token reaches whisper and dispatch fine, but the *state* dispatch depends on is never produced.
