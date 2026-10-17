# Security Deep Analysis: BL-8 Mission Memory (batch: Stages 1, 2, 3, 5)

Branch `feature/bl8-mission-memory`, tip `258ac6c222f202b1b3ae7f88fe4572fec6c524cd`.
Worktree HEAD started at `24f217fc` (44 commits behind); `git merge --ff-only 258ac6c2`
fast-forwarded cleanly onto a clean tree.

Scope as given: `body-layer/src/mission_memory/` (all seven modules), `src/logger.py`'s wiring,
`belief/tool_api.py`'s `TOOL_SET` extension, the `--mission-memory PATH` CLI flag. Stages 4 and 6
are not built; their absence is confirmed by reading, not treated as a finding.

### Dependency Status

No dependency change. No new import outside the stdlib + existing world-model/belief seams.

### What was read

All seven `mission_memory/` modules in full (`entries.py`, `store.py`, `admission.py`, `marks.py`,
`query.py`, `tools.py`, `log.py`), the `logger.py` wiring (`_mission_memory_step`,
`_mark_here_fn`/`_mark_target_fn`, `_resolve_mission_memory_log_path`, the `--mission-memory`
`parser.error` gating), `belief/tool_api.py`'s `TOOL_SET` registration, `crew_console.py`'s
`handle_command` dispatch for `mark_here`/`mark_target`, and the plan, implementation log and both
Reviewer passes (`plan.md`, `implementation.md`, `review.md`). Independently re-ran the full test
suite (2162 passed, 4 xfailed — matches both Reviewer passes and the implementer's reports).

### Examined per the task's five points

1. **The new file write (`log.py`, `_resolve_mission_memory_log_path`).** The path comes from the
   CLI flag — operator-supplied, same trust level as every other `--*-log`/`--mission-memory`
   sibling (`_resolve_group_trace_log_path` etc.) already in this codebase; this is not a new
   pattern. `expanduser()` then `per_run_log_path(...)` then `mkdir(parents=True, exist_ok=True)`,
   with `OSError`/equivalent caught and reported once — mirrors the sibling exactly. **The JSONL
   framing cannot be broken by entry content**: `log.py:37` writes
   `json.dumps(encode_entry(entry), default=str) + "\n"`. `json.dumps` escapes embedded `\n`/`\r`
   in any string field (including a landmark phrase or a label) to `\n`/`\r` *inside* the JSON
   string, never emitting a literal newline — a debrief parser reading one `json.loads` per line
   cannot be desynchronised by entry content, long or short. Checked by reading `json.dumps`'
   documented behaviour and confirming no custom separators/`ensure_ascii=False` override that
   would change it; none exists here.
2. **Input provenance into the store.** Landmark phrases (`EntryPosition.landmark`) are frozen at
   write time from `enrichment.semantic_facts_for`'s existing near-fact radius (Decision 9) — the
   same gated vocabulary `describe_our_position` already surfaces today, not new free text. The
   one genuinely free-form field is `MarkPayload.label`. Traced where it can originate: the
   pilot-voice path (`crew_console._handle_mark_here`/`_handle_mark_target`, via
   `mark_here_fn: Callable[[float], str]`/`mark_target_fn: Callable[[str, float], str]`) **never
   supplies a label at all** — those closures (`logger.py:1549`, `:1571`) call `marks.mark_here`/
   `marks.mark_target` with no `label` argument, consistent with Decision 6's scope note that the
   richer mark forms need open-vocabulary speech not yet built. The only call site that can set a
   non-`None` label today is `mission_memory.tools.remember_location`'s own `label` parameter —
   see point 3, where this matters.
3. **`TOOL_SET` 15 → 17 and `remember_location`.** Confirmed, by grep and by reading
   `belief/brain_reply.py`/`belief/escalation.py`, that **no code anywhere in the repo calls a
   `ToolSpec.fn` generically** — `TOOL_SET` is a registered-but-undispatched surface as of this
   batch (the implementer's own agent-memory note,
   `.claude/agent-memory/implementer/project_tool_set_has_no_dispatcher_yet.md`, states this and I
   independently re-ran its grep: `grep -rn "tool_api\|TOOL_SET" brain-layer/ body-layer/src/
   logger.py body-layer/src/belief/brain_client.py body-layer/src/belief/brain_reply.py` returns
   nothing). The brain-seam that exists and executes today is `escalation.py`'s structured-reply
   path (`pick`/`confirm`/`unable`/`ask`), validated by `brain_reply.validate_brain_reply`, which
   `remember_location`/`recall_memory` are not part of. **So the exposure this point asks about is
   real but not yet live**: once a dispatcher reads `TOOL_SET` and lets the brain call
   `remember_location(..., label=...)`, the brain fully controls `label`'s content and length with
   no validation at any layer between the tool call and the JSONL write — no length cap, no
   character filtering, nothing resembling `brain_reply.py`'s validation discipline for the
   structured-reply path. The concrete risks at that point: unbounded growth of the store/log file
   from a confused or looping model, and a self-referential context-amplification path (a label
   written now is read back by `recall_memory`/`get_contact_history` as brain context later,
   potentially re-presenting a hallucination to the model as a standing fact with no code-side
   check that it was ever true). This is not externally-triggerable prompt injection today — the
   label's author and reader are the same brain process, and DCS-originated text reaching `label`
   has no path (every other field source is the bounded `OP_*`/cardinality vocabulary) — but it is
   exactly the gap a dispatcher implementation will inherit silently if nobody is told to look. Not
   a required fix now, because there is no live call path to fix against (there is nothing to
   exploit) — filed below, same shape as the `BL-B35` precedent (fix-when-reachable, not fix-now).
   Index exhaustion on the mark counter (`_next_mark_index`) is not a real concern: a plain Python
   `int`, unbounded by the interpreter; unlimited appends at today's volumes (plan's own estimate,
   ~3600/sortie worst case) cost memory and disk, not correctness.
