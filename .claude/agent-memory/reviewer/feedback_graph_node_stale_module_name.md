---
name: graph-node-stale-module-name
description: knowledge-graph node named a function at logger.py:1301 that no longer exists (module renamed/merged into body.py) -- verify a graph-named second call site exists on disk before treating it as evidence of a missed site.
metadata:
  type: feedback
---

While verifying the "only remaining reporting reader of `runner.scan_plan`" claim on
`fix/optic-views-actual-look`'s follow-on commit (review in
`plans/optic-views-actual-look/review.md`, delta `9031125e..8091730e`), `.claude/scripts/gq.sh`
returned a node `_speech_log_sink() [src=body-layer/src/logger.py loc=L1301]` — a second
definition, which would have meant the commit's "grepped every other reporting reader" claim was
false and a sibling defect was missed.

`body-layer/src/logger.py` does not exist in the tree at all (`ls body-layer/src/` has no
`logger.py`; `grep -rn "_speech_log_sink" src/` finds exactly one definition, in `body.py`). The
graph is stale here — it still indexes an old module layout from before a rename/merge into
`body.py`, and the node's own `gq.sh` output already warns of this generically ("a miss means
not indexed yet, never does not exist") but gives no equivalent warning for a *stale hit*.

**Why:** root `CLAUDE.md`'s graph-vs-grep split says grep is authoritative for "does anywhere
still assert X" questions, and this is exactly that shape of question applied to source structure
rather than prose — a graph hit naming a file/line is a claim about what existed *when the graph
was last built*, not what exists now.

**How to apply:** when the graph names a second call site, construction site, or sibling function
as evidence a claim in a diff/commit is incomplete, confirm the named file/symbol actually exists
on disk (`ls`/`grep`) before treating it as a real finding — a graph rebuild lag can manufacture a
false "you missed one" exactly as easily as it can hide a real one. Don't report a stale graph node
as a defect in the reviewed commit without this check.
