---
name: scratchpad-probes-run-pre-implementation
description: A plan's scratchpad/ probes that monkeypatch the seam a plan is about to change (e.g. Contact.record) must be run against the pre-implementation commit, not the merged one -- running them post-merge raises a TypeError on the keyword collision, which is expected, not a defect.
metadata:
  type: feedback
---

On `plans/bounded-fold-displacement/` (`BL-B58` option 2 / `BL-B59`), the task asked me to "run"
the scratchpad probes as the independent check on the plan's acceptance-table numbers. Running
`probe_o2_bound.py` directly against the merged branch tip (`d2cfa4b`) failed immediately:

```
TypeError: _install.<locals>.record() got an unexpected keyword argument 'ambiguous_fold'
```

**Why this happens:** these probes (`plans/<feature>/scratchpad/*.py`) exist to measure a design
*before* it is implemented — they monkeypatch the real seam (`Contact.record`,
`_fold_target_for_ambiguous_candidates`) to install their own version of the proposed mechanism,
so the numbers in the plan are independently derived rather than read off the eventual
implementation. Once the real implementation lands, `Contact.record`'s signature already has the
keyword the probe's own patched wrapper does not expect, and the two collide.

**How to apply:** for a Reviewer verifying a plan's own acceptance-table numbers via its
`scratchpad/` probes, check out (via `git archive <pre-implementation-sha> | tar -x -C <scratch>`,
not a live checkout if the branch is held elsewhere) the commit the plan was written against —
usually the plan's own commit, named in the plan's front-matter or Stage 0 — and run the probes
from inside that snapshot's subproject directory. Running them against the merged tip is not a
stricter check; it is the wrong input entirely, and the `TypeError` is itself the signal, not a
defect in either the probe or the implementation. The merged code's own correctness is checked
separately, by mutation against the merged tip directly (disable the clamp, revert `max()` to
`+=`, etc.) — a different and complementary check from reproducing the plan's own numbers.

See also `plans/bounded-fold-displacement/scratchpad/README.md`'s own line: "The probes assign
`contact.position` directly; merged code must not" — the probes were never meant to run against
merged code at all.
