# Performance Review: BL-8 Mission Memory, Stages 1, 2, 3, 5

Branch `feature/bl8-mission-memory`, tip `258ac6c222f202b1b3ae7f88fe4572fec6c524cd` (HEAD started
at `24f217fc`, fast-forwarded cleanly onto a clean tree).

Scope: `body-layer/src/mission_memory/` (`entries.py`, `store.py`, `log.py`, `admission.py`,
`marks.py`, `query.py`, `tools.py`), the wiring in `body-layer/src/logger.py`
(`_mission_memory_step`), and the additions to `body-layer/src/belief/tool_api.py`
(`get_contact_history_with_memory`). No DCS/live sortie available — every figure below is either
read directly off the code (bounds, call sites) or reasoned from the plan's own stated worst-case
volumes (~3600 entries / 2-hour sortie), and I say which for each claim.

## 1. Per-poll cost of `_mission_memory_step` (the common case: nothing written)

`_mission_memory_step` → `admission.step` iterates `contacts.contacts` once (bounded by tracked
contact count, ~30 per the plan's own estimate) and calls `_maybe_write_entry_for_contact` for
each. Two things happen **unconditionally**, before any write-gate gets a chance to say no:

- `_composition_for`/`_motion_info` build a small dataclass per contact — pure Python, no I/O,
  negligible at ~30 contacts.
- `memory.latest_entry(contact.id)` is called for every nameable/air-defence contact, every poll,
  purely to check the `RESIGHT_MIN_INTERVAL_S` gate — **this is the one real cost driver**, below.

`memory.latest_entry` is **not O(1)**, and the store's own docstring says so
(`store.py:98-108`): the `_latest_live` dict gives the target `seq` in O(1), but resolving that
seq to its `Entry` object walks `reversed(self._entries)` until it finds a match. For a contact
whose last entry is recent, this is cheap. For a contact that stopped changing early and is never
re-written again, the scan depth grows with every entry written by *every other contact* since
then — worst case, a scan over the whole log, once per poll, for as long as that contact stays
tracked.

**Reasoned, not measured**: at the plan's own stated worst case (~3600 entries over a 2-hour
sortie, ~30 tracked contacts), if a handful of those contacts go "stale" early and are never
rewritten, each poll could scan deep into a multi-thousand-entry list for each of them. At a
plausible 1–2 Hz poll rate over 2 hours (7200–14400 polls), this is the kind of cost that grows
with sortie length and entry count together, not a fixed per-poll constant.

**Action: MONITOR, not NOW.** The store's own docstring already names the correct mitigation
(`"add a seq -> Entry index alongside _latest_live"`) and explicitly defers it until the estimated
volume stops holding. I agree with that call: at ~3600 entries worst case the absolute cost is
still small (thousands of pointer comparisons, not millions), and the admission thresholds
themselves are explicitly uncalibrated pending Sortie A (plan "Risks & Unknowns") — building the
index now would be optimizing against a number nobody has measured yet. **Watch for**: if Sortie A
or later tuning pushes `RESIGHT_MIN_INTERVAL_S` down (more entries) or sortie duration well past
two hours, re-measure `latest_entry`'s actual scan depth before accepting a second order-of-
magnitude increase in entry count on faith.

## 2. The write path — is this BL-B32 again?

No, and it's worth saying why not, since the dispatching prompt named that precedent explicitly.
BL-B32 was `POST /speak` synthesizing TTS **synchronously inside the poll body, on every spoken
callout** — a high-frequency path (every utterance) with an expensive-and-variable per-call cost
(speech synthesis). `MissionMemoryLogWriter.write` is a single `open(path, "a")` / one-line
`json.dumps` + `write` / implicit close, called **only when an entry is actually appended** — and
appends are already rate-limited to the same handful-to-tens-per-sortie volume the admission rules
enforce (§1's gates, plus `FIRED_ON_FOLD_WINDOW_S` for `fired_on`, plus pilot-command-rate for
`mark`). This is the same shape as the existing, already-accepted `speech_log.SpeechLogWriter`
pattern, not a new instance of the TTS defect class.

The sink **does** run synchronously inside the poll thread's call stack (`store.append` releases
its lock before calling `sink(entry)`, but the call itself is still on the poll thread, still
inside `_mission_memory_step`'s try/except). A slow or hung disk would still stall that poll for
the duration of one `open`/`write`/close. Given the write rate (tens per sortie, not per poll),
this is an acceptable risk at the same level the pre-existing `speech_log` sink already carries —
not a regression this feature introduces.

**Failure path checked and confirmed inexpensive**: `log.py`'s `write` catches `OSError`, sets
`self._disabled = True`, prints one line to stderr, and returns — every subsequent call is a
single `if self._disabled: return` with no further I/O attempted. Read directly
(`mission_memory/log.py:33-44`); matches the plan's stated disable-once-and-report requirement.
No per-poll cost once disabled.

**Action: none.** No fsync, no per-write flush beyond the implicit close; correctly bounded by
admission-rule throughput, not poll rate.

## 3. In-memory store growth

Append-only `list[Entry]`, never truncated, plus two small dicts (`_struck_by`, `_latest_live`)
bounded by entry/contact count respectively. At the plan's own worst-case ~3600 entries, this is a
few thousand small frozen dataclasses — negligible memory, no read path walks the *whole* history
on the poll thread (confirmed in §1 — the one poll-thread read, `latest_entry`, is seq-indexed,
not a `kind`/`belief_ref` scan over everything).

