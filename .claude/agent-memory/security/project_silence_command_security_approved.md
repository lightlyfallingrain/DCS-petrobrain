---
name: silence-command-security-approved
description: silence-command (body-layer + audio-adapter) security deep analysis — APPROVED, the two stuck/silent-without-ack properties checked by code tracing, not assertion
metadata:
  type: project
---

`feature/silence-command` (tip `250270c`) deep-analysis APPROVED 2026-10-04. No new dependency
(both `pyproject.toml`s diff empty). The two safety-relevant properties were checked by tracing
actual code paths, not by trusting the implementation/review docs' account:

- **Ack-before-mute is structurally guaranteed**, not just ordered correctly today: `_handle_silence`
  calls `_print` (which pushes the ack) strictly before `self.silenced = True` is assigned. Every
  exception inside `_print`'s per-sink pushes is caught with a scoped `except` except one
  (`overlay_client.push_text_line` on a non-`AircraftLayerError`), and that one fails *toward not
  silencing* (propagates before the flag flip) rather than toward silencing without an ack.
- **Clearing (`self.silenced = False`) is a bare in-memory assignment** placed before any fallible
  dispatch logic in both `handle_command` and `_handle_utterance`'s "handled" branch — no I/O or
  parsing sits between "a command was recognised" and "the flag clears," so there is no exception
  path that can leave it stuck on.
- **The elevated `ACT_FLOOR_CANCEL` (0.80) floor for `silence` is live on the real voice path**,
  confirmed by reading `classify_response`'s actual `floor = ACT_FLOOR_CANCEL if token in
  CANCEL_TOKENS else ACT_FLOOR` line and tracing that `handle_transcript` → `_act_on_voice_decision`
  is the only route from a live transcript to `"act"` disposition — not merely checking that
  `"silence"` was added to the `CANCEL_TOKENS` set.

General pattern worth reusing: for any "can state X be set/stuck without property Y holding" claim
in a plan/review, trace the actual write site and its surrounding exception handling rather than
accepting the ordering described in prose — this is the fourth-ish time pre-existing docs described
the code accurately, but the independent trace is what makes the "APPROVED" trustworthy rather than
inherited. See [[project_br1_stage2_ollama_trust_boundary]] for a previous case where this kind of
trace caught a real divergence the docs didn't.
