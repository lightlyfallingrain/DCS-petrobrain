# Definition of Done: BL-B119 (effector-says)

**Tip tested:** `d3ca5194afa269fe9df072a0661c7de1add626e9` on `feature/effector-says`
(fast-forwarded into this DoD worktree from `11e40eb4280a6359d6b122843b5854e0a43860e6`, which was
also `main`'s own tip at the time — no stale base). **This verdict is scoped to that sha.** If the
branch moves after this report, re-run before merging.

## Code Quality

Subproject touched, derived from `git diff --name-only 11e40eb4280a6359d6b122843b5854e0a43860e6
HEAD`: **`body-layer/` only** (plus `.claude/agent-memory/`, `plans/effector-says/`,
`body-layer/ROADMAP/` bookkeeping — no other subproject's code).

| Check | Command | Result |
|---|---|---|
| Format | `ruff format --check src tests` (from `body-layer/`) | PASS — 204 files already formatted |
| Lint | `ruff check src tests` (from `body-layer/`) | PASS — all checks passed |
| Type check | `mypy src` (from `body-layer/`, strict) | PASS — no issues in 83 source files |
| Full test suite | `.claude/scripts/fast-tests.sh --full body-layer` (foreground, parallel) | PASS — **3294 passed, 4 xfailed** (147.5s) |

(`body-layer/.venv` did not exist in this worktree; created fresh with Python 3.12 + ruff/mypy/
pytest/pytest-xdist + `pyproj>=3.6`/`numpy>=1.26,<2.5` per `body-layer/pyproject.toml`.)

- **No unhandled errors/panics in data paths.** The engine stays pure (`advance()` never raises on
  a bad `petrovich_says` cell — `_speak_text` guards the empty-string case before any indexing,
  confirmed independently in `security.md`). `AudioAdapterClient.push_speech` still raises
  synchronously on the calling thread exactly as before this feature; `drain_effector_speech`
  introduces no new try/except and no new swallowed exception.
- **No debug output left in committed code.** `git diff` over `body-layer/src` for this feature's
  commit range shows no added `print(`/`pdb`/`breakpoint`; the one `self._print(...)` hit in a
  grep is the pre-existing, intentional speech-output method, not debug output.
- **No leftover debug code or TODO comments introduced by this feature** — grepped the diff for
  `TODO|FIXME|XXX`, no hits.

## Scope & Correctness

- **Implementation matches the plan.** All four plan items are built: (1) the engine reports a
  row's line on completion (written, or already-in-position per Q1) and stays pure, draining
  through `body.py`; (2) cell text is stripped and sentence-cased/punctuated as written; (3) the
  four hard-coded handler returns are removed, keeping their other side effects, and `_handle_
  engage`'s own arming also speaks "weapons armed" through the shared `weapon_safety_transition`
  field (Q2); (4) the out-of-scope list (`"Unable, guidance not ready"`, `"Observ on, wait."`, every
  other non-sequence readback) is confirmed untouched — Reviewer verified by inspection and by the
  passing suite, this DoD pass re-confirmed by grep (`_handle_observ_on`'s refusal branch still
  returns before `observ_transition` is set).
- **No unplanned scope added silently.** Reviewer's own scope-fit check (review.md) found the diff
  touches exactly `effector_sequences.py`, `effector_engine.py`, `crew_console.py`, `body.py`, and
  their tests, plus bookkeeping — confirmed again against the merge-base diff above.
- **No invariants from CLAUDE.md violated.** No-omniscience boundary untouched (this feature is
  entirely on the command/effector side, no `Percept`/ground-truth involved). Module independence
  intact — no new cross-subproject import. No behaviour-affecting constant was added bare (Reviewer
  checked; re-confirmed — `_speak_text`'s punctuation rule and `EffectorRunState.spoken`'s default
  `()` are not tunable-constant-shaped, they're formatting/state, not a dial).
- **Ledger:** `.claude/scripts/accepted-items-ledger.sh plans/effector-says` produced **no output**
  — expected, since this is a small plan with no Architect pass and therefore no `U<n>` ids
  (confirmed by Reviewer and re-run here). The plan's three verbatim pilot decisions (Q1/Q2/Q3) are
  accounted for by hand: all three built, none deferred (see "What is built" below).
- **All new files staged.** `git status --porcelain` was empty after the fast-forward merge and
  stays empty after every file this DoD pass wrote, once staged below.

## Testing

- **Core logic covered.** Engine: row-written → line once; already-in-position → line once;
  empty cell → nothing; failed condition / unknown readback → nothing; failed write → nothing until
  retry succeeds, then once; two triggers in one poll → lines in fire order. Parser: quote
  stripping. Crew console: the four handlers return `[]`, still set their transitions. End-to-end
  in `body.py`'s real poll path with fakes: "weapons armed" spoken exactly once, never twice, even
  across several more polls past completion.
- **Tests are meaningful, not decorative.** Reviewer verified the real wiring **by mutation**
  (disabled the `drain_effector_speech` call in `body.py`, re-ran the one true end-to-end test, it
  failed `0 == 1`, restored) — not just by reading the code.
- **No existing tests broken.** Full suite above: 3294 passed, 4 xfailed, same xfail count as
  the implementer's own fast-set run (2237 passed / 4 xfailed) scaled up by the `slow` tests.
  `test_dispatched_command_tokens_all_return_something` (a project-wide regression guard this
  feature broke in flight, not named in the plan's own Tests section) was fixed correctly, per
  this role's reading of the diff and the implementer's/reviewer's own memory notes on that exact
  guard.

## Documentation

- **Reviewer findings addressed.** `review.md` verdict: APPROVED, Required Fixes: **none**. Two
  Optional Refinements, neither blocking:
  - The same-poll pending-restart double-speak note: **given a tracked home**, filed as
    [[BL-B121]] (`body-layer/ROADMAP/BL-B121.md`, added to `body-layer-backlog.md`'s index). Not
    exploitable today (re-confirmed at DoD: every shipped speaking sequence is single-row, no
    `WaitRow`, every trigger is a one-shot `CrewConsole` field consumed once per poll) — becomes
    live risk only once a multi-row speaking sequence is written, which the entry says explicitly.
  - `_speak_text`'s already-punctuated-cell branch has no dedicated unit test — low risk, pure
    function, mypy-clean, left as stated (not worth a backlog id by itself; noted here for
    visibility).
- **Every accepted plan decision accounted for.** `accepted-items-ledger.sh` gives no `U<n>` lines
  for this plan (no Architect pass). By hand against "Decisions, verbatim": Q1 (speak even when
  already in position) — **built**, R12 self-check-match path speaks. Q2 (attack-run start also
  speaks "weapons armed") — **built**, `_handle_engage` converges on the same
  `weapon_safety_transition` field; end-to-end test covers one command path, this DoD pass's
  acceptance card block 5 covers the engage-triggered path live. Q3 (line arrives on completion, a
  poll later, as confirmation) — **built**, this is the whole mechanism (R12/write-completion
  points, not recognition time).
- **Non-obvious behaviour explained.** Via code structure (engine stays pure, `body.py` drains) and
  docstrings (`crew_console.py`'s four handlers each explain where their line now lives); one
  `notes/` entry added on the fixture-freeze gotcha and one on the regression-guard gotcha (see
  below) — both durable, non-obvious, not already in CLAUDE.md or derivable from a quick code read.

## Security

`plans/effector-says/security.md` exists: **APPROVED**, Required Fixes: none. Traced end-to-end
that only the pilot's own local `config/sequences/mi-24p/*.md` files can feed `petrovich-says`
text; no brain/escalation path reads it back; parser and `_speak_text` both crash-free on every
edge case traced by hand (empty, whitespace, single quote, unmatched quote, very long, non-ASCII,
embedded `|`). One low-risk item (no length cap on the cell) explicitly not filed — outside this
project's stated threat model (the "attacker" would need pre-existing filesystem write access,
already total compromise). Re-read, not just re-cited: concur with that call.

## Performance

`plans/effector-says/perf.md`: **APPROVED**. Every finding is MONITOR — the new `spoken` tuple
allocation is empty-tuple-interned when idle and bounded by (currently single-row) sequence length
when busy; `drain_effector_speech`'s `list(spoken)` conversion is O(1) even in the idle case;
row-completion work only runs on a player-paced event, not per poll; parse-time stripping is
load-time-only, off the poll path entirely.

## Verdict

**PASSED.** No required fixes outstanding from any of Reviewer/Performance/Security. One optional
refinement given a tracked backlog entry ([[BL-B121]]); the other left as a stated low-priority
gap. All mechanical checks pass at the tested tip above.

## Acceptance boundary — what these fixtures structurally cannot reach

Every test here drives `CrewConsole`/`effector_engine`/`body.py` with **fakes**: a fake
`AircraftLayerClient` that reports whatever read-back value the test hands it, and a fake clock.
What that cannot reach:

- **Whether the real DCS switch actually moves when the sequence writes it.** The engine's
  "row completes" signal is driven by a *read-back* of the effector arg, not by DCS physically
  actuating anything — a fixture can assert "the engine believes the switch reached `armed`" but
  cannot prove the cockpit switch model agreed in the same frame, or that the write landed on the
  intended device at all.
- **Timing as heard, not as counted.** The tests assert the line is reported/spoken *once*, in the
  right order, at the right field. They cannot tell whether that one line is audible at the moment
  a human pilot expects it, overlaps another callout, or lands during a radio transmission gap —
  only an ear in the cockpit can judge that, which is exactly what this DoD pass's acceptance card
  asks for.
- **The attack-run convergence (block 5 on the card) under real timing.** The fixture test proves
  the *mechanism* — two callers setting the same field produce one spoken line — but it does not
  drive a real `_handle_engage` call racing a real poll-loop effector run at DCS's own frame rate;
  a genuinely pathological interleaving (e.g. the engage command arriving mid-write) is not
  something any fixture here was built to probe.

This is the worked-example class of gap this role exists to name: a fixture pass proves the engine
does exactly what it says, against exactly the inputs it was given; it says nothing about whether
what it says is what the pilot, in the seat, actually hears.
