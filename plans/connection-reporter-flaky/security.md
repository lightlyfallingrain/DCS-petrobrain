## Security Deep Analysis: connection-reporter-flaky

### Dependency Status

No dependency change. `git diff f4e552c1 08630ae7 --stat` touches only `body-layer/tests/test_logger.py`,
`body-layer/tests/test_brain_client.py`, four `.claude/agent-memory/` notes, `body-layer/ROADMAP/BL-B92.md`,
`body-layer/ROADMAP/BL-B93.md`, `body-layer/ROADMAP/body-layer-backlog.md`, and
`plans/connection-reporter-flaky/{debug,review}.md`. No `pyproject.toml` in any subproject changed
(`git ls-files '*/pyproject.toml'` lists six; none in the diff).

`pytest-randomly` — named explicitly in the task — was checked and is declared nowhere:
`grep -rn "pytest-randomly\|pytest_randomly\|randomly"` across `*.toml`/`*.cfg`/`*.ini` in the repo
returns no hits. `debug.md`/`review.md` corroborate it as a manual, dev-time-only install into the
shared `body-layer/.venv` for seed-sweeping during the investigation (not committed, not declared),
and confirm it has since been uninstalled. This matches the user's own account; nothing in this diff
reintroduces it.

### Code Findings

No production code changed (confirmed by diff scope above — `body-layer/src/` is untouched). The
only behavioural changes are inside two test files:

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/tests/test_brain_client.py:334` | `monkeypatch.setattr(urllib.request, "urlopen", _refused)` | Patches a stdlib call site to raise a synthetic `URLError`-wrapping-`ConnectionRefusedError`, replacing a previous real loopback socket bind. `pytest.MonkeyPatch` auto-reverts at test teardown regardless of outcome — standard, scoped, not a leak. The new approach *removes* a real bound socket from this test, which is a smaller attack/noise surface than before, not a larger one. | None |
| `body-layer/tests/test_brain_client.py:343-345`, `test_logger.py:4697,4724,4759` | Filter `caplog.records` by `r.thread == worker.ident` / `r.name == logger_module.__name__` | Addresses genuine cross-test pollution from leaked daemon `_poll_loop` threads (pre-existing architecture: nothing stops a `daemon=True` thread started by another test's `BrainLayerClient`). This is a test-isolation fix, not a new behavior reachable outside the test suite. No production thread-lifecycle change. | None |
| `body-layer/tests/test_brain_client.py:104-115` (pre-existing, untouched by this diff) | Real `socket.bind(("127.0.0.1", 0))` test server | Loopback-only, ephemeral port, pre-existing — not part of this feature's diff, not a new finding here. | None (pre-existing, out of scope) |

No `eval`/`exec`, no deserialization of untrusted data, no new file paths, no new network listener
bound beyond loopback, no secrets, no shell-outs. The diff cannot be reached by anything on the LAN
or by untrusted input — it only changes how the test suite observes its own synthetic log records.

### Passed to Reviewer

None — no player-facing or correctness-adjacent behavior in this diff; it is test-infrastructure
only.

### Verdict

APPROVED

### Required Fixes (if any)

None.
