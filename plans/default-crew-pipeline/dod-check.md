# DoD Check: BL-B96 (default crew pipeline)

**Scope of this verdict: commit `7149f48a854764db3d5428516706b869e933650a`**, tip of
`feature/default-crew-pipeline` at the time of this check. If the branch moves, this verdict is
stale and must be re-run.

**Worktree address check.** This worktree's own HEAD (`9ebc414907e805c4f0efdd9f44a6ab091170ee4f`,
main's tip) was not an ancestor of the expected tip (`git merge-base --is-ancestor` returned false
either direction) and the tree was clean with no unique commits, so per the dispatching brief this
was the "anything else: report and stop" case restated as "clean tree, no unique commits ->
checkout --detach" — detached directly onto `7149f48a854764db3d5428516706b869e933650a` with
`git checkout --detach`. Confirmed by `git rev-parse HEAD` immediately after. No worktree had the
branch checked out elsewhere, so every command below ran against the exact tip, not an archived
snapshot.

## Mechanical checks (all re-run directly in this worktree, at the tip above)

| subproject | ruff format --check | ruff check | mypy --strict (src) | mypy tools | pytest |
|---|---|---|---|---|---|
| body-layer | pass (173 files) | pass | pass (74 files) | pass (10 files) | 2576 passed, 4 xfailed |
| aircraft-layer | pass (72 files) | pass | pass (25 files) | n/a | 581 passed |
| audio-adapter | pass (31 files) | pass | pass (16 files) | n/a | 349 passed, 2 skipped |

All three subprojects' counts match `review.md`'s re-review table exactly (re-review of
`6c63719d`). No `.venv` exists inside this worktree; every tool above was invoked via the main
checkout's absolute `.venv/bin/<tool>` path, per the dispatching brief.

**Lua syntax** — every `.lua` file under `aircraft-layer/dcs-export/` parses clean:
`find aircraft-layer/dcs-export -name '*.lua' -print0 | xargs -0 -n1 luac5.1 -p` produced no
output (no errors). Confirmed no F10/overlay Hook `.lua`/`.dlg` files remain in that directory at
all (directory listing has 39 files, none named `petrobrain-f10-*`/`petrobrain-overlay-*`).

**Command map / status page:**
- `python3 .claude/scripts/command-map-check.py` -> `command map current (67 tokens)`, exit 0.
- `grep -i f10 docs/status/petrovich-commands.html` -> no output, exit 1 (clean).

**CLI surface** (`body-layer/src/body.py`, run live via
`PYTHONPATH=src:../world-model/src .venv/bin/python -m body --help`):
- No `--console`, `--crew-text`, `--f10-commands`, `--overlay`, `--speech-audio`, or
  `--speech-input` flag exists in the parser output.
- `--audio-adapter-url` is present with no default; confirmed live by running `python -m body`
  with `--aircraft-layer-url`/`--theatre`/`--world-model-db` given and `--audio-adapter-url`
  omitted: `error: --audio-adapter-url is required (omit only together with --print-tuning) --
  BL-B96: speech in/out are always on`.

**Full-repo final sweep** (plan Stage 8), re-run directly rather than taken from
`implementation.md`'s word:
- `grep -rl "python -m logger"` across the repo hits only historical records: `plans/*/debug.md`,
  `plans/*/implementation.md`, `plans/*/review.md`, `plans/*/dod-check.md`,
  `.claude/agent-memory/dod/...`, and `docs/acceptance/*.md` — every one of Stage 8's exempted
  categories, confirmed by reading the hit list, none in live code/docs.
- `grep -rl "import logger\b"` / `"from logger\b"` across `*.py` — zero hits anywhere.
- `grep -rn "logger\.py"` in `body-layer/CLAUDE.md`, `body-layer/RUN.md`,
  `aircraft-layer/CLAUDE.md`, `aircraft-layer/WORKFLOW.md`, `audio-adapter/CLAUDE.md`, and
  `body-layer/run-scripts/*` — zero hits.
- `grep -rn -- "--console|--crew-text|--f10-commands|--speech-audio|--speech-input|--overlay"`
  across `body-layer/src`, `body-layer/tests`, `aircraft-layer/src`, `aircraft-layer/tests`,
  `run-scripts/`, and the four `CLAUDE.md`/`WORKFLOW.md` files above — every hit is a historical
  comment describing the removal (`"BL-B96 removed --console"`, docstrings on the rewritten
  threading test), never a live flag definition, parser call, or branch. No
  `--f10-commands`/`--speech-audio`/`--speech-input`/`--overlay` hit at all, anywhere.
