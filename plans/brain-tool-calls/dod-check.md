# Definition of Done — BR-2 brain tool calls (Stages 0–3 batch)

**Scope of this check: Stages 0–3 only.** Stages 4 (landmark `where`), 5 (`say`, gated on flight),
6 (`remember_location` + `[[BL-B79]]`'s live path) and 7 (fly and tune) are **not** in this batch.
BR-2 stays open after this merge; see `brain-layer/ROADMAP/BR-2.md`.

**Verdict scoped to this tip.** Ran against `feature/brain-tool-calls` tip
**`f5c7a633c4bd4251cb0ef4222ad612b946784b32`**, matching the dispatch's expected sha exactly —
confirmed before any other action (`git rev-parse HEAD` after fast-forward). This verdict is a
statement about this one commit; if the branch moves before merge, re-check.

## Branch verification

```
$ git rev-parse HEAD                         # before merge
415fa1358afb4e2f0f3330d7d1b27cb17ef9baa1     # strict ancestor of the feature tip
$ git merge-base --is-ancestor HEAD feature/brain-tool-calls && echo ok
ok
$ git merge --ff-only f5c7a633c4bd4251cb0ef4222ad612b946784b32
Fast-forward, 53 files changed
$ git rev-parse HEAD                         # after
f5c7a633c4bd4251cb0ef4222ad612b946784b32
```
Tree was clean before and after. 53 files, 10,740 insertions, 304 deletions.

## Inputs read in full

`plans/brain-tool-calls/plan.md`, `alignment.md`, `explore-notes.md`, `implementation.md`
(Stage 0/1/2/3 + Review fix + Security fixes + Performance fix sections), `review.md` (NEEDS
REVISION → re-review APPROVED → security/performance fix re-review APPROVED), `security-review.md`
(APPROVED, two findings, both fixed), `performance-review.md` (NEEDS MITIGATION, fixed),
`brain-layer/research/2026-11-12-tool-call-form.md`, `brain-layer/ROADMAP/BR-2.md`,
`brain-layer/ROADMAP/BR-B2.md`, `brain-layer/ROADMAP/BR-B3.md`.

## Checks (all three subprojects, fresh in this worktree)

| subproject | format | lint | mypy --strict | pytest | notes |
|---|---|---|---|---|---|
| audio-adapter | pass (31 files formatted) | pass | pass (16 files) | **391 passed, 2 skipped** | matches review's own figure |
| body-layer | pass (202 files formatted) | pass | pass (82 files) | **3274 passed, 4 xfailed** | matches the security/performance re-review's figure exactly |
| brain-layer | pass (17 files, `src`/`tests` only) | pass | pass (9 files) | **96 passed** | `ruff format` over `tools/` additionally reformats the pre-existing, untouched `tools/live_cross_process_check.py` — confirmed via `git diff` it is not part of this branch's diff, per the dispatch's own note; ignored |

`.venv` symlinked into this worktree per the dispatch (`<subproject>/.venv` → the main checkout's
own venv); never staged (they show `??` in `git status` and stay that way).

`.claude/scripts/commit-quality-gate.sh`: not separately invoked as a standalone check — it is a
`PreToolUse` hook on `git commit` and fires automatically at this DoD's own commit below, on
exactly the staged diff (docs/roadmap/notes only, no subproject source changed in this DoD pass).

`invariant-check` skill, scoped to this batch's touched files across all three subprojects: **all
9 checks PASS or pre-existing WARN**, no FAIL. The three new `# type: ignore[arg-type]` sites this
batch adds (`body-layer/src/belief/tool_api.py:437,441,608`) are the ones `review.md`'s "Optional
Refinements" already named and left as acceptable (adapters passing already-validated `str | None`
through to a stricter `Literal`-typed parameter). No omniscience violation, no unsanctioned
cross-subproject import, no `sys.path` manipulation, no `BINOCULAR_RANGE_MULTIPLIER` return, no
stray `print()`, no bare `except:`, no TODO/FIXME introduced.

## Feature implemented as planned

Each plan Stage, where it landed:

- **Stage 0 (probe).** `brain-layer/tools/stage0_tool_call_probe.py` + `stage0_cases.json` (15
  cases) + `brain-layer/research/2026-11-12-tool-call-form.md`. Verdict, run on the user's own Mac
  against live Ollama (agent sandboxes have no route to it, per BR-1.2): native `/api/chat` `tools`
  over the closed grammar (13/15 vs 8/15 once two prompt defects were fixed), `num_ctx=2048`,
  `BRAIN_MAX_TOOL_ROUNDS=4`.
