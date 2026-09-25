# DoD Check: brain-layer BR-1 Stage 1

Branch `feature/brain-layer` @ `9e135a7` (not yet merged). Verification below was run against
`1f0dd63`; the one commit added after (`9e135a7`, "Reframe the loopback default") touches only a
shell-script comment in `run-scripts/run-brain.sh` — no source, no test — so re-running format/
lint/type/test was not needed, and was confirmed unnecessary by reading that commit's diff
directly (`git show 9e135a7 --stat`: one file, `run-scripts/run-brain.sh`, comment only). Checked
from an isolated `git archive` scratch tree (`/private/tmp/.../scratchpad/brtree`), not the DoD
worktree's own checkout — the worktree is `main`-based and cannot check the branch out a second
time, and `pytest`'s `pythonpath` override has silently reported `main`'s baseline in place of a
branch's own figures before
(`.claude/agent-memory/dod/feedback_dod_worktree_pythonpath_trap_applies_here_too.md`).

## Subprojects touched

`git diff --stat main..feature/brain-layer` shows two code subprojects — `body-layer/`,
`brain-layer/` (new) — plus `plans/`, `docs/`, and agent-memory files. No `aircraft-layer/`,
`world-model/`, `audio-adapter/`, or `mission-interpreter/` changes.

## Code Quality

| Subproject | format | lint | mypy --strict | pytest | Result |
|---|---|---|---|---|---|
| body-layer | `105 files already formatted` | `All checks passed!` | `Success: no issues found in 49 source files` | `1220 passed, 4 xfailed in 12.65s` | PASS — matches expected 1220/4 |
| brain-layer | `8 files already formatted` | `All checks passed!` | `Success: no issues found in 5 source files` | `20 passed in 4.30s` | PASS — matches expected 20 |

All four commands run verbatim, from inside the archived tree's own subproject directory, against
each subproject's own venv (`/Users/sg/Code/DCS-petrobrain/{body,brain}-layer/.venv/bin/`, per
task instructions — these venvs exist only in the main checkout, read-only from here).

No `TODO`/`FIXME`/`XXX` in the touched source files. `print()` calls found in
`belief/escalation.py` (`DebugPrintBrainClient`, an intentional debug-aid stand-in, documented as
such in the module docstring) and `logger.py` (pre-existing console-output paths, not new debug
output). One `except Exception:` in `brain-layer/src/server.py:77` — read in context: it is
`_run_job`'s documented crash boundary around `Decider.decide`, logs via `logger.exception` and
drops the job rather than silently swallowing — not suppression, and reviewed as such by Security
(`plans/brain-layer/security-review.md`, `job.py`/thread-safety row).

## Scope & Correctness

- Implementation matches `plans/brain-layer/plan.md` Stage 1: `StubDecider`, `POST /escalate`,
  `GET /replies/poll`, non-blocking handoff, stand-by-after-timeout, staleness revalidation,
  newest-wins at the job-slot level. Confirmed by reading `brain-layer/src/{server,job,decider}.py`
  and `plans/brain-layer/implementation.md` against the plan.
- Reviewer (`review.md`): **APPROVED, no required fixes**, all six focus areas checked out.
- No unplanned scope added: the two Stage 2 prerequisites and D10's absent validator are recorded,
  not built — correctly out of scope for Stage 1.
- `awaiting_reply_to`'s newest-wins exception is honestly left unimplemented (deferred to Stage 3,
  documented in `plan.md`), consistent with "no unplanned scope."
- No CLAUDE.md invariants violated: DCS stays authoritative (nothing in `situational_header`
  carries ground truth — independently re-traced by Security), no in-process cross-subproject
  import introduced (`brain-layer` and `body-layer` talk over HTTP only; Security grepped both
  trees and found none), no DCS installation write, single-player scope respected.
- All new files staged/committed on the branch (see file list in the SubagentHandback report);
  nothing left uncommitted on `feature/brain-layer` itself.

## Testing

- Core logic covered: `test_decider.py`, `test_job.py`, `test_server.py` (brain-layer, 20 tests,
  including the async round-trip, staleness, and generation-superseded cases); `test_brain_client.py`
  (211 new lines, body-layer's poll/parse path); `test_crew_console.py` (328 new lines — stand-by
  timing, drain_brain, pick/confirm/ask handling); `test_speech.py` (unable/stand-by rendering);
  `test_escalation.py` (payload shape).