- `grep -rln "overlay|f10|F10"` across `aircraft-layer/src`, `aircraft-layer/tests`,
  `body-layer/src`, `body-layer/tests` — read every hit's context; all are either
  (a) `ConsolePerceptionRunner`/unrelated substring matches, or (b) historical
  port-numbering/provenance comments ("formerly `text_sender.TextOverlaySender`, retired by
  `BL-B96`", "the F10 command channel, retired by `BL-B96`") — none describe a live route, socket,
  or flag.
- `run-scripts/run-crew-text.sh` read directly: `-m body`, no removed flags, `--audio-adapter-url`
  present. `run-scripts/run-console.sh` does not exist (deleted per plan). No `logger` string
  anywhere in `run-scripts/`.
- `aircraft-layer/WORKFLOW.md`: no "Deploy the F10 commands Hook" or "Deploy the overlay Hook"
  section remains (`grep -n "^## Deploy"` lists only the Export.lua and mission-start Hook
  sections). The `autoexec.cfg`/`net.allow_dostring_in` paragraph survives under the mission-start
  Hook's own section (confirmed by reading it directly) — the one hard constraint the plan named.

**Backlog obsolescence notes** — `body-layer/ROADMAP/BL-B7.md`, `BL-B8.md`, `BL-B9.md` each read
directly: all three carry a 2026-10-24 "Obsolete note" citing `BL-B96`, stay `[x]` done, IDs not
reused.

**Debug output / TODOs introduced by this feature:** `git diff 9ebc4149..7149f48a -- '*.py' | grep
-nE '^\+.*(print\(|TODO|FIXME|pdb\.set_trace|breakpoint\(\))'` — one hit, `print(CREW_TEXT_HELP_
TEXT, file=sys.stdout)`, which is the REPL's own intentional `--help`-equivalent text output, not
debug leftover. No unhandled bare `except:`/panics found in the touched diff (the review and
security-perf pass both read `_poll_transcripts`/`CrewConsole._print`'s exception handling
directly and confirmed it degrades, never raises, out of the poll tick).

**Clean tree:** `git status --porcelain` empty at the tip before this check began and remains
empty (no files staged/modified by this DoD run until this report and its commit, below).

## Scope & correctness

- Implementation matches `plans/default-crew-pipeline/plan.md`'s eight stages — confirmed by
  `review.md`'s full read and the re-review of the one required fix, both independently re-run
  above rather than taken on the implementation report's word.
- No unplanned scope found by Reviewer, Security/Performance pass, or this check.
- No invariant from `body-layer/CLAUDE.md` violated: the no-omniscience boundary, the
  `ConsolePerceptionRunner`-stays decision, and the additive-CLI-flag convention for the surviving
  debug flags are all unaffected by this removal (confirmed by reading `CLAUDE.md`'s own current
  "What this is" and "Running the live logger" sections, which already describe the post-BL-B96
  state accurately).
- All new/modified files staged — confirmed via clean `git status --porcelain` at the tip.

## Testing

- `test_mock_flight_chain.py`'s console-threading smoke test was rewritten (not deleted) against
  the crew-text threading model, per the plan's own Decision — confirmed present
  (`test_mock_flight_chain_threaded_crew_text_smoke`) and passing in the full `pytest` run above.
  Reviewer confirmed it also caught and fixed a real pre-existing bug (REPL-thread
  `sqlite3.Connection` affinity) rather than being a weaker stand-in.
- No existing tests broken — full suites green across all three subprojects, matching the review's
  own re-run figures exactly.

## Documentation

- Reviewer's one required fix (command-map F10 badges/caption) — re-reviewed and confirmed
  APPLIED in commit `6c63719d`, re-verified again here (`grep -i f10` on the status page, above).
- Three optional refinements from `review.md` (stale module-name/flag mentions in
  `audio_sender.py`, `watched_args.py`, `voice_repl.py`, and `vocabulary.py`'s tense) — all applied
  per the re-review and confirmed non-behavioural.
- Non-obvious behaviour (warn-and-keep-trying via `ConnectionReporter`, the autoexec.cfg
  relocation, the plain-text-logger deletion as a scope reading) is explained in `plan.md`'s
  Decisions section and `body-layer/CLAUDE.md`'s "Running the live logger" prose — both read
  directly and confirmed current.

## Security

`plans/default-crew-pipeline/security-perf.md` — **APPROVED**, light combined pass (user-waived
full separate passes; authorised because diff shape is a removal, not new risk surface). No
security blocker. One non-blocking performance finding, not filed as debt, left to the user as
options A (ignore) / B (backlog) / C (fix now) / D (stop) — see "Non-blocking finding" below. This
satisfies the DoD checklist's security-review requirement in the form this project currently uses
(`security-plan-review.md` is not a separate artifact for this change — the combined light pass
covers both plan-level and deep-analysis concerns per root `CLAUDE.md`'s once-per-batch cadence).

### Non-blocking finding carried forward, not decided here

The security/perf pass found the audio-adapter poll/push calls share the main perception/belief
poll thread with a 5s default timeout, now exercised unconditionally every poll instead of only
when a user opted in. Probability low on this project's actual same-box/closed-port topology,
medium if ever run cross-machine behind a silent-drop firewall; impact is a degraded tick rate,
self-recovering, never a crash, never silent (`ConnectionReporter` announces the transition). This
is **not accepted debt with an unblock condition to execute** — it is an open choice handed to the
user (A/B/C/D), not yet decided, so there is nothing to run and verify at this gate. If the user
picks (B), a `BL-B` id should be minted for it at that point, not before.

## Acceptance boundary — what this DoD pass structurally cannot reach

This pass verified **static/mechanical correctness**: the flags are gone, the routes are gone, the
file is renamed, the tests pass, the diff sweep found no live straggler. It did **not**, and could
not from fixtures/CLI help text alone, verify:

- That speech actually plays and is actually heard once `audio-adapter` answers (the
  `ConnectionReporter`/`AudioAdapterClient` wiring is proven correct by unit test against a fake,
  never against a real adapter process or real audio hardware).
- That the warn-and-keep-trying banner is legible/non-alarming in a real terminal during an actual
  sortie when `audio-adapter` starts late, as opposed to in a scripted `--help`/`parser.error`
  check.
- That removing the F10 Hook and overlay Hook `.lua` files from a live `Saved Games\DCS\Scripts\`
  tree (not just this repo) leaves no stale DCS-side registration — a copy-deployed file surviving
  on a Windows box independently of this repo's own deletion is exactly the kind of drift
  `aircraft-layer/WORKFLOW.md` warns about generally, and nothing in this run touches that
  Windows-side state.
- That `--audio-adapter-url`'s new required-ness doesn't break a run-script or automation the user
  has outside this repo that previously relied on the flag being optional.

None of this is more testing within reach right now — it needs Windows, a running DCS mission, and
the user's own ears. Listed as `#needs-flight` items below, per root `CLAUDE.md`'s roadmap-entry
convention, rather than gating this merge on them.

## #needs-flight items (for the owning BL-B96 roadmap entry, not gating this merge)

1. Delete the stale F10/overlay Hook `.lua`/`.dlg` files from the Windows box's
   `Saved Games\DCS\Scripts\` tree (this repo's deletion does not reach a copy already deployed
   there).
2. Restart the aircraft-layer collector against the current (F10/overlay-free) `Export.lua`/Hook
   scripts and confirm no stale port binding / no leftover registration in `dcs.log`.
3. Run `body.py` with a real `--audio-adapter-url` against a live sortie: confirm speech out is
   audible, speech in is recognised and dispatched, and the warn-and-keep-trying banner appears
   correctly if `audio-adapter` is started late or not at all, then clears when it answers.
4. Watch for the security/perf pass's non-blocking finding in a real sortie: does the poll/push
   timeout ever visibly stall perception (a conspicuously late contact update) when
   `audio-adapter` is reachable but slow/hung rather than cleanly refused.

These are the main loop's to tag `#needs-flight` on the BL-B96 entry file at merge time, per root
`CLAUDE.md`; this DoD pass does not mark the roadmap entry done or tag it itself (dispatching brief
reserves both to the main loop at merge).

## Milestone-completion question

**Does BL-B96 change what the next milestone (BL-B89, 9K113 scanning re-sequencing) should be, or
invalidate an assumption it relies on?** No. BL-B89 is about re-sequencing the sight's search cycle
(wide S-scans -> narrow visits, pointing-at-a-place) and does not depend on the F10/overlay
transports or the mode-flag surface BL-B96 removed; nothing in BL-B89's own entry
(`body-layer/ROADMAP/BL-B89.md`) references any of them. BL-B96 does change the operating default
(speech always on, no F10) but that is a baseline shift orthogonal to BL-B89's scope, not an
invalidated assumption.

## Verdict

**PASS** — scoped to tip `7149f48a854764db3d5428516706b869e933650a`. All mechanical checks pass,
scope matches plan, Reviewer's required fix is verified applied, Security+Performance light pass
is APPROVED with one non-blocking finding left open to the user, and the clean-tree/staging
requirement holds. Per the user's standing instruction ("When DoD passes, merge"), this gates a
merge to `main` — the main loop performs the merge and the roadmap update, not this DoD run.
