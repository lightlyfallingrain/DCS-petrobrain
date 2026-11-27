### Implementation Summary -- BL-16 M4, SAU channel handover

On entering mode 1 (`fd_mode` -> `"m1"` from anything else -- a voice
take or the unpark mode 2 -> mode 1 path), Petrovich now runs an
effector sequence that switches SAU H, K, T **off** and B **on**,
mirroring the existing hand-back-to-player sequence
(`controls-to-player.md`) that sets all four **on**. Spec:
`plans/flight-lift-vector/explore-notes.md`, "M4 SAU explore
(2026-11-28)"; `body-layer/ROADMAP/BL-16.md`'s "M4 re-scoped" paragraph.

Mid-task addition from the coordinator (user, 2026-11-28, verbatim):
*"for the SAU channel on/off changes, do not wait between them, just
turn all on right away ... this case is an exception"* to the general
~1s spacing between effector writes. Addressed with a new optional
per-file header param, `step-delay-s` -- see "The no-gap mechanism"
below.

### Files Changed

- `body-layer/src/belief/flight_authority.py` -- added
  `controls_to_petrovich_edge(prev, new) -> bool`, the twin of the
  existing `controls_to_player_edge`, read the other direction: `True`
  exactly when `fd_mode` moves into `"m1"` from anything else. Compares
  `fd_mode` directly (same "no edge to observe" non-issue as its twin:
  the default/no-sample state is `"off"`, never `"m1"`), so it fires
  exactly once per entry, including a re-take
  (`m1` -> `off` -> `taking` -> `m1` fires only on the last transition)
  and the unpark `m2` -> `m1` path. Never fires on entering `m2`.
- `body-layer/src/belief/effector_sequences.py` -- new
  `EffectorTrigger.CONTROLS_TO_PETROVICH = "controls-to-petrovich"`
  member and its `TRIGGER_INFO` entry. New optional header param
  `step-delay-s` (`_OPTIONAL_HEADER_KEYS`), parsed and range-checked
  (finite, >= 0) in `_parse_header`; a bad value drops the file with a
  `SequenceError`, same posture as every other header error. New
  `SequenceFile.step_delay_s: float | None = None` field, `None` when a
  file does not set it (every file but the two SAU ones).
- `body-layer/src/belief/effector_engine.py` -- `advance`'s per-write
  `next_due_sim` now reads `sequence.step_delay_s if not None else
  EFFECTOR_SEQUENCE_STEP_DELAY_S`, instead of the module constant
  unconditionally. Updated that constant's own docstring to point at
  the override.
- `body-layer/src/body.py` -- imports `controls_to_petrovich_edge`;
  fires `EffectorTrigger.CONTROLS_TO_PETROVICH` on that edge, right
  beside the existing `CONTROLS_TO_PLAYER` fire site (same poll-loop
  neighbourhood, same "capture previous, compare" idiom).
- `body-layer/config/sequences/mi-24p/effectors.toml` -- three new
  curated effectors for the SAU channels' own OFF buttons
  (`p_sau_h_channel_off`/`p_sau_k_channel_off`/`p_sau_t_channel_off`,
  `SAU-H-OFF-PTR`/`SAU-K-OFF-PTR`/`SAU-T-OFF-PTR`). These are
  **separate momentary buttons from the existing `p_sau_*_channel_on`
  entries**, not the same switch's "off" position -- pressing the OFF
  button is what actually turns a channel off; `values = { on = 1.0,
  off = 0.0 }` names the button's own press/rest raw values, same shape
  and same "reads 0.0 at rest, always writes" comment as the ON buttons.
  No OFF entry for B -- B stays on, never switched off by this build.
- `body-layer/config/sequences/mi-24p/switch-reference.md` --
  regenerated (`tools/render_switch_reference.py --write`); the three
  new "Curated as" cells.
- `body-layer/config/sequences/triggers.md` -- regenerated
  (`tools/render_triggers.py --write`); the new `controls-to-petrovich`
  row.
