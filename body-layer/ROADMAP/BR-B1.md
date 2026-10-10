# BR-B1 — The wider CLASSIFY_COMMAND_VOCABULARY the duplicate Stage 2 branch built

- [ ] **Revisit the 44-token `CLASSIFY_COMMAND_VOCABULARY` (token → spoken-phrase mapping) that
  `feature/br1-stage2` built, against the 7-token no-slot set `main` ships.** Deferred at the
  2026-09-25 fold, not rejected — `plans/brain-layer/implementation.md`'s "Folding in the duplicate
  branch", item 4, judged it *"a scope difference, not a style difference"* and said to revisit in a
  later prompt-tuning pass if the narrow set under-serves real sorties. `[[BR-1.2]]`'s own entry
  names the same open question. This entry exists so the artifact survives the branch: everything
  else that branch held was either folded into `main` or deliberately rejected, and the token list
  itself was only ever *described* in prose. First `BR-B` item; brain-layer has no `ROADMAP/` of its
  own, so its entries live here (root `CLAUDE.md`, "Backlog items carry IDs").

**What `main` offers the classify prompt today** (7 tokens, no slots, `brain-layer/src/prompts.py`):

```
watch_nearest, watch_nearest_air_defence, report_all,
cancel_task, cancel_scan, cancel_watch, stop_talking
```

**What the duplicate branch offered** — 44 entries, and a `dict[str, str]` rather than a tuple, so
each token carried the spoken phrase the model should recognise it from:

```python
CLASSIFY_COMMAND_VOCABULARY: dict[str, str] = {
    "scan_ahead": "scan ahead",
    "scan_left": "scan left",
    "scan_right": "scan right",
    "scan_full": "scan the full arc",
    "scan_bearing_n": "scan north",
    "scan_bearing_ne": "scan northeast",
    "scan_bearing_e": "scan east",
    "scan_bearing_se": "scan southeast",
    "scan_bearing_s": "scan south",
    "scan_bearing_sw": "scan southwest",
    "scan_bearing_w": "scan west",
    "scan_bearing_nw": "scan northwest",
    "scan_clock_8": "scan eight o'clock",
    "scan_clock_9": "scan nine o'clock",
    "scan_clock_10": "scan ten o'clock",
    "scan_clock_11": "scan eleven o'clock",
    "scan_clock_12": "scan twelve o'clock",
    "scan_clock_1": "scan one o'clock",
    "scan_clock_2": "scan two o'clock",
    "scan_clock_3": "scan three o'clock",
    "scan_clock_4": "scan four o'clock",
    "report_all": "report all contacts",
    "report_bearing_n": "report contacts to the north",
    "report_bearing_ne": "report contacts to the northeast",
    "report_bearing_e": "report contacts to the east",
    "report_bearing_se": "report contacts to the southeast",
    "report_bearing_s": "report contacts to the south",
    "report_bearing_sw": "report contacts to the southwest",
    "report_bearing_w": "report contacts to the west",
    "report_bearing_nw": "report contacts to the northwest",
    "report_clock_8": "report eight o'clock",
    "report_clock_9": "report nine o'clock",
    "report_clock_10": "report ten o'clock",
    "report_clock_11": "report eleven o'clock",
    "report_clock_12": "report twelve o'clock",
    "report_clock_1": "report one o'clock",
    "report_clock_2": "report two o'clock",
    "report_clock_3": "report three o'clock",
    "report_clock_4": "report four o'clock",
    "watch_nearest": "watch the nearest contact",
    "watch_nearest_air_defence": "watch the nearest air defence",
    "cancel_task": "cancel the current task",
    "cancel_scan": "stop scanning",
    "cancel_watch": "stop watching",
}
```

**Three things to weigh, and the third is the one that is easy to get wrong:**

1. **It is mostly slot-taking commands spelled out as separate tokens** — eight bearings and nine
   clock hours, twice over (scan and report). That is why `main`'s set is "no-slot": the narrow set
   is not a subset of this one minus some commands, it is a different design, one that keeps slot
   extraction out of the model's job entirely.
2. **Widening costs nothing structurally.** The body-side D10 validator is the authority on
   legality either way (`belief/brain_reply.py`), and `_validate_confirm` checks the offered
   vocabulary *and* `dispatched_command_tokens`, so a wider offer cannot dispatch something body
   does not already implement. `implementation.md` item 4 makes exactly this point.
3. **Widening is not free in latency, and this is measured.** The duplicate branch's own
   implementer memory recorded classify at a mean of 132 ms against *this* 44-token table, versus
   D6's 38–63 ms figure taken on a minimal bare-candidate probe — and attributed the gap to prompt
   eval over the fuller command table. So "more tokens is free because the validator catches
   anything illegal" is true about *safety* and false about *cost*. That measurement, and the rest
   of the branch's findings, are harvested into
   `.claude/agent-memory/implementer/project_br1_stage2_duplicate_branch_findings.md`.

**Unblock condition:** a real sortie where the pilot's phrasing misses the 7-token set — `BR-1.2`
is `#needs-flight` precisely to learn that. Do not widen speculatively before then; the whole
reason `main` narrowed it was that nobody had flown either version.

#status/open #needs-flight
