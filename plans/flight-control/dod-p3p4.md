# Definition of Done: BL-16 mode 2 Stages P3+P4 (CBTM align/align-for-launch/break/break-away, recovery)

**Verdict: FAILED.** Verification was run against `feature/bl16-p3p4-cbtm` tip `1fab614c`
(checked out in this worktree as `p3p4-dod`, created from that sha since the feature branch itself
is checked out in a sibling worktree, `/Users/sg/Code/DCS-petrobrain-bl16-p3p4`, per the dispatch
instructions). This verdict is scoped to `1fab614c` only; if the branch moves, re-run.

Reviewer (`review-p3p4.md`, APPROVED after a review-fix round), Performance Reviewer
(`perf-p3p4.md`, APPROVED), and Security (`security-p3p4.md`, APPROVED, filed `[[AC-B22]]`) all
passed this batch on the strength of a **targeted** nine-file test run plus a collect-only smoke
check — neither of which executes the integration tests below. DoD's full suite, run for the first
time on this batch, finds **4 pre-existing tests broken**, which fails the DoD criterion "No
existing tests were broken."

## What failed

Full suite run from this worktree (`/Users/sg/Code/DCS-petrobrain/<subproject>/.venv/bin/pytest`,
cwd inside the worktree's subproject dir, `-n auto`):

- **aircraft-layer**: `961 passed` — clean.
- **body-layer**: `4 failed, 3667 passed, 4 xfailed in 161.12s` (parallel, pytest-xdist).

The 4 failures, all caused by the same root cause plus one related test-double gap:

1. **`tests/test_body.py::test_seat_changes_fire_seat_copilot_then_seat_pilot`**
2. **`tests/test_body.py::test_a_seat_read_across_a_mission_restart_fires_nothing`**
3. **`tests/test_body.py::test_engage_with_no_target_fires_start_then_stop_through_the_poll_loop`**

   Root cause for all three: `belief.ai_pilot_wheel.advance_parked_flight_state` (line ~444) now
   calls `client.get_payload_latest()` **unconditionally, every poll** (this batch's launch-
   detection read) — but `tests/test_body.py`'s own `FakeConsoleAircraftClient` (the hand-
   duplicated test double these three tests drive through the real poll loop,
   `_run_crew_text_poll_loop`) has no `get_payload_latest` method at all. Every poll of the real
   loop raises `AttributeError`, caught by the loop's own top-level `except Exception` ("crew-text
   poll cycle failed; continuing") — so the loop doesn't crash the test process, but
   `advance_parked_flight_state`'s other field updates (including `player_seat`, which these three
   tests assert on) never happen, because the exception fires before any `replace(...)` in that
   function runs. Confirmed by reading `advance_parked_flight_state` directly: the payload read is
   the first line in the function body, ahead of the seat/mode mirroring this batch did not touch.

   **This is the same recurring category this project's own implementer memory already names**
   (`project_emitter_visibility_stage_b_firing.md`, BL-B73/AC-B8, 2026-??): *"a new unconditional
   call site in a shared perception source breaks every `FakeAircraftClient` duplicate in the test
   suite, not just the ones testing the new feature."* That finding was about
   `NakedEyePerceptionSource.poll()`; this is the same shape one layer over, in
   `advance_parked_flight_state`. Both were caught only by a full-suite run, not by a targeted or
   smoke one — see "Recurring-fix pattern" below.