- `body-layer/config/sequences/mi-24p/controls-to-petrovich.md` (new) --
  the handover-to-Petrovich sequence: H off, K off, T off, B on (ensured
  explicitly, never assumed from what the player left). `step-delay-s |
  0` in the header.
- `body-layer/config/sequences/mi-24p/controls-to-player.md` -- added
  `step-delay-s | 0` to its header (same exception applies to its own
  four SAU rows).

### Tests Added

- `tests/test_flight_authority.py::TestControlsToPetrovichEdge` --
  fires entering m1 from off/taking/m2; does not fire staying in m1,
  entering m2, entering off, or on the default no-sample state; fires
  exactly once across a full retake cycle (m1 -> off -> taking -> m1).
- `tests/test_body.py` -- three poll-loop integration tests: a voice
  take into m1 fires `CONTROLS_TO_PETROVICH`; the unpark m2 -> m1 path
  fires the same trigger; entering m2 fires nothing.
- `tests/test_effector_sequences.py` -- `step-delay-s` header parsing:
  absent -> `None`; present and valid -> parsed float; non-numeric and
  negative both drop the file with a `SequenceError` naming the
  problem; an unrelated unknown header key is still rejected (confirms
  the optional-key allowance did not loosen the general check).
- `tests/test_effector_engine.py` -- `test_step_delay_s_override_writes_
  every_row_the_same_poll` (a `step_delay_s=0.0` sequence writes all
  four rows from one `advance` call) and
  `test_other_sequences_keep_the_default_spacing_unaffected` (a
  `step_delay_s=None` sequence still writes one row per poll, pinning
  that the override did not change the shared default).

### Checks (body-layer/)

- `ruff format --check`: pass (one file needed reformatting after the
  edits; reformatted and re-checked clean)
- `ruff check`: pass
- `cd body-layer && .venv/bin/mypy src`: pass (no issues, 95 files)
- `pytest tests -q -n auto -p no:cacheprovider` (full suite, once at
  the end): **3913 passed, 4 xfailed** in ~152s. The scattered
  "background brain reply poll failed (retrying)" lines in the output
  are expected log noise from unrelated brain-client tests, not
  failures.
- `config/defaults.toml`: unchanged, correctly -- `step-delay-s` is a
  per-sequence-file parsed value, not a `tuning.*` behaviour constant,
  so it does not go through the tuning mechanism (root `CLAUDE.md`'s
  tuning rule is about constants in code, not sequence-file fields).

### Notable Discoveries

- **The SAU channel OFF buttons were not yet curated.** `effectors.
  toml` only had the ON buttons (`p_sau_h_channel_on` etc., used by the
  pre-existing `controls-to-player.md`); the raw dump and `switch-
  reference.md` already listed `SAU-H-OFF-PTR`/`SAU-K-OFF-PTR`/
  `SAU-T-OFF-PTR` uncurated. Added the three, mirroring the existing ON
  entries' shape/comment.
- **No per-sequence timing override existed before this task.** The
  only existing way to change the gap between writes was `wait_s(<n>)`
  rows, which only ever *add* a pause, never remove the default. The
  `step-delay-s` header param is the smallest addition that fits the
  existing file format (one more optional 2-column header row,
  resolved the same way `run-on-trigger` already is) rather than a new
  per-row column or a second mechanism -- it is file-scoped because
  both sequences this exception applies to (the new controls-to-
  petrovich.md and the pre-existing controls-to-player.md) are
  *entirely* SAU rows; nothing here needed a per-row grain.
- **The implicit self-check still applies to the OFF buttons exactly as
  it does to the ON buttons**: since they read 0.0 at rest always (the
  arg is the click pulse, not a persisted state), every fire presses
  them regardless of whether the channel is actually on -- same
  "whether a repeat press is harmless is unverified" caveat the ON
  buttons' own comment already carries, not a new open question.
- `EffectorTrigger`/`TRIGGER_INFO` is still the single declaration
  (`effector_sequences.py`); no second copy was introduced.
- Did not mark `[[BL-16]]` or M4 done on any roadmap entry, per the
  task's own instruction -- that stays the coordinator's/reviewer's
  call once this is reviewed and flown.
