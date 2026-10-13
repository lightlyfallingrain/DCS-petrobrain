---
name: bl12-trace-records-unconditional
description: GroupStore.reconcile always builds its trace_records dicts (one per cluster), even with --group-trace off; only the sink write is gated. A new field added to that dict (e.g. fold_budgets) costs on both the on and off path, not just the on path.
metadata:
  type: project
---

`body-layer/src/belief/groups.py`'s `reconcile` builds `trace_records` (one dict per cluster,
phases 1-3) unconditionally, regardless of whether `--group-trace`/`trace_sink` is set. Only the
final write-out (`if trace_sink is not None: for record in trace_records: trace_sink(record)`) is
gated. This was BL-12's own design (`plans/group-contact-identity/performance-review.md`), not
something a later feature introduces.

**Why: a dict field added to that record (e.g. `BL-B58`'s `fold_budgets`, one list comprehension
per cluster) is paid on every `reconcile` call, trace-on or off** — not free when the flag is
off, just small. Measured (`plans/bounded-fold-displacement/performance.md`): adding
`fold_budgets` moved the no-sink full-reconcile baseline from BL-12's 0.100 ms to 0.103-0.105 ms
at realistic scale — inside noise, but the mechanism (always-built, not gated) is the thing to
check, not assume, on the next field added to this record.

**How to apply:** when reviewing a change that adds a field to `reconcile`'s trace record, measure
the no-sink path too, not only the `--group-trace`-on delta — the dict construction itself is the
unconditional cost, the sink write is the conditional one. See
[[bl12-group-trace-writer-is-not-rare]] if it exists, or `plans/group-contact-identity/
performance-review.md`'s "`group_trace_log.GroupTraceLogWriter`" finding for the full account of
why the writer's own "handful of rows" docstring premise is false but the cost is still immaterial
at today's scale.