- Tests are meaningful, not decorative: verified by reading `test_server.py`'s async-handoff and
  superseded-generation cases and `test_crew_console.py`'s stand-by-boundary case directly; these
  assert on behavior (timing, discarded replies), not just "does not raise."
- No existing tests broken: full body-layer suite (1220/4) and brain-layer suite (20) both green
  against the branch tip, matching each role's own prior reported counts.
- Additionally verified live, this session, against a running `python -m brain_layer` process
  (see Live spot-check below) — this repeats what the plan's own `live_cross_process_check.py`
  already established, as a sanity check before writing the acceptance card, not as new evidence.

## Live spot-check (mechanical, not acceptance)

Started `PYTHONPATH=src .venv/bin/python -m brain_layer --port 7797 --stub-delay-s 0` from the
archived tree; confirmed via `urllib` (curl is blocked in this sandbox):
- `GET /health` → `{"ok": true}`
- `POST /escalate` with a minimal payload → `{"ok": true}`
- `GET /replies/poll?after=0` → `[{"kind": "unable", "reason": "NO_SUCH_COMMAND", "utterance_id": "u1", "t_sim": 1.0}]`

This confirms the module name, `PYTHONPATH=src` convention, and the flags `run-brain.sh` uses are
correct and actually produce a working server — not re-derived from reading the code alone.

## Documentation

- Reviewer findings: none required, none outstanding.
- Non-obvious behavior: extensively documented via module docstrings (`escalation.py`, `job.py`,
  `server.py`, `decider.py`) and `body-layer/CLAUDE.md`, rather than a separate `NOTES.md` note —
  consistent with this project's convention of documenting in code/CLAUDE.md where the explanation
  is local to the mechanism.

## Security

