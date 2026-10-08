---
name: bl11-stage4-round4-logging-visibility-fix-approved
description: APPROVED cf65d8a; caplog.at_level hides a visibility gap pytest-only testing can't reach
metadata:
  type: project
---

Round 4 of `BL-11` Stage 4 (`feature/bl11-stage4-fail-closed`): DoD found `_log_live_los_coverage_
summary`'s `logger.info(...)` line never printed on a real run — nothing in `body-layer/`
configures logging, so Python's `logging.lastResort` fallback (threshold `WARNING`) silently drops
every `INFO` call. Survived three review rounds and a security deep analysis because every
existing test used `caplog.at_level(logging.INFO, ...)`, which forcibly overrides the ambient level
and proves the call fires without proving it is visible under the real default.

**The general lesson**: `caplog.at_level` is correct for pinning that a log call happens with the
right message, and is structurally blind to whether that call is visible under a module's actual,
unconfigured logging configuration. Any module that owns its own named logger and has no
`basicConfig`/handler setup anywhere needs at least one test with **no** `caplog` override at all,
asserting on real `capsys`-captured `stderr`/`stdout`. Reviewing a logging-visibility fix: mutate by
commenting out the configuration call and rerun the visibility tests — they should fail against
real-stream assertions while `caplog`'s own "Captured log call" section still shows the record.
That's the proof the two claims ("fires" vs. "visible") are actually distinct, not asserted.

Also verified by `grep`+read (not trusted from the implementer's writeup): the scoping decision to
configure one named logger (`logging.getLogger(__name__)`, scoped, never `logging.basicConfig`/
root) is safe because Python's logger-hierarchy lookup only composes on dotted-name prefixes —
`"logger"`, `"perception.hybrid_source"`, `"belief.crew_console"` are three unrelated names here,
so raising one's level/handler cannot leak into another's unrelated per-poll `INFO` call
(`hybrid_source.py`'s `_record_drop`, confirmed called on every unassociable detection every poll
from both of its call sites) and flood it.

**One real but non-blocking finding**: the new `_configure_logger_for_main()` leaves
`logger.propagate` at its default `True`. Reproduced: if this module is ever imported into a host
process that has its own root handler, a line now prints twice (confirmed with a `basicConfig` +
`_configure_logger_for_main()` repro). The docstring explicitly reasons about exactly this
imported-into-a-host-process scenario while the code doesn't handle the duplicate-print case —
this branch has now disagreed with its own comments twice (round 1's flood/silence inversion, this
one). Ruled **optional, not required**: nothing in the current call graph reaches the scenario, and
the failure mode if it ever did is noisy (a doubled line), not silent (a dropped one) — the inverse
of what this whole round exists to fix. Logged as a recommendation (`logger.propagate = False`, one
line) for whoever next touches this module, not a blocker.

See also [[project_bl11_stage4_coverage_log_defect]] and [[project_bl11_stage4_round3_main_branch_
wiring_approved]] for the earlier rounds on this same plan.