4. **`tests/test_aircraft_client.py::test_write_ai_pilot_goal_posts_to_command_endpoint`**

   `AircraftLayerClient.write_ai_pilot_goal` (body-layer's own HTTP client, `src/aircraft_client.py`)
   gained `cbtm_action`/`cbtm_seq` as two new trailing optional parameters this batch, always
   included in the POSTed payload dict (as `None` when unset). This one pre-existing test calls the
   method with the old 7-positional-argument shape and asserts the exact resulting payload dict —
   which no longer matches, since the payload now always carries the two new keys. Not a production
   defect (the two extra `None` fields are harmless on the wire, same as `hvrt_step`'s own addition
   handled correctly elsewhere) — a test literal that wasn't updated for the new signature.

Neither gap was caught earlier because:
- The Reviewer's/Implementer's targeted nine-file run never included `test_body.py` or
  `test_aircraft_client.py`.
- The whole-suite **smoke** check (`--collect-only`) only confirms every test *imports and
  collects* — it never executes a test body, so an `AttributeError` raised at call time, or a
  stale literal assertion, is invisible to it.
- This is exactly why the full suite is DoD's own job (root `CLAUDE.md`, "Tests") rather than
  something any earlier role is expected to run.

## What passed

- **aircraft-layer**: `ruff format --check` clean (85 files), `ruff check` clean, `mypy src` clean
  (28 files), full suite `961 passed`.
- **body-layer**: `ruff check .` — all checks passed; `ruff format --check .` — 2 files would
  reformat, both pre-existing and untouched by this batch (`research/2026-10-05-security-audit.md`,
  `research/2026-11-17-lupa-sandbox.md` — markdown-embedded code snippets, already noted as
  pre-existing in `review-p3p4.md`'s re-review); `mypy src` — clean, 92 files.
- **Behaviour constants / `defaults.toml`**: `AI_PILOT_RECOVER_AGL_DROP_M = 40.0` and
  `AI_PILOT_RECOVER_IAS_CEILING_KMH = 280.0` both present in the **rendered**
  `body-layer/config/defaults.toml`, matching the plan's own Q-P3-2/Q5 figures; no second-sentence
  drop (both docstrings genuinely single-sentence, same as Reviewer's own finding).
- **Scope fit**: mode 2 only, as amended; mode 1 correctly gets only the two "unable" stubs
  (`_axes_cbtm_align_unready`, permanent `AI_OVERLAY`; `_axes_cbtm_break_unready`, temporary
  `NOT_READY`) — confirmed by reading `rules/actions.py` directly, matching Reviewer's own account.
- **Plan/alignment/review/perf/security**: all APPROVED on this tip (`review-p3p4.md`,
  `perf-p3p4.md`, `security-p3p4.md`), no required fixes outstanding from any of them.

## Accepted-items ledger

`.claude/scripts/accepted-items-ledger.sh plans/flight-control` reports "U1 U2 U3 not yet
answered (no `**Answered` line)" — a false negative of the mechanical check, not a real gap: this
plan answers its decisions inline (`**U1 answered 2026-11-18 (user, verbatim):**`, etc.) rather
than with a standalone `**Answered` line the script's regex expects, and the script's section
extraction concatenates every "Decisions Requiring User Input" heading in the file (six of them)
until it hits a non-matching heading, so it stopped at the first (U1-U3, from the original mode-2
plan, already closed and merged long before this batch).

Manually checking this batch's own decisions section (`plan.md` line 3776, "Decisions Requiring
User Input (this batch)"):

- **U11** — "does mode 1's 'break turn' ever need a 180° ('break away') form?" Answered by the
  main-loop amendment: *"U11 is answered: mode 1 gets break away too (standing direction: every
  mode-2 flight command except the 9K113 aligns exists in mode 1)."* **Not named in
  `implementation.md` by id** — but the behaviour it resolves to is built as a **deferral**, not
  silently dropped: the amendment itself states mode 1's break/break-away get only the temporary
  `NOT_READY` "unable" stub this batch, with the real mode-1 break mechanism explicitly pushed to
  "the mode-1 batch" (confirmed in `implementation.md`'s own opening line: *"mode-1 break
  turn/break away ... is explicitly withdrawn from this batch"*; confirmed in `rules/actions.py`'s
  `_axes_cbtm_break_unready` being commented "temporary until the mode-1 batch"; confirmed in
  `body-layer/ROADMAP/BL-16.md`'s next-batch entry, see below). Recommend Implementer add an
  explicit `U11` mention to `implementation.md`'s next section when the mode-1 batch lands, so the
  ledger's mechanical check stops reporting it as unmentioned once this batch's section is read in
  isolation.

## Recurring-fix pattern (process signal, not code debt)

This is the **second** time this exact shape has reached DoD/Reviewer: an unconditional new read
added to a per-poll function (first `NakedEyePerceptionSource.poll()`'s `get_firing_latest()`
in BL-B73/AC-B8; now `advance_parked_flight_state`'s `get_payload_latest()`) breaks every
hand-duplicated Fake*Client across the test suite that doesn't implement the new method, and in
both cases this was caught only by the full suite, not by a targeted run or the collect-only
smoke check. `.claude/agent-memory/implementer/project_emitter_visibility_stage_b_firing.md`
already names the first instance and its own fix shape (add the method to every duplicate,
returning a well-formed default). Recommend: when an Implementer adds an unconditional call to a
client method inside a function reached by the real poll loop, grep for every hand-duplicated
`Fake*AircraftClient`/`Fake*Client` in `tests/` and add the new method to each, rather than relying
on the reviewer's targeted file list to happen to include every test file that builds one — this
has now recurred with the same root cause and the same blind spot (targeted selection not covering
every Fake-client file) twice. This may be worth a check at Implementer/Reviewer time (a grep step
when adding an unconditional per-poll call) rather than catching it at DoD every time, since DoD's
full run is the only thing that has caught it either time.

## Live acceptance

Not reached — the DoD check itself failed before acceptance testing. No test card published this
round.

## Required fixes (routes to Implementer, then Reviewer, then back to DoD)

1. Add `get_payload_latest` to `tests/test_body.py`'s `FakeConsoleAircraftClient`, returning a
   well-formed "no payload sample yet" default (`None`, matching every other `get_*_latest`
   default on that fake), matching the real `AircraftLayerClient.get_payload_latest`'s contract.
2. Update `tests/test_aircraft_client.py::test_write_ai_pilot_goal_posts_to_command_endpoint`'s
   expected payload dict to include `"cbtm_action": None, "cbtm_seq": None`.
3. Re-run the full body-layer suite (`--full`) after both fixes and confirm `0 failed`.
4. (Optional, not blocking) Add an explicit `U11` mention to `implementation.md`'s mode-1-batch
   section once that batch starts, so the ledger script stops flagging it.

## Checks run, for the record

- `aircraft-layer`: `ruff format --check`, `ruff check`, `mypy src`, full `pytest tests -q -n auto`
  (961 passed) — all from `/Users/sg/Code/DCS-petrobrain/aircraft-layer/.venv`, cwd this worktree's
  `aircraft-layer/`.
- `body-layer`: `ruff format --check .`, `ruff check .`, `mypy src` (`PYTHONPATH=src:../world-model/src`),
  full `pytest tests -q -n auto` (4 failed / 3667 passed / 4 xfailed) — all from
  `/Users/sg/Code/DCS-petrobrain/body-layer/.venv`, cwd this worktree's `body-layer/`.
- `defaults.toml` rendered output read directly for the two new tunables.
- `.claude/scripts/accepted-items-ledger.sh plans/flight-control` run and read by hand (false
  negative explained above).

Tested tree: `1fab614c7241614af73a31c6cc23a06d0eec0608` (branch `feature/bl16-p3p4-cbtm`, checked
out here as `p3p4-dod`).

## Re-run 2026-11-19 — PASSED

**Verdict: PASSED.** Scoped to tip `edec57e4` (`feature/bl16-p3p4-cbtm`, checked out in this
worktree by fast-forwarding `worktree-agent-abc5db4afd3cd5010` onto it — `HEAD` was a strict
ancestor of `edec57e4` with a clean tree, so `git merge --ff-only edec57e4` applied cleanly; no
snapshot fallback needed). If the branch moves past `edec57e4`, re-run.

The two fixes from the required-fixes list above landed in `81352488` (test-only: the
`FakeConsoleAircraftClient.get_payload_latest` default and the `test_aircraft_client.py` expected-
payload update) and were re-reviewed APPROVED in `edec57e4` (`review-p3p4.md`'s final section,
"Review Summary (DoD fix round, `81352488`, test-only)") — full read of both diffs against both
required fixes, no production code touched, 273 passed on the two named test files. Item 4
(optional, not blocking) is resolved by the plan itself: `plans/flight-control/plan.md`'s
"Amendment 2026-11-18" section states outright *"U11 is answered: mode 1 gets break away too"*
and names the next-batch deferral explicitly, so no further implementation-log edit was needed —
confirmed by reading that section directly (see "Ledger" below).

**Full suites re-run from this worktree, both subprojects, both clean:**

- `aircraft-layer` (`/Users/sg/Code/DCS-petrobrain/aircraft-layer/.venv`, cwd this worktree's
  `aircraft-layer/`): `ruff format --check .` — 1 file would be reformatted
  (`research/2026-10-06-unit-id-join-reduce.py`); `ruff check .` — 1 finding (`EXE001`, same
  file). **Both pre-existing and untouched by this feature** — confirmed with
  `git diff --name-only 2ef961c3 HEAD -- aircraft-layer/research/2026-10-06-unit-id-join-reduce.py`
  (no output; `2ef961c3` is `git merge-base main HEAD`). `mypy src` — clean, 28 files. Full
  `pytest tests -q -n auto` — **961 passed**, 0 failed.
- `body-layer` (`/Users/sg/Code/DCS-petrobrain/body-layer/.venv`, cwd this worktree's
  `body-layer/`): `ruff format --check .` — 2 files would be reformatted
  (`research/2026-10-05-security-audit.md`, `research/2026-11-17-lupa-sandbox.md`). **Both
  pre-existing and untouched by this feature** — same merge-base diff check, no output. `ruff
  check .` — all checks passed. `mypy src` (`PYTHONPATH=src:../world-model/src`) — clean, 92
  files. Full `pytest tests -q -n auto` — **3671 passed, 4 xfailed, 0 failed** (3667 + the 4
  previously-failing tests, now passing).

No new debug output, TODOs, or unhandled-error paths found in the two test-only files touched by
`81352488`; no production code changed by the fix round, so the invariant/scope checks from the
original pass stand unchanged.

**Ledger, re-checked by hand** (the mechanical script only reads the plan's *first* "Decisions
Requiring User Input" heading, named limitation —
`.claude/agent-memory/dod/feedback_accepted_items_ledger_only_checks_first_decisions_section.md`):
U1/U2/U3 (mode-2 section, line 572) are answered and out of this batch's build scope as already
covered in the original pass; U11 (line 3778, "this batch") is answered in the plan's own
"Amendment 2026-11-18" subsection — *"U11 is answered: mode 1 gets break away too"* — and
explicitly deferred to the next batch (mode-1 break/break-away/rotor envelope), which is exactly
what `rules/actions.py`'s `_axes_cbtm_break_unready` comment and `body-layer/ROADMAP/BL-16.md`'s
next-batch entry already say. Nothing unmentioned, nothing unbuilt-and-undeferred.

**Unblock condition executed, not just read**: the required-fixes list's own item 3 ("re-run the
full body-layer suite after both fixes and confirm `0 failed`") is the clearing condition for this
round's FAILED verdict — it was run above, for real, from this environment, and shows `0 failed`.

**Checks run, for the record (this round):** `aircraft-layer` and `body-layer` full suites, lint,
format, mypy as logged above; `git diff --name-only` against `merge-base main HEAD` for both
flagged pre-existing lint/format files; `plans/flight-control/plan.md`'s "Amendment 2026-11-18"
section read directly for U11's resolution; `review-p3p4.md`'s final section read directly for
the fix-round re-review verdict.

Tested tree: `edec57e4` (branch `feature/bl16-p3p4-cbtm`).
