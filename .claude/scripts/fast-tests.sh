#!/usr/bin/env bash
# Fast test selection for one subproject: a smoke check plus the tests that touch the changed
# files. Used by the commit gate (commit-quality-gate.sh) and by implementer/reviewer runs.
# The FULL suite is the Definition of Done's job (and a merge whose tree DoD did not test).
#
# User direction, 2026-11-16: "not every commit needs a test run, definetely not a complete test
# suite. Smoke test yes. Test on the files that were cahnged, yes." and "since DoD runs the full
# suite, and usually merges right after, the merge does not need another full suite".
#
# Usage:
#   .claude/scripts/fast-tests.sh <subproject> [changed-path ...]
#       changed paths are repo-relative; with none given, the subproject's changes against the
#       merge-base with origin/main (committed, staged and unstaged) are used.
#   .claude/scripts/fast-tests.sh --full <subproject>
#       the whole suite (what DoD runs), in parallel when pytest-xdist is installed.
#   PETROBRAIN_FULL_TESTS=1 makes every invocation a --full one.
#
# What "fast" runs:
#   1. Smoke: `pytest --collect-only` over the whole tests/ dir -- every test module imports and
#      every test collects. Catches a broken import or syntax error anywhere, in seconds.
#   2. Targeted: changed test files, plus every test file that names a changed module (by module
#      basename for .py, by file basename for anything else -- Lua, TOML, sequence .md), run with
#      `-m "not slow"`. Tests marked `slow` (scenario mock flights, sweeps) run only in --full.
# Run from anywhere; each pytest runs with the subproject as CWD (mypy/pytest config discovery).
set -uo pipefail

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "fast-tests: not in a git tree" >&2; exit 2; }
cd "$ROOT" || exit 2

FULL=0
if [ "${1:-}" = "--full" ]; then FULL=1; shift; fi
[ "${PETROBRAIN_FULL_TESTS:-0}" = "1" ] && FULL=1

SUB=${1:-}
if [ -z "$SUB" ] || [ ! -d "$SUB/tests" ]; then
    echo "usage: fast-tests.sh [--full] <subproject> [changed-path ...]" >&2
    exit 2
fi
shift

PYTEST="$SUB/.venv/bin/pytest"
[ -x "$PYTEST" ] || PYTEST=$(command -v pytest || true)
if [ -z "$PYTEST" ]; then
    echo "fast-tests: no pytest for $SUB (expected $SUB/.venv/bin/pytest)" >&2
    exit 2
fi
PY="$(dirname "$PYTEST")/python"

# body-layer imports world-model in-process; every other subproject needs only its own src.
PP="src"
[ "$SUB" = "body-layer" ] && PP="src:../world-model/src"

# Parallel when pytest-xdist is importable in this venv.
XDIST=""
if [ -x "$PY" ] && "$PY" -c "import xdist" >/dev/null 2>&1; then XDIST="-n auto"; fi

if [ "$FULL" = "1" ]; then
    echo "fast-tests: $SUB full suite ${XDIST:+(parallel)}"
    # shellcheck disable=SC2086
    (cd "$SUB" && PYTHONPATH="$PP" "$ROOT/$PYTEST" tests -q $XDIST)
    exit $?
fi

# Changed paths, restricted to this subproject.
if [ "$#" -gt 0 ]; then
    CHANGED=$(printf '%s\n' "$@")
else
    BASE=$(git merge-base HEAD origin/main 2>/dev/null || echo HEAD)
    CHANGED=$( { git diff --name-only "$BASE" -- ; git diff --name-only --cached ; git ls-files --others --exclude-standard ; } | sort -u)
fi
CHANGED=$(printf '%s\n' "$CHANGED" | grep "^$SUB/" || true)

# 1. Smoke.
echo "fast-tests: $SUB smoke (collect all)"
(cd "$SUB" && PYTHONPATH="$PP" "$ROOT/$PYTEST" tests -q --collect-only -p no:cacheprovider >/dev/null 2>&1)
SMOKE=$?
if [ "$SMOKE" -ne 0 ]; then
    echo "fast-tests: $SUB smoke FAILED -- collection error; rerun to see it:"
    echo "  (cd $SUB && PYTHONPATH=$PP .venv/bin/pytest tests -q --collect-only)"
    exit "$SMOKE"
fi

# 2. Targeted selection.
SELECTED=""
add() { case " $SELECTED " in *" $1 "*) ;; *) SELECTED="$SELECTED $1" ;; esac; }
while IFS= read -r path; do
    [ -n "$path" ] || continue
    rel=${path#"$SUB/"}
    case "$rel" in
        tests/test_*.py)
            [ -f "$SUB/$rel" ] && add "$rel" ;;
        tests/*) ;;  # fixtures/conftest: covered by smoke; a conftest change also selects nothing extra
        *)
            base=$(basename "$rel")
            key=${base%.py}
            [ -n "$key" ] || continue
            # test files that name the module/file
            for t in $(cd "$SUB" && grep -l -w -F -- "$key" tests/test_*.py 2>/dev/null); do add "$t"; done
            ;;
    esac
done <<< "$CHANGED"

if [ -z "$SELECTED" ]; then
    echo "fast-tests: $SUB no targeted tests for the changed files (smoke passed)"
    exit 0
fi

COUNT=$(printf '%s\n' $SELECTED | wc -l | tr -d ' ')
# Parallel only pays for itself past a handful of files (worker start-up costs seconds).
PAR=""
[ "$COUNT" -gt 4 ] && PAR="$XDIST"
echo "fast-tests: $SUB $COUNT targeted test file(s), -m 'not slow' ${PAR:+(parallel)}"
# shellcheck disable=SC2086
(cd "$SUB" && PYTHONPATH="$PP" "$ROOT/$PYTEST" $SELECTED -q -m "not slow" $PAR)
RC=$?
# pytest exit 5 = "no tests collected" (e.g. every selected test is slow): not a failure.
[ "$RC" -eq 5 ] && { echo "fast-tests: $SUB selected tests are all slow-marked; covered by --full"; exit 0; }
exit "$RC"
