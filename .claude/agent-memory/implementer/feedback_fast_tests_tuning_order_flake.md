---
name: fast-tests-tuning-order-flake
description: fast-tests.sh's targeted file selection can reproduce a deterministic, order-dependent tuning.py singleton pollution that the full suite's alphabetical order never hits -- diagnose via tuning.py's import-time Resolution before assuming a regression.
metadata:
  type: feedback
---

`body-layer/src/tuning.py`'s `Resolution.defaulted`/`applied` dicts are populated incrementally,
module by module, the first time each tuning-declaring module is imported in the process --
reading `os.environ["PETROBRAIN_TUNING"]` at that exact import instant (the module's own
documented "constants bind by value at import" design). This makes the global `defaulted` set's
final contents depend on **which order test files get imported during collection**, not just which
files run.

`.claude/scripts/fast-tests.sh`'s targeted selection (grep -l by changed-file basename, insertion
order, not sorted) can produce an import order that differs from the full suite's own alphabetical
`pytest tests -q` order. On BL-16's mode-1 batch (`e1e1fe99`), this reproducibely failed
`test_main_print_tuning_works_without_aircraft_layer_url` (asserts `"at default"` appears in
`--print-tuning`'s output) under `fast-tests.sh body-layer` specifically, twice in a row -- but
passed standalone, within its own file, combined with any one other changed-file's test file, and
under the full suite's own order, every time.

**Why:** some earlier-imported module in that specific combination set `PETROBRAIN_TUNING` (or
left `os.environ` holding a value from an earlier test) pointing at a file supplying every key
(e.g. `config/defaults.toml` fed back as an override), so every constant resolves as `"applied"`
rather than `"defaulted"` for the rest of the process -- permanently, since the dicts are a
process-lifetime singleton, immune to a later `monkeypatch.delenv` inside the failing test itself.

**How to apply:** if a `--print-tuning`/`tuning.py`-adjacent test fails only under `fast-tests.sh`
and passes under every other invocation (alone, in its own file, under the full suite), don't treat
it as a regression from your diff — trace it through `tuning.py`'s own import-time `Resolution`
population first. Confirm by running the full suite (`pytest tests -q`, DoD's own order): if clean
there, root `CLAUDE.md`'s own rule applies — the full suite, not `fast-tests.sh`'s targeted
heuristic, is the authoritative gate. Report the finding plainly rather than chasing it to a fix;
fixing it for real means making `tuning.py`'s resolution re-readable per-test (an architecture
change, not an Implementer-scope fix for one feature's test run).
