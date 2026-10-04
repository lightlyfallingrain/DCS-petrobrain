### Definition of Done — `silence` command

**Branch `feature/silence-command`, tip `de6c530`** (verified: `git rev-parse HEAD` matched before
anything else ran). No `plan.md` — no architect pass preceded this; the user's own message settled
the two load-bearing decisions directly (absolute silence including urgent callouts; one spoken
acknowledgement). `implementation.md` records the remaining design points, per the task's own
framing.

### Code Quality

Two subprojects touched (`git diff --name-only main...HEAD`): `body-layer/` and `audio-adapter/`.
Both run from fresh `.venv`s built in this worktree (none existed), matching the implementer's and
Reviewer's own reported figures exactly:

| | body-layer | audio-adapter |
|---|---|---|
| `ruff format --check src tests` | pass (114 files) | pass (29 files) |
| `ruff check src tests` | pass | pass |
| `mypy src` (`--strict`) | pass, 53 source files | pass, 15 source files |
| `pytest tests -q` | **1398 passed, 4 xfailed** | **219 passed, 1 skipped** |

(`pytest` in body-layer prints a `BrainLayerError`/`URLError` traceback mid-run — a background
async-client test exercising a deliberately-refused loopback connection, not a failure; the summary
line is clean.)

No debug output, no `TODO`/`FIXME`, no bare `except: pass` introduced — grepped the full diff of
both `src` trees. No unhandled errors in data paths: Security's deep analysis independently traced
every write site around the new `self.silenced` flag and found the one real failure mode (an
exception during the ack's own push) fails toward *not* silencing, never toward stuck-on.

### Scope & Correctness

- Matches the user's own direction, recorded verbatim in `implementation.md`: absolute silence
  including urgent callouts, one spoken acknowledgement, ended by any subsequent dispatched
  command.
- No unplanned scope: two items were explicitly flagged and *not* built — `brain_reply.
  OFFERED_CONFIRM_VOCABULARY` left unextended (brain-layer's own concern), and no DCS F10 menu
  button (aircraft-layer's Hook script, separate subproject). Both are documented, not silently
  dropped.
- No CLAUDE.md invariant violated: the no-omniscience boundary is untouched (this is a dispatcher/
  output-gating change, no new percept/contact field); module independence holds (no new
  cross-subproject import); the change is additive and a true no-op for anyone who never says
  `silence`.
- All files staged: working tree is clean (`git status --porcelain` empty) — Implementer, Reviewer
  and Security all committed their work already; this report and the roadmap/NOTES updates below
  are committed as part of this pass.

### Testing

- Core logic covered: 10 new body-layer tests pin the exact pushed tuple (not just truthiness) for
  the ack, the no-op-not-toggle behaviour, the suppressed-vs-heard distinction for both routine and
  urgent lines, and both ends of the silence/clear cycle including the unresolved-speech
  non-clearing case. 6 new audio-adapter tests (5 in `TestSilence` + 1 in `test_vocabulary.py`)
  pin all three phrasings, the `"stop"` non-collision, the cancel-family non-collision, and
  adversarial sentences.
- Tests are meaningful: Reviewer independently re-ran and re-derived the reasoning rather than
  trusting the implementer's account (confirmed `VERB_ANCHOR_WORDS` derivation and the `"quiet"`/
  `"quite"` collision against the real matcher, not the plan's claim of it).
- No existing tests broken: `test_dispatched_command_tokens_all_return_something`'s update is a
  mechanical consequence of `NO_RETURN_VALUE_COMMAND_TOKENS` gaining a member, not a weakening —
  Reviewer confirmed the loop ordering is safe.

### Documentation

- Reviewer's `review.md`: **APPROVED, no required fixes.** Two optional refinements noted (the
  `stop_talking`-while-silenced interaction; `HELP_TEXT`'s deliberate omission) — neither blocking,
  both already explained in `implementation.md`.
- Security's `security-review.md` (deep analysis): **APPROVED, no required fixes.** Ack-before-mute
  and no-stuck-on both verified by construction, not just by the implementer's claim.
- Non-obvious behaviour is explained in `implementation.md`'s "Design points settled" and "Notable
  Discoveries" sections, and the collision-check lesson is now in `NOTES.md` (see Harvest below).

### Security

- No `plans/silence-command/plan.md` and no `security-plan-review.md` exist, and that is expected
  under the current cadence (root `CLAUDE.md`'s "Agents" section: security runs once per feature,
  immediately before DoD) combined with there having been no architect pass to review a plan
  against in the first place — there was nothing for a plan-stage review to have run on.
- `security-review.md` (the deep-analysis pass) exists and is **APPROVED**. No dependency change
  (confirmed directly via `git diff` on both `pyproject.toml` files, not taken from the plan's
  account).

### Performance

**Deliberately no performance pass**, and this is a recorded decision, not a skipped gate: the
entire change is one `bool` check (`not self.silenced`) at the single existing `push_speech` call
site, on a path that already does synchronous HTTP I/O to the TTS engine. Security's own review
explicitly agreed no separate performance pass was warranted, for the same reason. There is nothing
on this path for a performance review to measure.

### Mechanical checks summary

**PASS.** All four commands clean in both subprojects, test counts match exactly across
implementer/Reviewer/Security/DoD (four independent runs, same numbers), no debug/TODO/error-
suppression findings, clean working tree, both required sign-offs present and approved.

### Acceptance boundary — what fixtures structurally cannot reach

Everything above is a fixture/console-and-static-analysis result. It proves the gate is singular,
the ack precedes the mute, and the state machine cannot get stuck. It proves nothing about:

- **Whether the recogniser, on this pilot's actual voice and accent, resolves any of the three
  phrases at all.** No benchmark recording exists for `"silence"`/`"be quiet"`/`"shut up"` — unlike
  the F10 vocabulary's full accent-adapted corpus. This is unmeasured by construction, not by
  oversight.
- **Whether one word of acknowledgement is the right amount** in the cockpit, under workload,
  versus too little or too much.
- **Whether absolute silence through an actual threat still feels like the right call once it has
  been felt, not just chosen in the abstract.** The user chose this deliberately when asked, but a
  chosen behaviour and a lived one are different data points — this project's own precedent (the
  F10 contact-list menu, the mission-frequency correction) is that lived experience has reversed
  earlier choices before.

None of this is a defect or a gap in the gate above — it is the honest line past which only a
sortie, not a fixture, can answer. Card published:
https://claude.ai/artifact/XJxhmMrmYMfTSHQC3dPS4m (source: `docs/acceptance/
2026-10-04-silence-command.md`). Live acceptance is **deferred, not waived** — recorded on
`body-layer/ROADMAP.md`'s live-acceptance debt list, since the plan never scoped it out and this
is exactly the "the sortie the next day found two real defects" class of risk this project's own
history warns about.

### Verdict

**DoD: PASSED** (mechanical gate). Acceptance testing: pending the user's own flight — see card
above.
