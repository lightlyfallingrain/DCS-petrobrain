## Security Deep Analysis: BL-12 — Group-level contact identity and continuity

Reviewed at `33da5b4` (fast-forwarded from a stale worktree base; see Address note below),
`main..feature/bl12-group-contact-identity`, ~25 commits. Source surface: `body-layer/src/belief/
{groups.py,contacts.py,position_belief.py,association_over_time.py,speech.py,decay.py,
classification.py}`, `body-layer/src/{group_trace_log.py,logger.py}`.

### Address

HEAD at dispatch was `cb39159` (strict ancestor of `33da5b4`, clean tree) — fast-forwarded with
`git merge --ff-only 33da5b4`. Confirmed at tip: `33da5b4`.

### Dependency Status

**No new dependency.** `git diff main..HEAD -- '*/pyproject.toml'` is empty. Confirmed independently
of the task statement.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `group_trace_log.py:42-76` | New file writer on sortie path, `--group-trace PATH` | Path comes from the operator's own CLI argument (same trust level as `--speech-log`/`--detection-trace`, not externally-influenced data). Resolution (`logger.py:_resolve_group_trace_log_path`) expands `~`, stamps per-run, creates parent dirs, and degrades to `None` on any of `_RESOLVE_FAILURES` rather than raising — identical posture to `speech_log.py`/`detection_trace_writer.py`. `write()` catches only `OSError`, sets `_disabled=True`, and never re-raises; the caller (`ContactStore.tick`'s `group_trace_sink` call, `contacts.py:1655`) is not wrapped in try/except by design (per the module's own docstring) but the writer itself cannot propagate, so a full disk or unwritable path degrades the log, never the poll loop. Rows are plain dicts of floats/strings/short tuples (`now_sim`, `phase`, `group_id`, `member_contact_ids`, `centroid_x/z`, `extent_m`, `composition`) serialized with `json.dumps(..., default=str)` — no circular references, no attacker-influenced content that gets later interpreted (it is read-only debug JSONL, never re-parsed by this codebase). | None — matches the accepted posture of the other three sortie logs. |
| `groups.py:1026` (`confidence = math.hypot(...) / len(history)`) | Division | Guarded: only reached when `len(history) >= _MIN_HEADING_SAMPLES` (line 1021-1022 returns early otherwise). History itself is capped at `GROUP_HEADING_SMOOTHING_WINDOW` via slicing (line 1020) — bounded, not unbounded growth. | None |
| `groups.py:923` (`_centroid_uncertainty_of`), `:908` (`_centroid_of`) | `statistics.fmean` over `members` | Only ever called on a `cluster`/`members` sequence that already passed `_cluster_contacts`'s `min_members` (`GROUP_REPORTING_MIN_MEMBERS`) floor — empty or too-small sequences are dropped before these are reached (line 777, `if len(contacts) < min_members: ...` short-circuit). No empty-sequence `StatisticsError` path reachable. | None |
| `position_belief.py:330-338` (`Covariance2D.inverse`) | Division by `determinant` | Explicit floor (`floor = max(_MIN_DETERMINANT_RATIO * trace², _MIN_DETERMINANT_ABSOLUTE)`) applied before dividing — cannot reach zero. | None |
| `position_belief.py:638-646` (`_apply_floor`) | Division by `current_trace` | Explicit `if current_trace <= 0.0` branch floors to an isotropic split instead of dividing — documented as guarding a "should not arise from any real declared sigma" degenerate case. | None |
| `position_belief.py:413-433` (`bearing_uncertainty_deg`) | `atan2`/division by `slant_m` | `if slant_m <= 0.0: return 0.0` guard before the division. | None |
| `contacts.py:1102` (`fold_displacement_m +=`) | Unbounded-looking accumulator | Resets to `0.0` on every unambiguous resolution (continuity match or single passing candidate, lines 1071/1086); only accumulates across repeated *ambiguous* folds of the same contact. Worst case (an isolated case of a contact continuously ambiguous for an entire sortie) grows a float that only ever makes the admission gate *more conservative* (`_cluster_contacts`'s admission test only ever widens the required gap, per that function's own docstring) — never forces a merge, never a crash, never an eviction by itself. Not a security finding; a gameplay-fidelity edge case already named in the module's own comments. | None |
| `groups.py` `remembered_groups` | Retention across ticks | Bounded by `GROUP_REIDENTIFY_WINDOW_S` — a group matching no cluster is kept only while `now_sim - last_observed_sim <= GROUP_REIDENTIFY_WINDOW_S`, dropped past that. Not unbounded growth across a long sortie. | None |
| `logger.py:1434,1759,2620` (`except KeyboardInterrupt: pass`) | Error suppression | Pre-existing (present on `main`, unrelated to this feature's REPL/poll-loop entrypoints) — matches the 2026-10-05 audit's flagged set (7 total swallowed exceptions project-wide; unchanged count). Not a BL-12 finding. | None |

No new `type: ignore`, no new bare `except`, no new cross-subproject import, no new `print()` in
`belief`/`perception` core, `BINOCULAR_RANGE_MULTIPLIER` still retired — `/invariant-check` all
PASS except the two pre-existing WARN categories (7 swallowed exceptions, 4 `type: ignore`), byte-
identical in count to the prior audit. `/security-grep` surfaces nothing new in the BL-12 source
surface beyond the file-write hit already assessed above; the "DCS mission-scripting bridge" and
"reads sized by remote input" categories are entirely aircraft-layer/audio-adapter/brain-layer,
untouched by this feature.

### `BL-B59` exposure — bounded and visible, but not fully bounded

Confirmed the mechanism independently (not re-litigating the decision to defer the fix):

- **`belief/callouts.py`'s observability gate filters `CONTACT_DETECTED`/`CONTACT_REACQUIRED`
  events out of the push-candidate pool when the contact is currently grouped** (surfacing instead
  as the group's own disclosure line) — but **`CONTACT_CLASSIFICATION_CHANGED` is explicitly *not*
  filtered by group membership** ("every remaining kind still competes and speaks exactly as it
  does today, grouped contact or not", `callouts.py` module docstring). So a contact's own first
  identification as air defence is spoken individually *regardless* of whether it is, was, or later
  becomes grouped — eviction happening *after* that individual disclosure already reached the pilot
  does not retroactively un-speak it.
- **`CONTACT_ENGAGEMENT_CHANGED` ("Danger, …") is keyed on `Contact.classification` and ownship
  geometry alone** (`contacts.py:1540`, `envelope_for(contact.classification)`), gated only on the
  contact's own `is_watched` attention state (`current_attention in ("watch", "priority")`,
  `contacts.py:1449`) — not on group membership. An evicted air-defence contact that is individually
  watched keeps generating its own engagement warnings untouched by the eviction.
- **The group's own aggregate disclosure line** (composition, `air_defence_composition`, the
  threat-leading member chosen by `_leading_index`) is what actually loses the evicted member —
  this is the real, narrower content of the defect: the *group-level* summary becomes wrong, not a
  total silencing of the contact.
- **An evicted contact remains individually queryable.** It becomes ungrouped, and
  `CrewConsole._handle_report`'s own fallback explicitly still covers "contacts a real
  `belief.groups.Group` does not cover" via `group_facts`/`render_group_report` — a player-initiated
  `report` reaches it.
- **Visible in `--group-trace`.** Every reconcile call that still matches a group via `overlap` or
  `property` emits a trace record carrying that tick's *current* `member_contact_ids` and
  `air_defence_composition` (`groups.py:1468-1479`) — a consecutive-tick eviction shows up directly
  as a shrinking roster / disappearing `air_defence_composition` entry for the same `group_id`, with
  no reconstruction needed. This matches `BL-B59`'s own claim that the trace line makes it directly
  observable, and I confirm that claim against the actual `reconcile` code rather than taking it on
  trust.

**Net assessment:** the defect is **visible** (post-sortie, via `--group-trace`) and **partially
bounded** by two independent individual-disclosure channels (classification-change speech, and
watched-contact engagement warnings) that do not depend on group membership and are therefore
unaffected by eviction *once they have already fired*. It is **not fully bounded**: if an
air-defence contact is absorbed into a group and evicted again before its own individual
`CONTACT_CLASSIFICATION_CHANGED` is ever spoken (e.g. suppressed by the merge-echo or
`_already_reported_member_ids` redundancy logic, or simply not yet reached in the scheduler's
at-most-one-per-poll cadence) and the player has not explicitly watched it, the group's aggregate
line is the only channel that would have mentioned it — and that is exactly the channel the defect
breaks. This matches the roadmap's own characterization ("suppresses a report rather than
fabricates one") and is consistent with why the user prioritised it next rather than accepting it
as adequately mitigated. Not a new finding — confirms the existing `BL-B59` entry is accurately
scoped, with the trace-visibility claim independently verified against the code.

### Verdict

**APPROVED.**

No exploitable vulnerability in the feature diff. The one new I/O surface (`--group-trace`) matches
the accepted posture of the three existing sortie logs; every arithmetic path that could in
principle divide by zero or recurse unboundedly is guarded or bounded by an existing floor/window.
`BL-B59` is a known, already-disclosed correctness defect (not introduced by this review, not
re-litigated here) whose exposure is visible in the sortie trace and partially — not fully —
mitigated by channels independent of grouping.

### Required Fixes

None.
