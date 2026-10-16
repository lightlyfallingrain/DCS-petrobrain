## Security Deep Analysis: bl-b76-tripwire

**Verified against an isolated snapshot, not a merged worktree.** This worktree's HEAD
(`a5082adf`) and the target tip `e6a77d8e619519d457b6f6f4986fcc3a28adbf0e` have diverged
(neither is an ancestor of the other — `git merge-base --is-ancestor` false both ways), so per
protocol this stops short of merging. Verified instead via
`git archive feature/bl-b76-tripwire-rejected | tar -x -C /tmp/.../bl-b76-snapshot` and
`git diff 95ef7982 e6a77d8e619519d457b6f6f4986fcc3a28adbf0e`. Checks (ruff/mypy/pytest) were not
re-run here — no `.venv` in this worktree and no clean checkout of the tip to run them against;
taking the stated tip results (clean format/lint, mypy --strict clean, 2061 passed/4 xfailed) as
given, consistent with Reviewer's two passes on this branch.

### Dependency Status

No dependency change. The only new import is `belief.decay.OBJECT_ID_MEMORY_S`, an existing
constant from this same subproject, imported into `belief_truth_log.py` for the first time.

### Scope confirmed by diff

`git diff 95ef7982..e6a77d8e --stat` touches exactly: `body-layer/src/belief_truth_log.py`,
`body-layer/tests/test_belief_truth_log.py`, three `plans/bl-b76-tripwire/*.md` files, and one
`docs/acceptance/...object_permanence...md` note — nothing else. `perception/visibility.py`,
admission (`perception/source.py` gate chain), `Contact`, and `belief/attack_run.py` are all
**untouched**. The new cache is populated and read entirely inside `BeliefTruthLogWriter`
(a log writer, constructed only when `--belief-truth-log` is passed — see `logger.py:1536-1541,
1844`) and nothing it computes is read back by any belief/perception/attack-run code — it feeds a
JSONL row, not a decision. This is a measurement, confirmed by diff rather than by the docstring's
own claim, and no-omniscience is not affected.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `belief_truth_log.py:280-281` (new `_object_id_to_contact_id`/`_object_id_last_seen_sim` dicts) | Unbounded-looking accumulator | Entries are only ever **overwritten** per `object_id` (never appended), so size is bounded by the count of *distinct* DCS `object_id`s ever admitted in the process lifetime — the mission's ground-unit population, not elapsed time or poll count. `_object_ids_for_contact` filters stale entries on *read* but never evicts them from the dict on write, so a unit that despawns keeps one stale entry (two floats + one string) forever. For this project's actual object population (naked-eye-admitted ground units in one sortie) this is immaterial — not a meaningful growth path, and not a new failure mode: `belief.decay`'s own `object_id_continuity_valid` uses the identical "bound on read, not on write" shape against `Contact.last_seen_sim`. | None required. Low-risk, pre-existing pattern reused, not introduced. |
| `belief_truth_log.py:666-668` (`now_sim - last_seen_sim <= OBJECT_ID_MEMORY_S`) | Sim-time assumed monotonic | If `now_sim` ever regresses (DCS mission restart within the same running body-layer process, without the process itself restarting), a negative `elapsed_s` is `<=` the window and a stale mapping reads as fresher than it is. No code anywhere in `logger.py`'s poll loop detects or resets on a mission restart — `self.store.ingest`/`self.tasks.tick` make the same monotonic assumption with `ownship.t_sim` project-wide, and `belief/decay.py:383-399`'s `object_id_continuity_valid` has the exact same shape against `Contact.last_seen_sim`. This is a systemic assumption this feature inherits, not one it introduces or worsens — the blast radius if it fires is also systemic (every decay/continuity check in the belief layer), not specific to this tripwire row. | None required for this feature specifically. Worth a `todo/backlog` entry for the whole-codebase assumption if the user wants it tracked, but out of scope for this change. |
| `belief_truth_log.py:437,586-600` (`_update_object_id_contact_cache` call and the new rejected-row lookup loop), both ahead of the `try: ... except OSError` around the `json.dumps`/`write` call | Code that can raise sits outside the module's one `_fail`-on-write-failure boundary | Both new blocks are pure in-memory dict/set operations on data already validated by `DetectionTraceCollector`/`observation_id_to_contact_id` (existing, reviewed code) — no I/O, no external input parsing, no arithmetic that can raise (`entry.object_id`/`entry.outcome`/`entry.t_sim` are all plain attributes on an already-constructed dataclass). I could not find a code path that raises here; this is a structural observation, not a found exploit. If a future change adds anything here that *can* raise (e.g. a parse of external data), it would escape `_fail`'s "disable the log, don't kill the sortie" contract and crash the poll loop — worth remembering for whoever touches this method next. | None required now. |
| `belief_truth_log.py:605-620` (new `outcome`/`gate_outcome` fields in the JSONL row) | New data written to disk | `outcome` is one of three fixed string literals (`"admitted"`/`"rejected"`/`"absent"`); `gate_outcome` is `GateOutcome.value`, a closed enum (`"terrain_los"`, `"range_or_size"`, `"cockpit_mask"`, `"gaze"`, `"optic_fov"`, `"forest"`, `"player_bubble"`). No externally-influenced string or path ever reaches this writer — nothing here is attacker- or mission-author-controlled in a way that differs from what `present_in_snapshot`/`join_skew_s`/`live_los_clear` already wrote before this change. | None required. |

### No new dependency, no new disk path

The log still writes to the one path already resolved by `logger.py` (`--belief-truth-log`,
unchanged). No new file, socket, subprocess, or external-process call was added.

### Verdict

**APPROVED.** No material exposure. This is a logging-only widening of an existing sortie-log
writer: it adds an in-memory `object_id -> contact_id` join cache with the same
eviction-on-read-only shape the codebase already accepts elsewhere (`belief.decay`), writes three
new closed-vocabulary string/enum fields to an existing JSONL file, and does not feed anything back
into perception, admission, `Contact`, or attack-run decision logic — confirmed by diff, not by
the docstring's claim. Context: single-user, LAN-only project under active development; nothing
here is reachable from untrusted input.

### Required Fixes (if any)

None.