`recall_memory` (`query.py:58-97`) is an O(all entries) linear scan with a `.sort()` after —
explicitly a brain-facing call, never invoked from `logger.py`'s poll loops (confirmed: `query.py`
and `tools.py` are not imported in `logger.py` at all; only `admission.py`/`marks.py` are,
per the grep below). `chain_for` (`query.py:47-55`) is the same shape, filtered by `belief_ref`
rather than radius. Both are trivially fast at ~3600 entries (a linear scan over a few thousand
small objects is microseconds), so even though they are O(n), n is small enough that this doesn't
matter at the stated volumes.

```
$ grep -n "^from mission_memory\|^import mission_memory" body-layer/src/logger.py
from mission_memory.admission import FiredOnTracker
from mission_memory.entries import MarkPayload
from mission_memory.log import MissionMemoryLogWriter
from mission_memory.store import MissionMemory
```

`query.py`/`tools.py` do not appear — the poll-thread/brain-thread separation the plan requires
actually holds in the code, not just in the design doc.

**Action: none.** `get_contact_history_with_memory` (`belief/tool_api.py`) is the same
brain-facing, off-poll-thread shape — it calls `query.chain_for` for one contact's chain, merges
it with the existing belief-side history, all still O(total entries) at worst but still off the
hot path and at the same small n.

## 4. The query surface's thread separation — confirmed, not assumed

Covered above: `query.py` and `tools.py` have zero `belief` import and are never imported by
`logger.py`. The design's stated separation ("the poll thread must never scan the log") holds by
construction, verified by grep rather than taken on the plan's word.

## 5. Admission rules — the pathological-jitter case

Checked both `_write_group_entry` and `_maybe_write_air_defence`: the `RESIGHT_MIN_INTERVAL_S`
gate (`if now_sim - last_entry.t_sim < RESIGHT_MIN_INTERVAL_S: return`) is checked **before** any
material-change evaluation and is per-contact, keyed only on wall/sim time since that contact's
*own* last entry — it does not care how many times the material-change predicate would have fired
in between. So however hard position belief jitters near the `RESIGHT_MOVE_M` boundary, or however
often composition flaps across the `GROUP_ENTRY_CONFIDENCE_FLOOR`, **one contact can never write
more than one entry per `RESIGHT_MIN_INTERVAL_S`**. This directly bounds the worst case to the
plan's own arithmetic (tracked-contacts × sortie-duration / `RESIGHT_MIN_INTERVAL_S`), confirmed
by reading rather than assumed from the plan's prose.

`fired_on` has the equivalent per-shooter gate (`FIRED_ON_FOLD_WINDOW_S`), and `mark` is bounded by
human input rate (trivial). No admission rule can produce an unbounded or super-linear entry count
from jitter alone — the "thousands of entries" pathological case the task asked me to look for
does not exist in the current gate structure, **provided the tuning constants stay within their
declared `lo`/`hi` bounds** (`RESIGHT_MIN_INTERVAL_S` ∈ [5, 600]s). At the floor of that range
(5s), worst case becomes ~30 contacts × (7200s / 5s) ≈ 43,200 entries in a 2-hour sortie — still a
linear, not super-linear, function of tuning, and still small in absolute memory/CPU terms, but
worth flagging since it's an order of magnitude above the plan's own ~3600 estimate and would push
§1's `latest_entry` scan-depth concern from "probably fine" to "worth measuring."

**Action: MONITOR.** No code change requested — the bound already holds structurally. Note for
whoever runs Sortie A: if `RESIGHT_MIN_INTERVAL_S` gets tuned toward its floor, re-check §1's
`latest_entry` cost at the resulting entry volume rather than assuming the ~3600 estimate still
applies.

## 6. `pyproj`/`dcs_to_wgs84` cost

Confirmed `_build_entry_position` (admission.py) and `_mark_position` (marks.py) are only called
**after** the write-gates have already decided to write — not once per contact per poll
unconditionally. So the projection call's rate matches the write rate (§1/§5's bound), not poll
rate. Matches the plan's own "Risks & Unknowns" note that this would be a problem at per-poll
rates and isn't at per-entry rates — confirmed by reading the call sites, not assumed.

## Verification

```
cd body-layer && /path/to/main-checkout/body-layer/.venv/bin/python -m pytest -q
```

Run from inside this worktree's `body-layer/` (so pytest's rootdir/pythonpath resolve to this
worktree's source, not the main checkout's), using the main checkout's venv interpreter (this
worktree has no `.venv`, as every prior pass in this feature reported). Result: **2162 passed, 4
xfailed** — matches the Reviewer's and both Implementer passes' reported state exactly.

## Verdict

**APPROVED — MONITOR.**

What to watch, and where:
- `mission_memory/store.py`'s `latest_entry` (§1): its own docstring already names the fix
  (a `seq -> Entry` index) and the condition for needing it (entry volume growing past the
  ~3600/2-hour estimate, or sortie length growing well past two hours). Re-measure before Sortie A
  results are in if `RESIGHT_MIN_INTERVAL_S` gets tuned down materially (§5).
- No code change requested. The write path, the thread separation, and the admission-rule bounds
  all hold up under reading, not just under the plan's own claims — I independently confirmed the
  poll-thread/brain-thread split by grep rather than trusting the design doc, and independently
  derived the jitter-worst-case bound by reading the gate order rather than assuming it from the
  plan's prose.