- **Stage 1 (wake routing, honest edges).** `addressed` added to the wire (audio-adapter,
  additive); `BrainTurn` fold replacing `_pending_escalations`/`_stand_by_spoken_for`; `NO_BRAIN`
  on `available()` false; turn-budget expiry speaking `NO_ANSWER` once instead of discarding
  silently; U1's deterministic unaddressed-fallthrough degrade (no model call).
- **Stage 2 (tool loop, query tools, template answers).** `BRAIN_TOOLS` (seven adapters over
  `tools.find_contact`/`get_contacts`/`describe_contact`/`get_contact_history_with_memory`/
  `find_place`/`describe_our_position`/`mission_memory_tools.recall_memory`); `ToolContext`/
  `ParamSpec`/`ToolObservation`; D3 validation (`validate_tool_call`/`validate_turn_final`);
  `ToolLoopDecider` in brain-layer; the four D7 answer forms (`our_position`, `memory`, `contacts`,
  `nothing_seen`); D6's one-tool-execution-per-poll cap.
- **Stage 3 (commands).** `BRAIN_COMMANDS` (30 tokens, verified token-by-token against the real
  `handle_command` dispatch table — not copied from the plan's illustrative prose, which undercounted
  two token families); target dispatch through the real `handle_command` via a planted
  `[[BL-B102]]` `Mention` (E3, confirmed by a direct differential test, both `takes_target` shapes);
  header refs (D4); the R1 one-shot-signal fix (`where_is_it_requested`/`where_is_it_slots` no
  longer reset unconditionally by `handle_command`).

**Deliberate departures from the plan's prose, all logged and all correct calls:**
- **D5 token families corrected to real tokens.** The plan's D5 table wrote `report_clock_1..12`
  and `report_bearing_north/south/east/west`; the real dispatch table is 9 forward-only clock hours
  (no 5/6/7, the no-omniscience exclusion already applied to scan) and the full 8-point compass.
  Caught by checking the real table rather than copying the plan's prose; no token was dropped,
  the correction only widened two families to their real membership.
- **R1 narrowed.** The plan's own suggested fix ("at most one command dispatch per poll") was
  narrower than needed in the end: only `where_is_it`'s one-shot signal shape collides, since every
  other allowlisted command's readback is synchronous and the only other one-shot-signal tokens
  (`engage`/`disengage`/`observ_on`/`observ_off`/`weapons_armed`/`weapons_safe`) are excluded from
  `BRAIN_COMMANDS` by U2. Verified red-then-green against the real loop, not the plan's line
  numbers.
- **`command` finals degrade to `CANNOT_ANSWER` pre-Stage-3, not `FIXED_COMMAND_ONLY`.** Stage 2
  had no `BRAIN_COMMANDS` yet, so a command final was structurally excluded rather than
  policy-excluded — a different fact from U2's own degrade, correctly kept distinct.
- **Header refs via `[[BL-B102]]` referent memory**, exactly as D4 specified: `_header_contact_refs`
  resolves `_referent_memory`'s window to plain-text `describe_contact` summaries, capped, no x/z.
- **A4/A1 fixture expectations updated for the evidence rule**, not the rule weakened for the
  fixture. The one required Reviewer fix (below) meant `A4_which_ones_the_bmp`'s fixture needed a
  `"because": "BMP"` field it did not originally carry — added to the fixture, not exempted from
  the rule. `A1_where_two_shilkas_discriminated` remains a documented, reasoned gap
  (`_EXPECTED_COMMAND_NEEDS_EVIDENCE_GAP`): its fixture names a direct `command` with no `because`
  at all, and D3's rule — implemented exactly as specified — correctly degrades that to "which
  one?" rather than trusting an ungrounded pick.

**No unplanned scope added silently.** Every departure above is named, in implementation.md, as
the reviewer asked, and traced to a real discrepancy between the plan's illustrative prose and the
real code — never the other direction.

## All checks pass; core logic tested, no regressions

