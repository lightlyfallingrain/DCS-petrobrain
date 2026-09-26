### Definition of Done: `fix/audio-adapter-review-findings`

**Branch HEAD:** `f9b85d7` (Reviewer round 2 APPROVED). Diffed against `main` `2802c4f` (the two
whole-subproject reviews this fix is a change request against).

**Verified by re-running commands, not by trusting the reports.** Worktree
`agent-ad4668f9fb70caab0` was checked out on a stale unrelated branch at task start
(`worktree-agent-ad4668f9fb70caab0` @ `bd28563`, a fast-forward ancestor of both `main` and this
branch); the target branch is checked out in the main working directory so could not be checked
out here too (git refuses the same branch in two worktrees). Detached-checked-out `f9b85d7`
directly (a plain commit, not a branch name — no conflict), then additionally `git archive f9b85d7`
into a scratch tree (`/private/tmp/.../scratchpad/dod-audio-adapter/`) and built a fresh
`audio-adapter/.venv` there, per this repo's own "DoD worktree main-based" trap memory, to avoid
any doubt about which tree's code was actually exercised.

## Scope (mechanical, from diff)

`git diff --name-only bd28563 f9b85d7` — only `audio-adapter/` code/tests plus non-code bookkeeping
(agent-memory files, `plans/audio-adapter-review-findings/*.md`, the two review-doc corrections).
No other subproject touched. Only `audio-adapter/`'s own command set is required, confirmed by diff
rather than assumed.

## Code Quality — PASS

Run independently in the scratch tree's fresh venv (`python3 -m venv .venv && pip install ruff
mypy pytest`):

```
$ .venv/bin/ruff format --check src tests
29 files already formatted

$ .venv/bin/ruff check src tests
All checks passed!

$ .venv/bin/mypy src
Success: no issues found in 15 source files