4. **Resource exhaustion on the poll thread.** `_mission_memory_step` (`logger.py:1525-1536`)
   wraps the entire `admission.step(...)` call in `try: ... except Exception: logger.exception(...)`
   — a disk-full or any other write failure during the observed-entry path is caught, logged, and
   the poll loop continues; `log.MissionMemoryLogWriter.write` additionally disables itself once on
   the first `OSError` and reports to stderr, so a failing sink does not retry into every future
   poll. This matches Decision 8's "a memory write never kills the poll loop" claim for the
   admission path, and the Reviewer's fix round independently re-ran the mutation test confirming
   the `except ValueError` guards inside `_build_entry_position`/`_mark_position` are real.
   **One asymmetry, not a regression**: the commanded-mark path (`crew_console.handle_command`'s
   `mark_here`/`mark_target` tokens, dispatched from `_poll_f10_commands`'s per-command loop at
   `logger.py:1858-1861`) has no per-command try/except around the dispatch call itself, so an
   exception inside `marks.mark_here`/`marks.mark_target` (e.g. from `semantic_facts_for`, which is
   not wrapped in a `try` the way `dcs_to_wgs84` is) would propagate and could kill that poll
   iteration. Checked whether this is a new exposure BL-8 introduces: it is not — every other
   dispatched token in `handle_command` (`select_target`, `engage`, `describe_our_position`, …) is
   equally unwrapped at this call site, and `semantic_facts_for` is already reachable from this
   same unwrapped dispatch today via `tools.describe_our_position`. BL-8 adds two more callers of
   an already-exposed function under an already-existing posture; it does not create a new failure
   mode. Not filed as a BL-8 finding for that reason — pre-existing, project-wide dispatch posture,
   out of this batch's scope to fix.
5. **No ground truth, ever (Decision 8).** Read both `admission._build_entry_position` and
   `marks._mark_position`: both derive `lat`/`lon` exclusively from `dcs_to_wgs84(theatre,
   <believed x>, <believed z>)` where `x`/`z` come from `PositionEstimate`/`contact.position` (the
   fused belief), never from a DCS object id or `Observation.derived_world_position`. Both catch
   `ValueError` to `None`. No construction site anywhere in `mission_memory/` reaches for a
   ground-truth field — confirmed by grep (`grep -rn "derived_world_position\|getLife\|LoGetWorld"
   src/mission_memory/` returns nothing) and by the import-direction test, which independently
   confirms `mission_memory` cannot even see `detection_trace_writer.py`'s ground-truth-holding
   code (different package, no import edge). `detection_trace_writer.py` remains the sole sanctioned
   exception, undisturbed.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `src/mission_memory/tools.py:55-108` (`remember_location`) | Unbounded free-form `label: str \| None` parameter, no length/content validation, forming the brain's write path into a store later read back as brain context | Real gap, but **not currently reachable** — `TOOL_SET` has no dispatcher (confirmed by grep); becomes live only when brain-tool dispatch is built | Filed as `BL-B79` — fix when the dispatcher lands, not before |
| `src/mission_memory/log.py:36-37` | `json.dumps(...) + "\n"` per entry | JSONL framing cannot be broken by entry content (newlines escaped inside the JSON string) | None — false-positive-shaped concern, resolved by reading `json.dumps`'s behaviour |
| `logger.py:1858-1861` (`_poll_f10_commands`'s dispatch loop) | No per-command `try/except` around `handle_command`, so an exception in `marks.mark_here`/`marks.mark_target` (via `semantic_facts_for`) would propagate | Pre-existing project-wide posture — every other dispatched token is equally unwrapped, and `semantic_facts_for` is already reachable from this same unwrapped call site via `describe_our_position` | None — not a BL-8 regression, out of this batch's scope |
| `admission.py` / `marks.py` `dcs_to_wgs84` call sites | `except ValueError` around the one call that could raise from an unregistered theatre | Correct and tested (Reviewer's fix round independently re-ran the mutation test) | None |
| `mission_memory/*.py` | No ground-truth field reachable (Decision 8) | Confirmed by grep and by the import-direction structural test | None |

### Verdict

**APPROVED, with one backlog item filed: `BL-B79`** (`body-layer/ROADMAP/BL-B79.md`, next unused
number per `ls body-layer/ROADMAP/ | grep -oE '^BL-B[0-9]+' | sort -V | tail -1` → `BL-B78`, so
`BL-B79`). Reasoning for fix-when-reachable rather than fix-now: `remember_location`'s `label`
parameter has no live caller anywhere in this repo today (`TOOL_SET` is registered but
undispatched, independently re-confirmed by grep), so there is no exploitable path to fix against
yet — filing it now means whoever builds the brain-tool dispatcher inherits a named requirement
(bound `label`'s length, consider whether a model-authored memory entry should be flagged as such
on read-back) instead of a silent gap discovered later the way `BL-B35`'s unbounded
`response.read()` was.

No required fixes. Nothing else found rises above a documented false-positive or a pre-existing,
project-wide posture already accepted elsewhere in this codebase.