See the Checks table above. No existing test was broken; several were deliberately rewritten where
the plan's own `BrainTurn` fold and U1's supersession of the old implicit escalation route made
the old assertions test dead behaviour (Stage 1's own log names each one).

## Reviewer required fixes addressed

One required fix, one round: the header-seeded, ≥2-candidate ambiguity-evidence gap
(`_start_brain_turn` was offering header refs to `turn.offered` but never to `turn.candidate_sets`,
so a model naming one of several header-offered contacts skipped D3's evidence check entirely —
not merely leniently). Fixed by pushing a ≥2-member header into `candidate_sets`. Re-review
**APPROVED**, independently reproduced red-then-green by the Reviewer itself (not taken on the
implementer's word), and `A4_which_ones_the_bmp`'s fixture correctly updated to carry the evidence
the fix now requires rather than exempted from it.

## Security and Performance change requests addressed and reviewed

Both re-entered the Implementer → Reviewer loop per root `CLAUDE.md`'s change-request rule, and
both were reviewed as ordinary new code (five commits, `a31be8c2..1b13975f`) — **APPROVED**, no
further findings.

- **Security (deep analysis) — APPROVED, two findings, both fixed (option C) rather than
  deferred.** (1) U4 ("fold `[[BR-B2]]`/`[[BR-B3]]` into Stage 2") was accepted by the user and
  Stage 0's own implementation log correctly named Stage 2 as where it would land, but Stage 2's
  own log made no mention of it and a full NEEDS-REVISION review round passed without raising it —
  caught only by Security reading the two call sites directly. Fixed on this branch:
  `server.py`'s `_read_body` guard (ported from `audio-adapter`'s own shape, plus a declared-length
  cap) and `ollama_client.py`'s `_post_json` byte cap, shared by `generate()`/`generate_with_usage()`
  /`chat()`. Both backlog entries now `#status/done` with a resolution naming this branch. **This
  is now a recorded recurring category** — see "Recurring-fix pattern" below. (2) a Recommended,
  non-blocking finding (nothing wrapped `run_brain_tool`'s dispatch in `drain_brain`, inconsistent
  with every other poll-loop input source) — also fixed, not merely accepted as risk.
- **Performance — NEEDS MITIGATION, one required fix, applied.** `find_contact`/`get_contacts`'s
  two brain-tool adapters were enriching every admitted contact before the 5-item display cap
  discarded the work past the first five — 8–18 s mean, up to a measured 30–66 s tail, at a
  realistic 132–142-contact scene. Fixed: cap applied before enrichment, not after, scoped to the
  two adapters only; every other caller (`report_all`, the phrasebook loops) is unaffected by
  construction (`limit=None` default preserves exact prior behaviour, confirmed by dedicated
  call-count and ordering tests). The sibling `crew-query-path` finding stays MONITOR + Architect
  escalation, unentangled with this narrower fix.

## U4 built, verified in code

Per the dispatch's own instruction to verify in code, not the log:

```
$ grep -n "_read_body\|MAX_ESCALATE_BODY_BYTES" brain-layer/src/server.py
173:    def _read_body(self, max_bytes: int) -> bytes | None:
...
...:MAX_ESCALATE_BODY_BYTES = 262_144
$ grep -n "MAX_OLLAMA_RESPONSE_BYTES" brain-layer/src/ollama_client.py
...:MAX_OLLAMA_RESPONSE_BYTES = 1_048_576
...:        raw = response.read(MAX_OLLAMA_RESPONSE_BYTES + 1)
...:        if len(raw) > MAX_OLLAMA_RESPONSE_BYTES:
...:            raise OllamaRequestError(...)
```

Both present in the real source (confirmed by reading, not grepping a log entry), both covered by
dedicated tests (`test_escalate_*_content_length_*`, `test_*_raises_when_response_exceeds_byte_cap`)
that pass in this worktree's own fresh run above.

## Scope & correctness

- **No invariants from CLAUDE.md violated** — confirmed by the `invariant-check` run above and by
  Security's own end-to-end trust-boundary trace: the model can never supply a coordinate,
  `now_sim`, an unoffered ref, a tool outside `BRAIN_TOOLS`, or a command outside `BRAIN_COMMANDS`.
  `remember_location`/`[[BL-B79]]` confirmed still unreachable (not registered in `BRAIN_TOOLS`).
  No-omniscience holds through the new prompt builder (`recent_contacts` never carries a
  coordinate).
- **All new files staged with `git add`** — see Commit section below; `git status --porcelain`
  after commit is clean except the three `.venv` symlinks, which are correctly never staged.

## Documentation

- **Reviewer findings addressed** — see above.
- **Non-obvious behaviour explained**: `implementation.md`'s Notable Discoveries sections cover
  the D5 token-family correction, the R1 narrowing, the header-ref/candidate_sets fix, and the two
  fixture/implementation discrepancies the acceptance bench found and recorded rather than hid.
  `brain-layer/research/2026-11-12-tool-call-form.md` is the Stage 0 measurement record.

## Security sign-off

- `plans/brain-tool-calls/security-review.md` — **APPROVED** (deep analysis; two findings, both
  fixed; see above). No separate plan review was expected for this stage of work per
  `[[project_change_request_fix_no_security_plan_review_expected]]`-shaped reasoning — this batch's
  own security plan review ran at the original Architect stage, before Stages 0–3 existed as code;
  the deep analysis above is the correct, final gate.

## Acceptance boundary — stated up front

**What this feature's fixtures structurally cannot reach:**
- **Whether the model's tool-calling judgement holds up on a real, messy sortie scene** rather
  than Stage 0's 15 clean canned cases. The fixtures prove the *validator* rejects every invalid
  shape correctly; they cannot prove the *model* reaches for the right tool on an utterance nobody
  wrote a case for.
- **Whether 2–6 s of model time per answer feels acceptable in the cockpit**, as opposed to
  acceptable on paper against A4's stated envelope. Fixtures have no pilot's sense of "too slow."
- **Whether the brain seam itself is reliable under a real Ollama process on the user's own Mac
  during a live mission** — nothing in this batch, including Stage 0's own probe, has driven it
  through body-layer's escalate/poll wire end to end; Stage 0 measured the model directly, and
  BR-1 itself has never flown. A fixture pass proves the wire's *shape* is correct; it cannot prove
  the wire works under real network/process conditions for the first time.
- **Whether the E3 differential test's two representative tokens (`mark_target`, `cancel_task`)
  generalise to the other 28** — argued structurally (every token shares one dispatch shape), not
  verified by exhaustive test, per the Reviewer's own non-blocking note.

This is why the batch ships `#needs-flight` rather than done, and why Stage 7 exists.

## Accepted debt — unblock condition executed, where one exists

No outstanding accepted debt carries an executable unblock condition this DoD pass could run: U4's
own debt (`[[BR-B2]]`/`[[BR-B3]]`) was fixed on this branch rather than left deferred (see above),
and the live-acceptance debt's only clearing condition is an actual sortie, which this role cannot
perform. That is PENDING (live), not a wish with a command behind it.

## Notes harvest

Four candidates added, none duplicating an existing entry (checked via `/notes-harvest` and by
reading the relevant topic files directly):

- `notes/planning-and-process-lessons.md`: **"a log claiming scope is not evidence it was
  built"** (the U4 case — Stage 0 correctly deferred, Stage 2 silently never landed it, caught only
  by Security reading the real call sites).