$ .venv/bin/pytest tests -q
212 passed, 1 skipped in 28.13s
```

Matches both Implementer rounds' and both Reviewer rounds' reported counts exactly (212/1/0).

No debug output, no `TODO`/`FIXME`/`pdb`/`breakpoint` introduced (`git diff bd28563 f9b85d7 --
audio-adapter/src audio-adapter/tests | grep -iE "print\(|TODO|FIXME|pdb|breakpoint"` — no matches).

No unhandled errors in the data path: `_read_body()` now guards both non-numeric and negative
`Content-Length` with a clean `400` before any `rfile.read()` call — confirmed live below, not just
read.

All new/modified files staged and committed — `git status --porcelain` on the branch tip is clean
(confirmed on this worktree's own commit below).

## Scope & Correctness — PASS

- No `plan.md` for this feature — correct: this is a Security/Performance-Reviewer change request
  (`AGENTS.md`, "A change request from Security or Performance Reviewer re-enters the loop"), whose
  spec is the two committed whole-subproject review reports, not a fresh Architect plan. That rule's
  prescribed path is Implementer → Reviewer (review of the fix) → DoD — exactly what happened, in
  two rounds.
- Diff matches `implementation.md`'s description exactly — read the literal `capture.py`/`server.py`
  diff against the prose and both agree line for line (resolver function, help text, `_read_body`
  shape, the collapsed branch in round 2).
- No unplanned scope: grepped for other `args.poll_hz`/`DEFAULT_POLL_HZ` readers (Reviewer already
  did this and I re-confirmed via the diff) — `tools/probe_joystick.py` has its own unrelated flag,
  untouched. No body-size cap added (deliberately deferred, see Security below). `--poll-hz 0`/
  negative validation untouched (pre-existing gap, correctly left alone per Reviewer's optional-note,
  consciously not required).
- No invariants violated — single-subproject change, no new cross-subproject import, no multiplayer
  surface, no DCS-authority question involved.

## Testing — PASS, with one process note worth naming

- `test_capture_cli.py` (new) covers `_resolve_poll_hz` for every `--ptt` value's default, explicit
  override, and that the parser's own default is `None` (guards against reintroducing the bug via
  per-source parser mutation).
- `test_server.py`/`test_transcribe_api.py` cover missing/non-numeric/negative/valid
  `Content-Length` for both `/speak` and `/transcribe`, using a raw-header helper since
  `urllib.request.Request` cannot construct an invalid header.
- **Round 1's negative-length tests were meaningless as written** (passed against the pre-fix code
  for an unrelated reason) — this is exactly the "tests are meaningful, not decorative" DoD
  criterion in action, and it was Reviewer round 1, not this gate, that caught it by empirically
  reverting the code and running the tests, per the project's standing "verify the mechanism, not
  the hypothesis" discipline. Round 2's fix (assert on the specific rejection-path error message)
  was independently re-verified by Reviewer round 2 in a second, separate scratch extraction, and by
  me a third time (see below) — the same negative case reliably distinguishes pre-fix from post-fix
  across three independent runs now.
- No existing tests broken — same 212/1 count before and after both rounds.

**Independent live re-verification (this gate, not reusing implementer/reviewer output):**

```
$ .venv/bin/python -c "from audio_adapter.capture import _resolve_poll_hz
print('dcs default:', _resolve_poll_hz('dcs', None))
print('key default:', _resolve_poll_hz('key', None))
print('joystick default:', _resolve_poll_hz('joystick', None))
print('dcs explicit override:', _resolve_poll_hz('dcs', 45.0))"
dcs default: 30.0
key default: 60.0
joystick default: 60.0
dcs explicit override: 45.0
```

Started the real server (`python -m audio_adapter --port 17795 --target local`) and hit `/speak`
with a raw `http.client` connection (not `urllib`, which cannot construct an invalid header):

```
missing      -> 400 {"error": "body must be valid JSON"}
negative(-1) -> 400 {"error": "invalid Content-Length: '-1'"}
non-numeric  -> 400 {"error": "invalid Content-Length: 'abc'"}
valid body   -> 200 {"ok": true}
```

Matches the fix's intended behavior exactly: bad headers rejected before any body read; a real
request still succeeds.

## Documentation — PASS

- Reviewer round 1's one required fix (test-gap) is addressed in round 2, and round 2's own verdict
  is **APPROVED with no required fixes** — confirmed by reading `review.md`'s Round 2 section in
  full, not just its verdict line. The one optional suggestion (soften the exact-message assertion
  to `.startswith`) was **consciously declined**, not missed: `review.md` states it explicitly as
  "Not required... optional," and no implementer round after `1b2e337` touches those assertions.
- The corrected security record is coherent. Read `security-audit-audio-adapter.md`'s finding 2 and
  its "Focus-area findings" cross-reference (row 111 area) directly: both carry the same correction,
  quote the original wrong claim verbatim, explain the real pre-fix mechanism (`else b""` branch,
  then `json.loads("")` failing), and credit the Reviewer's empirical check by name. No
  half-corrected instance found — I read every occurrence of "negative" / "Content-Length" /
  "thread hang" in the document, not just the first hit.
- `--help` text documents the source-dependent default in place of requiring a code read — confirmed
  live above (`--poll-hz POLL_HZ  talk-control poll rate; default depends on --ptt: 30 Hz for dcs
  ..., 60 Hz for key/joystick ...`).

## Security — PASS (change-request path, not a fresh feature)

This branch has no `security-plan-review.md`/`security-review.md` of its own, and that is correct
for this task shape: it is a Security/Performance-Reviewer change request against an already-
APPROVED whole-subproject audit (`security-audit-audio-adapter.md`, `5594cb9`) and performance sweep
(`perf-review-audio-adapter.md`, `2802c4f`), both committed on `main`. Per `AGENTS.md`'s explicit
rule for this case, the required path is Implementer → Reviewer → DoD, which is what ran — a fresh
Security pass was not warranted, and Reviewer's own re-verification of the security document's
correction (round 2, independently reproduced in its own scratch extraction) stood in for it here.

**The deferred body-size-cap finding (RECOMMENDED #1) is recorded durably, not lost**: it names
`audio-adapter/ROADMAP.md`'s existing backlog item ("`POST /audio/play` has no request-size cap...")
by name and explicitly extends that standing exemption to cover `/speak`/`/transcribe`/`/stop` too
("recording it here so the same standing exemption covers it explicitly rather than being assumed
to"). That cross-reference lives in a committed, permanent document
(`security-audit-audio-adapter.md`), so the deferral will not be silently lost. One improvement
worth making at the next audio-adapter roadmap touch (not blocking this merge): the `ROADMAP.md`
backlog bullet itself still names only `POST /audio/play` — adding "(and audio-adapter's own
`/speak`/`/transcribe`/`/stop`, per the 2026-09-26 security audit's RECOMMENDED #1)" to that one line
would make the extension visible from the roadmap side too, not only from the audit doc.

## Roadmap entry — recommend one, following the `aircraft-layer-hardening` precedent

`aircraft-layer/ROADMAP.md` recorded its own review-driven hardening fix as a `[x]` Status entry
even though it wasn't a milestone ("Hardening: bounded audio queue + guarded collector `accept()`").
The same treatment fits here. Proposed one-line addition to `audio-adapter/ROADMAP.md`'s Status
section at merge time:

> - [x] **Hardening: per-source `--poll-hz` default + `Content-Length` guard — done 2026-09-26,
>   merged `<merge-sha>`** (`fix/audio-adapter-review-findings`, no plan.md — scoped directly from
>   the 2026-09-26 whole-subproject reviews). `--ptt dcs` now defaults to 30 Hz instead of the
>   undifferentiated 60 Hz the perf review found wired to nothing; `/speak`/`/transcribe` reject a
>   missing/non-numeric/negative `Content-Length` with a clean 400 before any body read. Two review
>   rounds: round 1's negative-length regression tests proved nothing (passed against the pre-fix
>   code too, for an unrelated reason); round 2 replaced the assertion with the specific
>   rejection-path error message, independently re-verified. **Does not change what's next** —
>   pre-existing RECOMMENDED findings, not new information.

## Milestone-completion question (root `CLAUDE.md`)

Does not change what the next milestone should be, and invalidates no downstream assumption. Both
fixes are latent hardening against findings already known and accepted in scope at the time of the
whole-subproject reviews; nothing here reveals new information about the pipeline's behavior.

---

## Acceptance boundary — what these fixtures structurally cannot reach

Both fixes are provable end-to-end with automated tests and a local loopback server, which is why
this gate ran them directly rather than deferring everything to the user. What no fixture here can
reach:

- **Fix 1 (`--poll-hz` default) has no in-cockpit observable.** The change is a request-rate halving
  on a background HTTP poll loop; nothing about it is perceivable in the sim, and the perf review
  that asked for it says plainly "I have not measured a frame-time or CPU regression... so I cannot
  claim it is currently causing a felt problem." Per the same judgment `aircraft-layer-hardening`
  used ("no acceptance card... neither changes anything perceivable in the cockpit"), there is no
  honest cockpit-based pass/fail card to write here. What *can* be verified live is the request
  *rate itself*, via the collector's own debug log — not a cockpit behavior, a plumbing fact. See
  the acceptance card below; it is offered as an optional confirmation, not a blocking pass
  criterion.
- **Fix 2 (`Content-Length` guard) is fully covered by what already ran** — this gate hit the real
  HTTP server with raw malformed headers, not just the unit tests. There is no live-DCS-only gap
  here.

## Acceptance Testing Plan: audio-adapter review-findings fix

**Branch:** `fix/audio-adapter-review-findings` — check out with:
```
git checkout fix/audio-adapter-review-findings
```
(This is already the branch checked out in the main working directory — no action needed if you're
already there.)

**Goal:** Confirm the two review-driven fixes behave as intended; optionally confirm the poll-rate
halving is real on the box it was written for.

**Prerequisites**
- [ ] `cd audio-adapter && mypy --strict src` — already confirmed clean above; re-run only if you
      want to see it yourself.
- [ ] A `.venv` in `audio-adapter/` (create with `python3 -m venv .venv && .venv/bin/pip install
      ruff mypy pytest` if missing — it's gitignored).

**Test Cases**

1. **Content-Length guard, on the Mac, no DCS needed.** In one terminal:
   ```
   PYTHONPATH=src .venv/bin/python -m audio_adapter --target local
   ```
   In another:
   ```
   curl -i -X POST http://127.0.0.1:7795/speak -H "Content-Length: -1"
   ```
   Expect `HTTP/1.0 400` and `{"error": "invalid Content-Length: '-1'"}` — not a hang, not a
   traceback in the server's terminal.

2. **A normal request still works.**
   ```
   curl -X POST http://127.0.0.1:7795/speak -d '{"text": "Confirming the guard did not break normal speech.", "urgent": false}'
   ```
   Expect `{"ok": true}` and to hear the line spoken.

**Edge Cases to Probe**
- `curl -i -X POST http://127.0.0.1:7795/speak -H "Content-Length: abc"` — expect `400`,
  `{"error": "invalid Content-Length: 'abc'"}`, same as the negative case (collapsed branch from
  round 2).

