# radio-check — BL-B82 (no scan on ground) then BL-B81 (radio check / greeting)

Build order per `body-layer/ROADMAP/BL-B82.md`: BL-B82 first (removes the on-ground silence
default, touched by BL-15's reset), then BL-B81 on the settled dispatch.

## BL-B82 — no scanning on the ground

**Seam for "no perception while on the ground":** both production poll loops already collect
observations in one place —
`PerceptionLogger.run_once` (`src/logger.py`, plain text logger) and
`ConsolePerceptionRunner.run_once` (belief-consuming loop) each have exactly one
`[observation for source in self.sources for observation in source.poll(...)]`
comprehension. Gating *there* (skip the comprehension, use `[]`, when
`ownship.alt_agl_m <= ON_GROUND_AGL_THRESHOLD_M`) stops every `PerceptionSource` (naked-eye,
hybrid) from producing anything, without touching any individual source. `ContactStore.tick`
still runs every poll, so existing belief keeps decaying/aging normally — **existing belief is
kept, Petrovich just stops adding new observations to it** (decided per the task brief: "unless
the code makes that unnatural" — nothing here makes keeping it unnatural, tick already handles an
empty-observations poll as the normal "nothing new seen" case).

`ON_GROUND_AGL_THRESHOLD_M` (`belief/crew_console.py`) is reused unchanged — it is not a *new*
constant, so it is not newly wired through `tuning.py` by this change (scope control); flagged in
the report as a pre-existing behaviour-affecting bare constant now doing more work.

**Removed:** `CrewConsole.maybe_apply_on_ground_default`, `_on_ground_default_applied`, the
`logger.py` call site, and `test_crew_console.py`'s tests for it. Its job (silencing speech on the
ramp) is superseded by "don't scan" — the pilot still hears everything, there is just nothing new
for Petrovich to say.

**Look commands on the ground answer "Unable, on the ground."`** New `CrewConsole.on_ground: bool`
field (mirrors how `enrichment` is refreshed every poll), set in both poll loops right where
`maybe_apply_on_ground_default` used to be called. `handle_command` checks it, for a new
`_LOOK_COMMAND_TOKENS` set, right after the existing world-model refusal check (refusal still
wins) and the silence-ends-on-any-command reset (a refused-on-the-ground look command is still a
real command).

`_LOOK_COMMAND_TOKENS` = every scan token (`_RELATIVE_SCAN_TOKENS`, `_BEARING_SCAN_TOKENS`,
`_CLOCK_SCAN_TOKENS`, `scan_bearing_deg`) + `watch_nearest` + `watch_nearest_air_defence` +
`follow`. Judgment call, stated here rather than escalated (local/reversible per the Escalation
Rules): the task names `watch` and `scan forward` as examples of "any command whose job is to make
him look"; `follow` is the one other token that shares that job exactly — it is the one command
that immediately raises binoculars onto a target (`logger.py`'s "any command lowers binoculars"
glue reads `last_command_target_contact_id`). `select_target`/`engage`/`step`/`report*` are
excluded: they only read existing belief (attention/priority flags, attack-run slotting) rather
than directing a new visual search, and degrade naturally ("no such contact") when belief is thin
from not having scanned — no special-casing needed for them to behave sensibly on the ground.

New `_UNABLE_TEMPLATES["ON_GROUND"]` = `"Unable, on the ground."`, reached via the existing
`render_unable` closed-reason mechanism (same shape as `NO_SUCH_COMMAND` etc).

## BL-B81 — radio check / greeting

Two new command tokens, dispatched through the existing `handle_command` (so refusal mode and
"any command ends silence" apply automatically, same as every other token):

- `"radio_check"` → `"Loud and clear."`
- `"greeting"`, slot `{"time_of_day": "morning"|"day"|"evening"|"night"}` → `"Good <time>,
  commander."`, echoing the pilot's own word.

New `render_radio_check()`/`render_greeting(time_of_day)` in `belief/speech.py`, `template=
"readback"` like every other command response.

**Crew-text (typed):** `parse_utterance`'s grammar (`utterance.py`) is contact-reference shaped
(every row extracts and resolves a `ref` group) and does not fit a no-reference command — rather
than bolt a reference-less row onto it, `handle_line` gets two literal/regex checks
("radio check", `good (morning|day|evening|night) petrovich`) before it falls through to
`_handle_utterance`, mirroring the existing `!inject-urgent`/`!voice` special cases immediately
above that call. A match dispatches straight to `self.handle_command(token, now_sim, slots)` —
same as voice's "act" disposition already does — so the refusal/silence/print behaviour is the
single `handle_command` implementation, not a second copy.

**Voice:** no body-layer-side work needed beyond adding the two tokens to
`DISPATCHED_COMMAND_TOKENS` and giving them dispatch behaviour — `handle_transcript`/
`_act_on_voice_decision`'s "act" path already calls `handle_command` generically for whatever
token `audio-adapter`'s `command_matcher` resolves to. Recognising the phrases as those tokens is
an `audio-adapter` vocabulary change, a separate subproject not touched here; body-layer is ready
the moment it is.

**F10:** not added. Not trivial by the existing pattern — every current F10 item is a Hook-side
Lua menu entry in `aircraft-layer/dcs-export/`, deployed via `WORKFLOW.md`'s opt-in and requiring
a DCS-side redeploy; adding one is a cross-subproject change, not a trivial extension of something
already in place. Radio check's whole point (per the backlog entry) is confirming the intercom/
Petrobrain are alive during engine start, which voice already covers once wired on the
audio-adapter side.

## Tests

- BL-B82: perception produces nothing while `alt_agl_m <= ON_GROUND_AGL_THRESHOLD_M` and resumes
  the poll after climbing above it (both `PerceptionLogger.run_once` and
  `ConsolePerceptionRunner.run_once`); a look command (`scan_ahead`, `watch_nearest`) on the ground
  returns `"Unable, on the ground."`; refusal mode still wins over on-ground for a look command; a
  non-look command (`mark_here`) still dispatches normally on the ground; existing belief survives
  a ground poll unmolested (decays, isn't wiped).
- BL-B81: `radio_check` → `"Loud and clear."` on the ground, in the air, and ends an explicit
  `silence`; each of the four greetings echoes correctly; refusal mode answers both with the fixed
  refusal line; typed "radio check" / "good evening Petrovich" crew-text dispatch correctly via
  `handle_line`.

## Affected files

- `body-layer/src/belief/crew_console.py` — remove the on-ground silence default; add
  `on_ground`, `_LOOK_COMMAND_TOKENS`, the look-command refusal branch, `radio_check`/`greeting`
  dispatch + handlers, `handle_line`'s two new literal/regex checks.
- `body-layer/src/belief/speech.py` — `render_radio_check`, `render_greeting`,
  `_UNABLE_TEMPLATES["ON_GROUND"]`.
- `body-layer/src/logger.py` — replace the `maybe_apply_on_ground_default` call site with setting
  `crew_console.on_ground`; gate both `run_once`'s observation comprehensions on `alt_agl_m`.
- `body-layer/tests/test_crew_console.py`, `test_logger.py` — updated/new tests.
- `body-layer/CLAUDE.md` — update the on-ground description.