- `notes/planning-and-process-lessons.md`: **"an evidence exemption keyed on source widens when
  the source grows cardinality"** (the header-ref ambiguity-evidence gap — the pronoun-trust
  analogy held for one candidate, not two or more).
- `notes/planning-and-process-lessons.md`: **"enrich after cap, not before"** (the performance
  fix — capping for display after enriching every admitted item pays the cost on everything
  discarded, not just what's shown).
- `notes/model-selection-and-local-llm-serving-brain-layer-br-1.md`: **"Stage 0 prompt defects
  dominate before the form question can be answered"** (run 1's 0/15 on both forms was two prompt
  sentences, not a model-capability result).

## Recurring-fix pattern — process signal

**U4's own failure shape has now recurred.** `.claude/agent-memory/dod/
project_plan_named_doc_step_can_be_dropped_silently.md` (BL-15: a plan's named documentation
deliverable survived three Reviewer-approved passes unbuilt, caught at DoD) and this batch's U4
(a user-accepted, stage-numbered security fold survived Stage 0's own correct deferral note plus
a full NEEDS-REVISION review round unbuilt, caught at Security) are the same mechanism: **an
explicit commitment that names which stage it will land in is trusted by every later pass's own
implementation-log reading, rather than independently diffed against the real code.** Recorded as
a new pattern memory (`project_recurring_accepted_plan_commitment_dropped_silently.md`) rather than
a one-off, since this is the second distinct feature family it has cost.

**This is process debt worth a check earlier in the role sequence, not just at DoD or Security.**
A Reviewer re-reading a plan's own numbered deliverables/decisions list against the real diff —
not just "does the code do what the plan's design says" — would likely have caught U4 at the
Stage 2 review round rather than needing Security's independent code read. Worth considering for
the Reviewer role's own standing checklist.

## Commit

Staged: `plans/brain-tool-calls/dod-check.md` (this file), `brain-layer/ROADMAP/BR-2.md`,
`ROADMAP.md`, `plans/inbound-speech/plan.md`, `plans/crew-query-path/plan.md`,
`notes/planning-and-process-lessons.md`,
`notes/model-selection-and-local-llm-serving-brain-layer-br-1.md`,
`docs/acceptance/2026-11-13-br2-brain-tool-calls-sortie.md`,
`.claude/agent-memory/dod/project_recurring_accepted_plan_commitment_dropped_silently.md`.

## Verdict

**DoD: PASSED** for Stages 0–3. BR-2 itself stays open (`#status/open` on its own entry file,
unchanged). Acceptance testing: **PENDING (live)** — test card published, `#needs-flight` tag
carried on `brain-layer/ROADMAP/BR-2.md`'s own "Stages 0–3 merged" entry. Per the 2026-10-26 user
direction, this does not gate the merge.