- `security-plan-review.md`: **absent.** Consistent with the project's default exemption for the
  Security role at this phase (`CLAUDE.md` "Agents": "Skip performance-reviewer and security for
  now... Only run either when the user explicitly asked"). This feature explicitly invoked Security
  once, for deep analysis after Reviewer — not at the plan stage — which matches both the upstream
  summary and what exists on the branch. Not treated as a DoD failure: the generic criterion
  assumes both passes are the project's default sequence, which this project has deliberately
  narrowed.
- `security-review.md`: **exists, APPROVED**, one recommended (non-blocking) fix — the
  `run-brain.sh` `--host 0.0.0.0` override, which exposed `POST /escalate` to the LAN with no
  compounding gap actually being exploited today. Confirmed fixed: `1f0dd63` removes the `--host`
  flag; `9e135a7` (after the security review, on user direction) rewords the comment so loopback
  reads as the correct *default for this deployment*, not a hardcoded property of the service —
  both changes verified directly by reading the commits on the branch.

## Verdict

**DoD: PASSED** on all mechanical and paper-trail criteria. Live acceptance is outstanding, listed
as debt (below and in `body-layer/ROADMAP.md`'s "Live acceptance debt" list), not counted as
passed — see the Acceptance Testing Plan in the handback report and
`docs/acceptance/2026-09-25-brain-layer-stage1-sortie.md`.

## Acceptance boundary — what fixtures structurally cannot reach

`StubDecider` produces a canned structural reply from plain code; no fixture in this branch, and
no amount of adding more, exercises whether a real model's output is sane, whether the wire format
survives contact with actual model text, or whether the crew loop *feels* right with a real voice
answering. Two specific gaps a fixture pass cannot catch, named because this workstream's own
history has a worked example (the F10 vocabulary's `Scan`-drove-the-9K113-sight defect and the
raw-task-id-spoken-aloud defect, both invisible to fixtures and only findable by a human hearing
the cockpit): whether "stand by" lands at a moment that actually feels right mid-utterance, and
whether hearing Petrovich answer *at all*, after silence, changes how the exchange reads — neither
is a thing code can assert on.

---

# DoD Check: brain-layer BR-1 Stage 2 (`OllamaDecider`)

Branch `feature/brain-layer-stage2` @ `39bb752` ("Enforce the two vocabulary constants instead of
asking them to agree"). Worktree was stale at launch (`6b8a86e`, an earlier "Status" commit) —
recreated on branch `worktree-agent-a83e2fcbf661244a8-dod` from `feature/brain-layer-stage2`'s own
tip before starting. All checks below were run directly, this session, from that checkout — none
taken from a prior agent's report.

## Scope

Commits `6b8a86e`..`39bb752`. `OllamaDecider` (real local model behind the `Decider` protocol),
the two prompts (classify/discriminate), the body-side D10 validator, the two non-blocking
prerequisites the performance review required before Stage 2 could run a real model, and the
folding-in of a duplicate implementation branch (`feature/br1-stage2`). This gate covers everything
since Stage 1's own DoD pass (`plans/brain-layer/dod-check.md`'s first section, above).

## Code Quality

Built both subprojects' venvs fresh in this worktree (none existed — `.venv` is gitignored) and ran
every command from each subproject's own `CLAUDE.md` "Commands" section, verbatim:

| Subproject | format | lint | mypy --strict | pytest | Result |
|---|---|---|---|---|---|
| brain-layer | `12 files already formatted` | `All checks passed!` | `Success: no issues found in 7 source files` | `45 passed in 6.48s` | PASS — matches Reviewer/Implementer's claimed 45 |
| body-layer | `111 files already formatted` | `All checks passed!` | `Success: no issues found in 52 source files` (only after `cd body-layer && mypy src` — running `mypy body-layer/src` from the repo root fails on the world-model seam import, exactly as `body-layer/CLAUDE.md`'s own CWD-discovery note warns) | `1292 passed, 4 xfailed in 16.36s` | PASS — matches expected 1292/4 |

No `TODO`/`FIXME`/`XXX` in any `.py` file touched by this range. Grepped every non-test source file
this range touched (`brain_client.py`, `brain_reply.py`, `crew_console.py`, `__main__.py`,
`decider.py`, `ollama_client.py`, `prompts.py`, `server.py`) for `print(`, bare/broad `except`, and
suppression markers: the only hits are `crew_console.py`'s pre-existing `_print`/console-output
methods and `except Exception:` guards, none of which sit inside a hunk this range actually
changed (confirmed with `git diff <range> -- crew_console.py`, hunk-by-hunk), and `server.py`'s
`_run_job`, which is the documented crash boundary around `Decider.decide` (logs via
`logger.exception`/`logger.warning`, then drops the job — not suppression, and independently traced
by both Reviewer and Security this stage, `security-review.md`'s `_run_job` row). No new debug
output.

**One doc-only fix made directly in this pass**: `brain-layer/CLAUDE.md` claimed `--decider`'s
default is `ollama` — it is, and always has been on this branch, `stub` (`__main__.py`'s own
docstring: "**still the default** — preserving `run-scripts/run-brain.sh`'s existing meaning
unchanged"). Confirmed against the running `--help` output before fixing the doc, not just the
source. Pure prose, no behavior change, no re-test needed.

## Scope & Correctness

- Implementation matches `plans/brain-layer/plan.md` Stage 2 and its two named prerequisites
  (`OllamaDecider`, classify/discriminate prompts, D10 validator, `poll_replies()` off the shared
  poll thread, `Decider.decide()`'s own bounded timeout) — confirmed by reading
  `brain-layer/src/{decider,ollama_client,prompts,server}.py` and
  `body-layer/src/belief/brain_reply.py` against the plan and `plans/brain-layer/implementation.md`.
- Reviewer: **APPROVED** (Stage 2 proper), **APPROVED** (the fold), **APPROVED WITH MINOR FIXES**
  (the Security/Performance change-request fold) — the one required fix (the
  `OFFERED_CONFIRM_VOCABULARY` docstring's one-directional-safety overclaim) is addressed in
  `39bb752`, and taken further than asked: the reviewer's own *optional* refinement (an AST-based
  sync test between the two mirrored vocabulary constants, `brain-layer/tests/test_prompts.py`)
  was implemented rather than deferred. Confirmed by reading the diff directly (see Code Quality
  above) — not re-stated from the commit message.
- No unplanned scope added: Stage 3's answer leg (`awaiting_reply_id`/`awaiting_reply_to`) is not
  touched anywhere in this range — confirmed `git diff 6b8a86e..39bb752 --stat` has no hits on
  `escalation.py`, `tool_api.py`, or `perception/`.
- No CLAUDE.md invariants violated: no in-process cross-subproject import introduced (grepped both
  `brain-layer/src` and `body-layer/src` for cross-imports — none; the two vocabulary constants are
  duplicated, not shared, and the new sync test parses body-layer's source as text specifically to
  avoid the import module independence forbids); DCS stays authoritative (prompts carry only
  `transcript` and belief-derived candidate `why` text, never `situational_header` — Security's own
  trace, `security-review.md`); no DCS installation write; single-player scope respected.
- **All new/modified files staged and committed**: `git status --porcelain` on the branch tip is
  clean.

## Testing

- Core logic covered: `brain-layer/tests/{test_decider,test_ollama_client,test_prompts,test_server}.py`
  (45 tests total, including `_unquote`'s matched/unbalanced/mid-string cases, the classify/
  discriminate parse paths, and the wedge/timeout prerequisites); `body-layer/tests/test_brain_reply.py`
  (D10 validator — pick/confirm/ask/unable, the composition regression
  `test_pick_because_survives_the_exact_quoting_a_real_model_produces`, and the three
  `OFFERED_CONFIRM_VOCABULARY` tests from the security fold).
- Tests are meaningful, not decorative: re-ran the three named regression/invariant tests
  individually — `test_poll_replies_tick_rate_unaffected_by_a_wedged_server` and
  `test_drain_brain_tick_rate_unaffected_by_a_wedged_brain` (both against real wedged raw sockets,
  not mocks) and `test_wrong_pick_because_tank_degrades_to_ask` — all pass, and read as asserting
  actual behavior (timing bounds, specific degrade outcomes), not "does not raise."
- No existing tests broken: full suites green at counts matching every prior role's claim (above).
- Additionally exercised live, this session, against a real running `brain_layer` process with
  `--decider stub` (the only decider reachable — the sandbox denies `127.0.0.1:11434`, see below):
  started the server on the documented port/module invocation, confirmed
  `brain-layer ready (decider=StubDecider)`, then ran `brain-layer/tools/live_stage2_decider_check.py`
  against it end to end — all five scenarios completed, including scenario 5's four-utterance
  overlapping-fire case (4/4 answered against the stub). This proves the tool's wire mechanics,
  port, module path, and CLI invocation are correct and actually run — it does **not** prove
  anything about a real model's output, since `StubDecider` was behind it, not `OllamaDecider`.

## Documentation

- Reviewer findings: the one required fix from the Security/Performance fold review is addressed
  (`39bb752`, confirmed above); no other findings outstanding across any of the four review passes
  on this branch.
- Non-obvious behavior: extensively documented via module docstrings
  (`server.py`'s `_run_job`/`DEFAULT_DECIDE_TIMEOUT_S`, `brain_reply.py`'s vocabulary-drift-safety
  note, `prompts.py`'s classify-vocabulary note, `__main__.py`'s decider-default rationale) rather
  than a separate `NOTES.md` note, consistent with this project's convention.
- **The two-implementation episode is recorded where a future reader will find it**:
  `plans/brain-layer/implementation.md`'s "Folding in the duplicate branch" section states which
  branch stayed base and why (the structural fix over the shorter-timeout one, verified against
  real wedged sockets rather than judged on code volume), an item-by-item account of what was
  ported from `feature/br1-stage2` (the BECAUSE-unquoting fix, the composition test neither branch
  had, `live_stage2_decider_check.py`, `test_prompts.py`) and what was deliberately not (the
  timeout-only prerequisite fix, the from-scratch `ollama_client.py`/`__main__.py`), and post-fold
  verification numbers. Confirmed nothing was lost: the one required-fix-shaped item from the older
  branch (the BECAUSE-quote handling) was ported and its two encoding-the-defect tests fixed in
  place rather than left passing against wrong output — read directly, not taken on the
  implementation log's word. `feature/br1-stage2` itself still exists locally
  (`git branch -a` — not yet deleted); retiring it is a housekeeping step for whoever merges this
  branch, not a DoD blocker on its own.

## Security

- `security-review.md`'s Stage 2 pass: **APPROVED**. One finding **RECOMMENDED and taken**
  (the `_validate_confirm` offered-vocabulary asymmetry, closed in `d51a25b`/`39bb752`); one
  finding **RECOMMENDED and explicitly deferred** (no byte cap on `response.read()` in
  `ollama_client.py`/`brain_client.py`, reachable only if `--ollama-url` is misconfigured to point
  at a non-Ollama service — user's own call to leave open, consistent with this project's stated
  threat model of trusted local infrastructure). Neither blocks DoD; both are named here so the
  deferred one stays visible rather than silently dropped.

## Performance

- `performance-review.md`'s Stage 2 pass: **APPROVED — MONITOR**. Both Stage 1 prerequisites
  measured as discharged (wedged poll 5015 ms → 0.088 ms; wedged decide bounded ~5003 ms, threads
  return to baseline). The MONITOR item — Ollama serializes generation, so one slow reply can
  chain-drop several *subsequent*, unrelated utterances, not just its own — is **reasoned from
  transport measurements plus D6's 32.7 s worst-case generation figure, not measured live**: no
  sandbox here has ever run a real Ollama daemon. `live_stage2_decider_check.py`'s scenario 5 is
  the instrument built to surface it; the acceptance card's test 4 is the live equivalent. This is
  a fact the user should have before flying, not just before merging — carried into the card.

## Judgement calls requested in this task's brief

1. **Is this feature honestly done given that nothing in it has ever talked to a real model?**
   Yes, with the acceptance boundary stated plainly rather than absorbed into the merge. Every
   mechanical property this stage can prove without a real model — the non-blocking invariant, the
   D10 trust boundary, the two timeout prerequisites, the vocabulary-sync enforcement, module
   independence, no-omniscience — has been proven, independently, by Reviewer, Security, and this
   pass, against real code paths (wedged raw sockets, not mocks; a real running server for the
   tool-wiring check). What none of that proves, and what no amount of additional fixture work
   *could* prove, is whether `qwen3:4b-instruct-2507-q4_K_M`'s actual output — its phrasing, its
   quoting habits beyond what `_unquote` was built against, whether it degrades to `ASK` as often
   in practice as the design assumes — survives contact with the validator and sounds right in the
   cockpit. That is exactly the class of gap the F10-vocabulary precedent (`Scan` driving the wrong
   sight, a raw task id spoken aloud) says a fixture pass cannot catch. Naming it is this gate's
   job; closing it is the sortie's.
2. **Did the fold lose anything, and is the episode recorded?** No loss found (see Documentation,
   above) — the one thing the older branch had that this one needed, the BECAUSE-unquoting fix
   including its second, unstated-but-same-class fix (the prompt terseness sentence), was ported
   and its regression coverage (including the composition test neither branch alone would have
   caught) added. Recorded in `plans/brain-layer/implementation.md`, in enough detail that a future
   reader does not need archaeology.
3. **The chain-drop MONITOR — does the user need to know before flying?** Yes, and it is in the
   acceptance card's own "Not judgeable" section and as its own numbered test (test 4), not buried
   in a plan file.

## Live spot-check (mechanical, not acceptance)

`PYTHONPATH=src .venv/bin/python -m brain_layer --host 127.0.0.1 --port 7796 --decider stub
--stub-delay-s 0`, then `brain-layer/tools/live_stage2_decider_check.py` against it — all five
scenarios ran and reported sane output (see Testing, above). Also ran `python -m brain_layer
--help` directly and confirmed every flag named in the acceptance card (`--decider`,
`--brain-model`, `--ollama-url`, `--decide-timeout-s`) exists with the documented default. Neither
of these reaches a real Ollama daemon — the sandbox denies `127.0.0.1:11434` to every agent on this
project, confirmed again this session (`which ollama`/`curl` to that port both denied by the
sandbox's own permission system before the command could even run).

## Verdict

**DoD: PASSED.** Live acceptance against a real model is outstanding — by design, not oversight —
and is the entire content of `docs/acceptance/2026-09-25-brain-layer-stage2-sortie.md`
(published as an artifact card: https://claude.ai/artifact/VPYm5D44Z98kuEk3ErwbD1). Recorded as
live-acceptance debt in `body-layer/ROADMAP.md`'s "Live acceptance debt" list and in the root
`ROADMAP.md` Brain Layer row, per this branch's own Stage 1 precedent (merged unflown, debt
tracked) rather than blocking the merge on a sortie only the user can fly.

## Acceptance boundary — what this stage's fixtures structurally cannot reach

Everything Stage 1's own boundary note said still holds, plus one addition specific to Stage 2: no
fixture built in-sandbox can exercise a real model's own language habits — its quoting style beyond
the one pattern `_unquote` was written against, how often it actually produces a clean `PICK
<id> BECAUSE <words>` versus wandering off the closed vocabulary, or whether its `ASK` questions
name a real distinguishing feature versus a plausible-sounding invented one. The validator is
designed to fail safe against exactly this uncertainty (bounded to "ask instead of guess," never
silent misdispatch) — but "fails safe" and "sounds right to the pilot" are different properties,
and only the second is what the sortie is for.
