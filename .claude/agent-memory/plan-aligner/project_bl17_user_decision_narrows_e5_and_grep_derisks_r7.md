---
name: project_bl17_user_decision_narrows_e5_and_grep_derisks_r7
description: BL-17 speech-rules plan check — a later user decision (U13) legitimately narrowed E5's wording, and grep found the plan's own risk (R7) was already half-solved in code.
metadata:
  type: project
---

BL-17 (`plans/speech-rules/alignment.md`, plan check 2026-11-17): the goal check's E5 said
Petrovich "says what is missing" on a rule load failure. The user's own later decision (U13,
`body-layer/ROADMAP/BL-17.md`) narrowed that to one fixed spoken phrase ("Action file error."),
with the cause only in the stderr log — *"One fixed phrase, not a per-cause description."* The
plan (D6) follows U13, not the goal check's literal wording.

**Why this is not a misalignment, unlike `[[project_bl_b111_decision_narrows_just_answered_expectation]]`:**
there, an open Decision quietly reopened the exact failure an expectation existed to close, with
no attribution. Here the narrowing is a *named* `U<n>` decision, explicitly quoted, and this
task's own framing says `ROADMAP/<feature>.md` decisions override the alignment file where they
differ. The distinguishing question going forward: is the narrowing attributed to a specific user
decision on file, or is it an unexplained gap between the goal check's prose and the plan's
behaviour? The former is `met, narrowed by U<n>` — note it, do not escalate. The latter is a
Finding.

**Second, smaller lesson:** the plan's R7 said an offset mark's reference-moment mechanism "may
have to carry the timestamp" from PTT release — framed as still-to-be-built. A grep
(`audio-adapter/src/capture_loop.py`, `transcribe_client.py:54`, `server.py:357-412`) found
`t_ptt_release_wall` already minted at PTT release and already threaded through `POST
/transcribe` — just not yet copied into `TranscriptEvent`/`transcript_queue`, which still stamps
`t_wall=time.time()` at match-completion (`server.py:395`). The risk was real (confirmed: today's
`t_wall` is not release time) but overstated as *unbuilt* when the hard part already exists.
**Grep a plan's own stated risk before accepting its framing at face value** — it can be both
correct and more pessimistic than the code already warrants, same genre as grepping an "unchanged"
claim (`[[project_relative_distance_grouping_clean_trace]]`,
`[[project_bl_b110_third_pass_clean_resolution]]`) but here applied to a *risk*, not a claim of
no-change.