**Optional — poll-rate confirmation (needs the Windows box + a running collector + DCS; UNVERIFIED
by me, cannot run it)**

There is no cockpit-perceivable difference between 30 Hz and 60 Hz polling — do not expect to feel
or hear anything change. What you *can* see is the request count in the collector's own debug log,
since `GET /ptt/state` handling is logged at DEBUG via `log_message` (`aircraft-layer/src/api/
server.py`):

1. Start the collector with `--debug` (per `aircraft-layer/WORKFLOW.md`).
2. Start capture with no `--poll-hz` override: `PYTHONPATH=src .venv/bin/python -m
   audio_adapter.capture --ptt dcs --adapter-url http://<mac-ip>:7795`.
3. Let it run ~10 seconds, then count `GET /ptt/state` lines in
   `Saved Games\DCS\Logs\aircraft_layer_debug.log` over that window (roughly line-count / seconds).
   Expect **~30/s**, not the previous ~60/s. This is the only way to observe the fix directly; there
   is no simpler in-flight signal, and I'm stating that plainly rather than inventing one.

**Pass Criteria**
The feature passes if test cases 1-2 and the edge case above produce the stated results and normal
speech playback is unaffected. The poll-rate confirmation is optional evidence, not a blocking
criterion — its absence does not block merge (root `CLAUDE.md`: never block a merge on live
acceptance the user cannot currently perform).

**Live-acceptance debt:** if the poll-rate confirmation above is not run before merge, it should be
recorded in `audio-adapter/ROADMAP.md`'s live-acceptance debt (or equivalent backlog note) as
pending the next sortie that has the collector running in `--debug` mode — not left as a one-off
caveat in this file.
