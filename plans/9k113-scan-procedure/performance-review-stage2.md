### Performance Review

Batch reviewed: BL-B89 Stage 2 (`look`/`sight`/`what is [at] <where>`, `8f5d2ade..627ab398`) plus
the carried-over `[[BL-B98]]` fix (`01a6fadd`, folded into Stage 1, both passes waived there by
user direction — see `plan.md`'s "Performance and security debt carried into this stage"). Tip
reviewed: `627ab398b074b308f90ba4ec023edb765ecdd25e`. Budget: body-layer's 1.0 Hz poll loop, no
hard real-time requirement yet (`[[project_body_layer_poll_loop_diagnosis]]`); audio-adapter's
`match_transcript` has no poll budget at all — it runs once per spoken utterance, an
event-triggered call, not a hot loop. Single-user, LAN-only project; proportionate depth.

### Findings

#### `_advance_bounded_look` (new, `optic_policy.py`) — one poll of the bounded clock/compass sweep

- **Location:** `optic_policy._advance_bounded_look`, called from `_decide_sighting`'s idle
  branch, once per poll, but **only when `choose_sighting_look` returned `None`** (nothing in
  `worth_looking` — i.e. only on the idle path, never alongside the already-measured `choose_look`
  cost, the two are mutually exclusive within one poll) **and only when `state.bounded_look is not
  None`** (a `look <o'clock>`/`look <compass>` is actually active — the common case is `None`, and
  the branch is never entered).
- **Mechanism:** a handful of attribute reads, one integer division
  (`(now_sim - leg_started_sim) // SEARCH_STEP_S`), an index comparison, and a `replace()` call —
  O(1) in the number of contacts, and O(1) in the number of search steps too (it indexes into
  `steps`, never iterates it). No allocation beyond the one `replace()`-produced `OpticState`,
  the same pattern every other branch of this module already uses per poll.
- **Risk:** none. This is strictly cheaper than the `choose_look`/`choose_sighting_look` path it
  runs instead of (Stage 1's own measured ~241 µs/poll at 55 contacts, `performance-review.md`) —
  `_advance_bounded_look` touches no `targets` sequence at all.
- **Action:** none needed.

#### `_sight_point_sweep` (new, `body.py`) — per-poll sweep-step generation for a bounded look

- **Location:** `body.py`'s `run_once` call site (line ~786), computing `sight_point_search`
  unconditionally every poll, feeding `_decide_sighting` via `decide_optic`.
- **Mechanism:** identical in kind and or of magnitude to the four pre-existing
  `sight_*_search`/`sight_out_of_regard_search` computations already measured negligible in
  `performance-review.md` (Stage 1: ≤0.05% of budget worst case) — one more
  `_split_sector_by_regard` + `search_pattern` + `_to_body_relative_steps` + `within_field_of_regard`
  filter chain, same shapes, same bounds (`fov_full_width_deg` vs. depression spread derives the
  row count, the regard span bounds the azimuth sweep). **Cheaper than those four in the common
  case**: `bounded_look is None` (no active bounded look — true on every poll outside an active
  `look <clock/compass>`) short-circuits on the very first line, before `search_pattern` or any
  geometry call runs at all.
- **Risk:** none — same mechanism, same order, already-accepted cost class, and the dominant case
  is an O(1) early return.
- **Action:** none needed (inherits Stage 1's MONITOR disposition for the sweep-generation family
  as a whole, not a new entry).

#### Two new per-poll drains (`drain_pending_point_request`, `drain_pending_point_clear`, `crew_console.py`)

- **Location:** `body.py`'s poll loop, called once per poll each, alongside the pre-existing
  `drain_events`/`drain_brain`/`drain_pending_positional_replies`.
- **Mechanism:** both open with `if self.refused or self.pending_point_* is None: return []` —
  the common case (no deferred point request/clear pending) is two attribute reads and a boolean
  short-circuit, no allocation. Exactly the same shape `drain_pending_positional_replies` already
  uses, which this plan's own "What's already built" section named as the precedent to follow.
- **Risk:** none.
- **Action:** none needed.

#### `_apply_point_request_transition` (new, `body.py`) and its call site

- **Location:** `body.py`'s poll loop, guarded by `if crew_console.point_request_transition is
  not None:` — the common case (no superseding command fired this poll) skips the call entirely.
- **Mechanism:** one `replace()` call when it does run — a handful of field reads/writes, no
  iteration, no allocation beyond the one dataclass copy. This only ever runs on a poll where a
  `look`/`scan`/cancel/task-changing command was just dispatched, i.e. at voice-command cadence
  (at most a few times a minute), not every poll.
- **Risk:** none.
- **Action:** none needed.

#### `match_transcript`'s two new slot-resolution branches (`point`/`"what"`, `command_matcher.py`)

- **Location:** `audio-adapter/src/command_matcher.py::match_transcript`, two new branches
  appended after the pre-existing `follow`/`report`/`select_target`/`step`/`engage`/`greeting`
  branches, before the generic phrase table.
- **Mechanism:** each is one `difflib.SequenceMatcher` ratio check against the first word, and —
  only if that clears `VERB_FLOOR` — one call to `_parse_point_slots` (four slot-parser calls over
  the normalized text, the same shape `_parse_follow_slots`/`_parse_report_slots`/etc. already
  use). **This has no per-poll budget at all** — `match_transcript` runs once per spoken
  utterance (a human speaking, at most a few times a minute), not from body-layer's 1 Hz poll
  loop. Measured anyway, `audio-adapter/.venv`, this review (can-this-fail probe run first: a
  point-slot transcript resolves to `token="point"`, a nonsense transcript resolves to
  `token=None` — the harness can fail and does not):

  | transcript | path taken | µs/call |
  |---|---|---|
  | `"look two o'clock"` | new `point` slot branch | 176 |
  | `"sight two o'clock three kilometres"` | new `point` slot branch | 229 |
  | `"what is at two o'clock"` | new `"what"` slot branch | 206 |
  | `"what do you see"` | falls through both new branches, lands in phrase table | 639 |
  | `"scan left"` | pre-existing phrase-table path (unaffected baseline) | 968 |
  | `"report all"` | pre-existing phrase-table path (unaffected baseline) | 1013 |
  | `"follow nearest"` | pre-existing `follow` slot branch (unaffected baseline) | 1080 |

  A transcript that resolves through either new branch is **cheaper** than one that falls through
  to the generic phrase table, because the phrase table's own ratio-scoring loop over every
  recorded phrasing is the expensive part — two more early-exit branches ahead of it only add cost
  to transcripts that still fall through *past* them, and `"what do you see"` (the one case that
  does, since `_parse_point_slots` finds no slot) is still well under the pre-existing
  `"scan left"`/`"report all"`/`"follow nearest"` baselines.
- **Risk:** none, at any plausible scale — this function runs once per voice command, never in a
  loop, and the added branches are provably not the expensive part of a miss.
- **Action:** none needed.

#### Carried-over `[[BL-B98]]` fix (`01a6fadd`) — this pass's required coverage of it

- **Location:** `optic_policy._start_glance_away`'s removed nulling, and `body.py`'s `run_once`
  OBSERV-off-edge branch (`look_azimuth_deg=None, look_elevation_deg=None` added to an existing
  `replace()` call).
- **Mechanism:** both changes touch fields already being written on these same branches — removing
  two keyword arguments from one `replace()` call and adding two to another. No new iteration, no
  new allocation beyond the `replace()` calls both branches already made before this fix. This is
  a correctness fix to which fields a pre-existing state transition carries forward, not a new
  computation.
- **Risk:** none — zero change to the cost of either branch; the set of fields in a `replace()`
  call does not affect its complexity.
- **Action:** none needed.

### Verification

- `body-layer/tests -q -p no:randomly`: **2612 passed, 4 xfailed** (own `.venv` absent in this
  worktree; resolved against `/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/pytest` per the
  task's fallback instruction).
- `audio-adapter/tests -q`: **357 passed, 2 skipped**.
- No source change made during this review — findings only.

### Verdict

APPROVED. Every hot-path addition in this batch is either O(1) relative to contact count and
search-step count (`_advance_bounded_look`), an early-return no-op in the common case
(`_sight_point_sweep`, both new drains, `_apply_point_request_transition`), or outside the 1 Hz
poll budget entirely (the matcher's two new branches, measured cheaper than the pre-existing
fallback path they sit ahead of). The carried-over `[[BL-B98]]` fix changes no per-poll cost. No
MONITOR item is added beyond what Stage 1's own review already carries for the sweep-generation
family and `choose_sighting_look`.
