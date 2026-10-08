# BL-11 Stage 4 (fail-closed LOS gate) — log-visibility check

**Branch:** `feature/bl11-stage4-fail-closed`. Check out with:

```
git checkout feature/bl11-stage4-fail-closed
```

## What this is, and is not

This is **not** a check of whether Petrovich sees the right things in flight. The fail-closed gate
itself (no live LOS verdict -> not admitted) is already authorised by real flight evidence and
**must not be re-flown**: the 2026-10-08 sortie measured 145/145 evaluated objects and 85/85
admitted objects receiving a live verdict, against a 76% baseline before the statics-enumeration
fix. See `docs/acceptance/2026-10-08-los-statics-population-sortie.md` for that evidence.

**What this card is for**: a narrow, mechanical check that two log lines actually print on a real
run, now that the logging-visibility bug DoD found (nothing in this codebase configured a logging
handler, so the end-of-run summary's `INFO` line was silently dropped by Python's `WARNING`-level
`lastResort` fallback) is fixed. There is **nothing to hear in the cockpit** — this is a post-flight
log check, not a perception.

## Setup (verified against this branch)

Run from `body-layer/`, using that subproject's own venv. Verified working on this branch:

```
cd body-layer
PYTHONPATH=src:../world-model/src .venv/bin/python -m logger --help
```

This prints argparse usage with no error — confirms the venv/PYTHONPATH setup is correct before
flying.

## The real run

Use the existing debug-view run script, which already wires `--detection-trace` (needed for the
coverage reducer below) — this is `run-scripts/run-crew-text-debug-view.sh`, unchanged by this
branch:

```
cd run-scripts
./run-crew-text-debug-view.sh
```

Fly a normal sortie. Stop the process the way you normally do (Ctrl-C / closing the session) —
that is what triggers the `finally:` block that writes the summary line.

## What to check afterward

**1. The end-of-run summary line appeared on stderr/console**, reading something like:

```
live LOS coverage: <no_verdict>/<evaluated> gate-4 evaluations had no live verdict this sortie
```

Expect a **healthy sortie to read something like `0/N`** (or a small number relative to N) — this
is the "guard visibly passed" line, and it must appear even when there is nothing wrong to report.
This line is what the whole DoD round existed to make visible; if it's missing, that's the defect
recurring.

**2. The transition warning did NOT appear**, unless something was actually wrong:

```
live LOS coverage gap: naked-eye gate-4 evaluations ...
```

This line already worked before the fix (by an accident of Python's logging defaults that this
branch's fix now makes deliberate) — it should still behave the same way: silent on a healthy
sortie, present if the live LOS feed genuinely degrades mid-flight.

**3. Reduce the detection trace for the real coverage number** (post-flight, not in the cockpit):

```
cd body-layer
.venv/bin/python ../.claude/scripts/los-verdict-coverage.py
```

With no argument this takes the newest `logs/dcs-detection-trace-*.jsonl` automatically (logs roll
per sortie). Expect a coverage share consistent with the 2026-10-08 evidence (close to 100% of
*evaluated* objects, not the old 76%-missing baseline) — this is a sanity cross-check against the
log line in step 1, not a new measurement; if it disagrees with what the log line says, say so.

## Bring-back list

- Did the `live LOS coverage: N/M ...` line appear at all? What were N and M?
- Did the `live LOS coverage gap: ...` warning appear? If so, what did it say, and does that match
  something you noticed in flight (feed degradation, a weird patch of terrain, etc.)?
- Does the reducer script's number roughly agree with the printed summary line?
- Anything that surprises you is worth more than anything on this list.
