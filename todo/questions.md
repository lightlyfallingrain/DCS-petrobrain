# Questions queued for the user

Created 2026-10-06, when the user handed over an autonomous overnight run and said:
*"Any input you need from me, queue and I'll get back to it."*

**Rules for this file**, so it stays usable rather than becoming a second backlog:

- One question per entry, with **why it blocks** and **what happens if it is not answered** — if the
  answer is "nothing blocks, I picked a default", it does not belong here; it belongs in the plan or
  commit that records the choice.
- An entry is removed when answered, and the answer goes to the plan, roadmap entry or decision list
  it belongs to — never left only here.
- Agents running in worktrees cannot reach the user. Anything they queue arrives in their report and
  is transcribed here by the main loop.

---

## Open

### Q1 — `flight-feedback-clear.sh` cannot see a capture written through Bash (config change, needs your ok)

**What happened:** the feedback-capture hook fired correctly when you raised the two review items,
and then stayed up after the capture was written — so it warned on every later Architect dispatch
even though the feedback was captured *and* explored. `flight-feedback-clear.sh` is `PostToolUse` on
`Write|Edit` and matches `.tool_input.file_path`; the capture went into
`docs/acceptance/2026-10-05-sortie-feedback.md` via a Bash heredoc, which has no `file_path` field,
so the marker never cleared. I cleared it by hand.

**Why it will keep happening:** this session runs with an auto-mode instruction to prefer Bash for
file edits, so the common path for writing a file is exactly the one the hook cannot observe.

**Proposed fix:** add `Bash` to the clear hook's matcher and have it clear the marker when
`git status --porcelain docs/acceptance/` shows a change, rather than reading `file_path`. That makes
the hook observe the *effect* instead of the *instrument*, which is the same reasoning that made the
gate structural in the first place.

**Needs you because** it edits `.claude/settings.json` hook wiring, and I do not change your hook
configuration on my own judgement. Nothing blocks meanwhile — the gate is advisory and never blocks
a dispatch.

### Q2 — `BL-B36`: the speech log is a verbatim transcript of everything the microphone heard

From the 2026-10-05 security audit. The sortie log contains `"Peace."`, `"All right."`,
`"Can I sell it?"` — you talking, not commanding. Harmless on your own machine; this repo is
**intended to go public**, and a committed or shared log is a voice transcript of your living room.

**Three options, and it is your call which:** hash or omit non-command utterances; keep the full
transcript but make the log opt-in with that stated in `RUN.md`; or leave it and rely on never
sharing the file. I would take the second — the full transcript is genuinely useful for diagnosing
`say_again` cases, which is exactly what it earned its place for.

**Does not block** anything in flight. It blocks a public release.
