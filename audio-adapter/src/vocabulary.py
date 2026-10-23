"""The spoken command vocabulary (`plans/inbound-speech/plan.md` Stage 1).

**This file is the primary command vocabulary, not a mirror of the F10
menu.** It began as a hand-synced duplicate of that menu, and the
docstrings and tests here said so; the user's direction on 2026-09-19
inverted the relationship: *"The F10 menu is only a temporary solution.
Voice is primary. It's alright if F10 menu goes stale, we'll remove it at
some point."* So the F10 command set is now the derived, legacy thing,
and this vocabulary is free to grow past it.

The split below is kept, but only as history rather than an obligation.
`LEGACY_F10_TOKENS` are the 15 that happen to coincide with the F10 menu
today, and `VOICE_ONLY_TOKENS` are the ones that never existed there.
**Divergence between the two is expected and is not a bug** -- do not
"fix" a mismatch against `aircraft-layer`'s `ALLOWED_COMMANDS` by
deleting anything here. When the F10 path is removed the split collapses
and both tuples fold into `TOKENS`.
`audio-adapter` must stand alone (root `CLAUDE.md`'s module-independence
rule -- the body-layer<->world-model in-process import is the sole
sanctioned exception, and this is not it), so it cannot import
`body-layer/src/belief/crew_console.py`'s `_RELATIVE_SCAN_TOKENS`/
`_BEARING_SCAN_TOKENS` tables directly. `aircraft-layer/src/collector/
f10_command_receiver.py`'s `ALLOWED_COMMANDS` tuple is the same 15 tokens,
hand-synced with that same crew_console.py source and with the Hook
script's F10 menu -- this file follows that established precedent (a third
hand-synced copy) rather than inventing a shared-constants mechanism.

Nothing here is synced automatically, and as of the direction above
nothing here needs to be synced at all. Stage 2's matcher and the
body-layer command path are where these tokens acquire behaviour; that
path is the one that must cover `TOKENS`, and it is independent of
whatever the F10 menu still offers.

`PHRASES` is this file's own addition, not mirrored from anywhere -- it is
the recogniser **bias hint list**: the spoken phrasings a constrained
grammar or prompt (whisper.cpp `--prompt`, and `--grammar` where used)
should steer
decoding toward, and the prompt list `tools/stt_bench.py` and the corpus
recording instructions are built from. Several phrasings per token,
matching the examples in `plans/inbound-speech/plan.md` Decision 4 --
deliberately not exhaustive; Stage 1's bench is what will show which
phrasings this user actually says and which get misheard.
"""

from __future__ import annotations

import re

#: The 15 tokens that also exist in the legacy F10 radio menu, in that
#: menu's own order. Kept as a named group for traceability while the F10
#: path still runs; it carries no obligation to match, since that path is
#: being retired (see this module's docstring). Expect it to fold into
#: `TOKENS` when F10 is removed.
LEGACY_F10_TOKENS: tuple[str, ...] = (
    "scan_ahead",
    "scan_left",
    "scan_right",
    "scan_full",
    "scan_bearing_n",
    "scan_bearing_ne",
    "scan_bearing_e",
    "scan_bearing_se",
    "scan_bearing_s",
    "scan_bearing_sw",
    "scan_bearing_w",
    "scan_bearing_nw",
    "watch_nearest",
    "watch_nearest_air_defence",
    "cancel_task",
    "cancel_scan",
    "cancel_watch",
)

#: Clock positions worth recognising: 8 through 4 the short way round,
#: i.e. the forward hemisphere. Deliberately not all twelve (user
#: direction, 2026-09-19). The reason is not recording time but the
#: project's own no-omniscience rule: Petrovich cannot see behind the
#: aircraft, so "report six o'clock" names a direction he has nothing to
#: report about. A command whose only honest answer is "I can't see
#: there" is not worth teaching a recogniser.
FORWARD_CLOCK_POSITIONS: tuple[int, ...] = (8, 9, 10, 11, 12, 1, 2, 3, 4)

#: Spoken number words for `FORWARD_CLOCK_POSITIONS`, since a recogniser
#: transcribes words rather than digits.
_CLOCK_WORDS: dict[int, str] = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
}

#: `report_all` and `stop_talking` are flat commands. The `report_bearing_*`
#: and `report_clock_*` families are the `report <target>` form, enumerated
#: rather than parsed as a slot because a closed grammar has to list what it
#: admits. Unit- and group-named targets ("report the tanks") are
#: deliberately absent: that target set is open, so it cannot be enumerated
#: into a grammar, and it belongs to free speech once the brain layer exists.
#: Commands with no F10 equivalent -- the first vocabulary this project
#: added for voice on its own terms rather than by transcribing a menu.
#: `scan_clock_<p>` -- the ownship-relative o'clock scan family (`plans/
#: voice-command-completeness/plan.md` Stage 5, user direction 2026-09-23:
#: *"'scan 1 o'clock' directs scan at a narrow sector that is own ship
#: relative. That is needed."*). Own-ship-relative direction today is only
#: `scan_ahead`/`scan_left`/`scan_right`/`scan_full` -- `left` alone spans
#: three o'clock hours (11, 10, 9), a 90-degree wedge, and there was no way
#: to say "just there" relative to the nose. Same nine forward hours as
#: `report_clock_*`, for the identical no-omniscience reason (`FORWARD_
#: CLOCK_POSITIONS`'s own comment).
#:
#: **Unbenched, like every token added here**: nine tokens with no
#: recordings in this corpus, the same cost that kept `cancel_scan`/
#: `cancel_watch` off voice until 2026-09-23 (see those tokens' own
#: comment below) -- cheapest to add when the corpus is next re-recorded,
#: not free today. Their recognition accuracy on this user's voice is
#: unmeasured as of this stage.
_SCAN_CLOCK_TOKENS: tuple[str, ...] = tuple(
    f"scan_clock_{p}" for p in FORWARD_CLOCK_POSITIONS
)

VOICE_ONLY_TOKENS: tuple[str, ...] = (
    (
        "report_all",
        "stop_talking",
        "say_again",
        # Absolute silence until the next dispatched command (`plans/
        # silence-command/implementation.md`, user direction 2026-10-04) --
        # body-layer's `handle_command` already dispatches this token; it
        # has no F10 button. No `follow`/`watch_nearest`-style synonym
        # pairing: this is its own command, not an alternate verb for an
        # existing one.
        "silence",
        "scan_bearing_deg",
        "report_bearing_deg",
        # `follow [<descriptor>] [<clock> o'clock] [<n> km]` -- a best-match
        # referring expression (`plans/watch-reporting/plan.md` Decision
        # 2b), the stopgap approximation of free-text targeting. A single
        # token, not a `follow_clock_*` family: descriptor/clock/range are
        # all parsed slots (`parse_descriptor`/`parse_clock`/
        # `parse_range_km` below), not enumerated phrases -- the
        # descriptor x nine hours x twenty ranges cross-product is in the
        # hundreds, far past what a closed grammar can list.
        "follow",
        # `report|describe [<what>] [<where>] [<how far>]` -- the slotted
        # crew query (`plans/crew-query-path/plan.md` Decision A, user
        # decision 12 of `plans/post-review-fixes/explore-notes.md`), the
        # same shape `follow` above already has and for the same reason:
        # 9 clock hours x 8 cardinals x 3 relative x 3 bands x 7
        # descriptors is in the thousands, far past what a closed grammar
        # can list. `descriptor`/`clock` reuse `parse_descriptor`/
        # `parse_clock` verbatim; `sector`/`relative`/`band` get the three
        # parsers added below.
        #
        # **The legacy `report_all`/`report_clock_*`/`report_bearing_*`/
        # `report_bearing_deg` tokens stay**, and four separate consumers
        # are why. **Not `LEGACY_F10_TOKENS`** -- the plan's Decision A
        # said so and this comment inherited it, but that tuple holds the
        # scan/watch/cancel tokens and has never held a `report_*` one,
        # so the legacy report families are not reachable from the F10
        # menu at all. What does reach them: `TOKENS` membership, which
        # is what the STT bench corpus iterates to print its record-these
        # prompts (`tools/stt_bench.py`'s `_print_prompts`); body-layer's
        # `_CLOCK_REPORT_TOKENS`/`_BEARING_REPORT_TOKENS` dispatch tables
        # and its `DISPATCHED_COMMAND_TOKENS` pinned test; the brain's
        # structured replies (`belief/brain_reply.py`); and the
        # typed-console path (`belief/voice_commands.py`). Retiring them
        # is a separate job. A zero-slot `"report"`/`"describe"` still
        # falls through to `report_all` through the ordinary phrase table.
        "report",
        # `select|set target <what> <where>` / `drop target` (`plans/
        # attack-run/plan.md` Decision 14, BL-14 Stage 1) -- `select_
        # target` carries the same five slots `report` above does
        # (`descriptor`/`clock`/`sector`/`relative`/`band`), parsed, never
        # enumerated, for the identical combinatorial reason. `drop_target`
        # is a plain, slot-free phrase matched by the ordinary phrase
        # table, like `cancel_watch`.
        "select_target",
        "drop_target",
        # `step [<count>] left/right/near/far` (`plans/attack-run/plan.md`
        # Decision 6, BL-14 Stage 4) -- `direction`/`count` are parsed
        # slots (`parse_step_direction`/`parse_step_count` below), not
        # enumerated phrases, for the same reason `follow`/`report`'s
        # slots are: 4 directions x several counts is small enough to
        # enumerate, but the recorded phrasings below are still bias
        # hints only, not the closed set this token accepts.
        "step",
        # `engage [<what> <where>] [guns|rockets|missiles]` /
        # `attack [<what> <where>]` (Decision 15, BL-14 Stage 5) -- the
        # same five what/where slots `select_target` parses, plus one new
        # weapon slot (`parse_weapon` below) that nothing on the body-
        # layer side reads yet (Decision 15: accepted, not required).
        "engage",
        # `disengage` / `stop attack` / `abort` (Decision 2) -- a plain,
        # slot-free phrase, like `drop_target`.
        "disengage",
        # `observ on` / `observ off` (`BL-B64` Stage 2, direction §6:
        # "OBSERV ON only on pilot command") -- plain, slot-free phrases,
        # the same posture `drop_target`/`disengage` already have. There
        # is no F10 equivalent (user direction: "OK to skip F10 menu
        # command" on the merge blocking this pair in), so both are
        # `VOICE_ONLY_TOKENS` rather than `LEGACY_F10_TOKENS` members by
        # construction, not by omission.
        #
        # **Deliberately NOT added to `belief.voice_commands.CANCEL_TOKENS`**
        # -- that set raises the floor a transcript's confidence must
        # clear before it is *acted on*, which lowers the odds of exactly
        # the thing the attack-run sortie feedback (§2, the reason this
        # pair must ship before merge) calls out: Petrovich not stopping
        # the sight when told to. `cancel_task`/`silence`/`drop_target`
        # are in that set because a *false act* destroys standing state a
        # misfire cannot cheaply undo; a false act on `observ_off` costs
        # nothing worse than re-entering OBSERV, while a *missed* act
        # (the floor set too high) is the failure that matters here. Both
        # tokens stay at the ordinary `ACT_FLOOR`.
        "observ_on",
        "observ_off",
        # `weapons armed` / `weapons safe` (`BL-B66`, `plans/
        # 9k113-effectors/plan.md` §4) -- the weapons safety switches bar,
        # plain slot-free phrases, same posture as `observ_on`/
        # `observ_off` above. **Deliberately "weapons armed"/"weapons
        # safe" only** -- user direction 2026-10-21 dropped "weapons
        # on"/"weapons off" (explore-notes.md point 7 had proposed
        # "weapons off/safe" as the matching pair; the user's own final
        # answer was "weapons armed/safe", not that). No F10 menu
        # equivalent, same reasoning `observ_on`/`observ_off`'s own
        # comment gives (voice is primary, the F10 vocabulary is the
        # legacy, non-growing one) -- checked, per the task brief's own
        # instruction to check.
        #
        # **Unlike `engage`'s own "attack" rejection above, "weapons" is
        # added here despite measuring the identical collision** --
        # `difflib.SequenceMatcher(None, "tanks", "weapons").ratio() ==
        # 0.5`, exactly `command_matcher.VERB_FLOOR`, so the reviewer's
        # own adversarial sentence ("the tanks are on the ridge") now
        # false-anchors on "weapons" too. The difference from `engage`:
        # that word had a real substitute (`engage`/`engage target`
        # already cover the dispatched token); there is no substitute
        # for "weapons armed"/"weapons safe" -- the user's own exact
        # words, Decision 3. The phrase-sequence score (`_phrase_match_
        # ratio`, this module's own docstring on why that is "the real
        # defence") still rejects the sentence end to end -- `token`
        # stays `None` -- this only flips the intermediate `verb_anchored`
        # flag from `False` to `True` on that one adversarial case, which
        # `test_transcribe_api.py::test_non_command_speech_enqueues_with_
        # null_token` had to be updated to reflect (one assertion, not the
        # test's own `token is None` outcome). Flagged for the user/
        # reviewer rather than silently absorbed.
        "weapons_armed",
        "weapons_safe",
        # `mark here` / `mark target` (`plans/bl8-mission-memory/plan.md`
        # Decision 6) -- the commanded half of mission memory, reachable
        # by voice and by the brain tool only, deliberately no new F10
        # radio-menu entry (BL-10's own instruction not to re-expand that
        # tree). Plain, slot-free phrases, the same posture `drop_target`/
        # `disengage`/`observ_on` already have: `mark_here` writes
        # ownship's current position, `mark_target` writes the currently
        # selected target's believed position. **Unbenched**, like every
        # token added here without a re-recorded corpus.
        "mark_here",
        "mark_target",
        # `radio check` / `good morning|day|evening|night petrovich`
        # (`[[BL-B81]]`, `plans/radio-check/plan.md`) -- the user's own
        # stated reason: "if intercom is off, there's no response. This
        # is an easy check that A) intercom is ON and volume good B) that
        # Petrobrain is operational." Both are ordinary commands dispatched
        # through `handle_command` like any other token (body-layer side
        # already wired, `01a69ec7`); this vocabulary is what makes them
        # recognisable from speech. `radio_check` is plain and slot-free,
        # like `drop_target`. `greeting` carries one parsed slot
        # (`time_of_day`, `TIME_OF_DAY_WORDS` below) -- the pilot's own
        # word is echoed back, not enumerated as four separate tokens, the
        # same `follow`/`report`-style "parse a slot, don't multiply
        # tokens" choice this file already makes, even though four values
        # would fit a closed grammar; it keeps one dispatch token on the
        # body-layer side rather than four.
        "radio_check",
        "greeting",
    )
    + tuple(f"report_bearing_{d}" for d in ("n", "ne", "e", "se", "s", "sw", "w", "nw"))
    + tuple(f"report_clock_{p}" for p in FORWARD_CLOCK_POSITIONS)
    + _SCAN_CLOCK_TOKENS
)

#: Numeric bearings are a **slot, not an enumeration** (user direction,
#: 2026-09-19: *"'<verb> bearing <south/etc>' is something I'll never
#: actually say. Just '<verb> south'. On the other hand '<verb> bearing
#: 320' is entirely possible."*). The compass words keep their bare form
#: and lose the "bearing" form entirely; degrees arrive as a parsed
#: number instead.
#:
#: Spoken digit by digit, always three digits ("bearing three two zero",
#: "bearing zero zero five"), which is standard readback form and removes
#: the ambiguity between 50, 350 and 005 by construction.
#:
#: **This 5-degree slot is a recognition checksum, not a precision
#: guarantee, and the two are independent** (`plans/
#: voice-command-completeness/plan.md` Decision 3). Roughly four in five
#: mishearings land on a value that is not a multiple of five, which is
#: what makes them *detectable* -- `parse_bearing` returns them as `heard`
#: without `degrees` so the caller can ask the player to say again rather
#: than act on a number nobody said. What body-layer's
#: `belief.crew_console._nearest_sector` then does with a value that *does*
#: pass this checksum is a separate, later decision: it quantises the
#: parsed bearing onto the nearest of the eight `Sector` compass buckets
#: (45-degree wide) before acting, because the user judged "o'clock
#: direction is enough, no need for x degrees granularity now"
#: (2026-09-23). Do not read that act-time quantisation back into this
#: constant, or "restore" 5-degree precision here later under the belief
#: that it was ever wanted at the acted-on value -- the checksum runs at
#: recognition time, the quantisation at act time, and neither one implies
#: anything about the other's resolution.
BEARING_RESOLUTION_DEG = 5

#: Every legal bearing: 0, 5, 10 ... 355.
LEGAL_BEARINGS_DEG: tuple[int, ...] = tuple(range(0, 360, BEARING_RESOLUTION_DEG))

_DIGIT_NAMES: tuple[str, ...] = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
)

#: Bearings sampled for the recording corpus. Not the legal set -- 72
#: values times two verbs is not a thing anybody should record, and the
#: matcher accepts all of them regardless. These are chosen so that
#: **every digit 0-9 is spoken at least once**, which is what the bench
#: actually needs to measure: numbers are the accent-fragile part, and
#: what matters is per-digit reliability rather than per-bearing.
_SAMPLED_SCAN_BEARINGS: tuple[int, ...] = (0, 45, 60, 90, 135, 180, 225, 270, 315)
_SAMPLED_REPORT_BEARINGS: tuple[int, ...] = (5, 180, 355)


def bearing_digits(degrees: int) -> str:
    """ "three two zero" for 320 -- always three digit words."""
    return " ".join(_DIGIT_NAMES[int(d)] for d in f"{degrees % 360:03d}")


def bearing_phrase(verb: str, degrees: int) -> str:
    return f"{verb} bearing {bearing_digits(degrees)}"


#: Tokens that route or retract a transmission rather than commanding
#: anything (user direction, 2026-09-19). They are listed here because the
#: recogniser must hear them and the bench must measure them, but nothing
#: downstream should ever dispatch them as commands -- see each entry's
#: phrasing note below, and `plans/inbound-speech/plan.md` for the tiering
#: design they belong to.
#:
#: `wake_petrovich` is the tier discriminator: a transmission beginning
#: with it is free speech for the brain layer, and one without it is a
#: command matched against this vocabulary. **Its two failure modes are
#: not symmetric.** A false wake sends a command to the brain, which can
#: interpret a command phrasing perfectly well -- the cost is latency. A
#: missed wake sends free speech to the command matcher, which will
#: fuzzy-match it onto *something* and execute a wrong action. So
#: detection should lean toward waking, and the bench's job is to say how
#: often this word survives at all: it is a Russian name spoken with a
#: Finnish accent, which is the least favourable case in the whole
#: vocabulary.
#:
#: `cancel_nevermind` retracts the transmission it ends. Its existence is
#: what forbids acting on anything before the transmission closes, since
#: the last word can withdraw everything before it. Every decision
#: therefore happens at PTT release, with no exceptions -- including
#: `stop_talking`, which an earlier draft had firing mid-stream for
#: barge-in latency.
ROUTING_TOKENS: tuple[str, ...] = ("wake_petrovich", "cancel_nevermind")

#: Every token the recogniser should admit. This, not any subgroup, is
#: what the grammar, the bench and Stage 2's matcher are built from.
TOKENS: tuple[str, ...] = LEGACY_F10_TOKENS + VOICE_ONLY_TOKENS + ROUTING_TOKENS

#: Spoken phrasings per token.
#:
#: **Phrasings are what this speaker actually says, not every English way
#: of saying it** (user direction, 2026-09-19: *"'scan to the right' vs
#: 'scan right' -> 'scan right' only. Or more generally <verb>
#: <left/right/ahead/etc>/<north/etc> without 'to the'."*). Directional
#: commands are bare verb plus direction, and filler articles are dropped
#: throughout -- "watch nearest", not "watch the nearest".
#:
#: Trimming these is not just tidying. Every phrasing is clips to record,
#: an alternative the matcher can land on, and one more way for a
#: mishearing to resolve to something legal -- so a phrasing nobody utters
#: costs recording time and widens the error surface while contributing
#: no recognition coverage at all.
PHRASES: dict[str, tuple[str, ...]] = {
    "scan_ahead": ("scan ahead", "look ahead"),
    "scan_left": ("scan left", "look left"),
    "scan_right": ("scan right", "look right"),
    "scan_full": ("scan full", "full scan", "scan all around"),
    "scan_bearing_n": ("scan north",),
    "scan_bearing_ne": ("scan northeast",),
    "scan_bearing_e": ("scan east",),
    "scan_bearing_se": ("scan southeast",),
    "scan_bearing_s": ("scan south",),
    "scan_bearing_sw": ("scan southwest",),
    "scan_bearing_w": ("scan west",),
    "scan_bearing_nw": ("scan northwest",),
    # `follow` is `watch`'s synonym (`plans/watch-reporting/plan.md`
    # Decision 2a) -- extra phrasings on the same tokens, not a new token.
    # `VERB_ANCHOR_WORDS` (`command_matcher.py`) is derived from `PHRASES`
    # at import time, so `follow` becomes an anchorable verb for free.
    "watch_nearest": ("watch nearest", "follow nearest"),
    "watch_nearest_air_defence": (
        "watch nearest air defence",
        "watch nearest air defense",
        "follow nearest air defence",
        "follow nearest air defense",
    ),
    "cancel_task": ("cancel task", "cancel"),
    # Narrow cancels (user, 2026-09-23: *"cancel task <task> should work
    # cancel <task>"*). They were F10-only when the tokens were added,
    # because this corpus has no recordings of them and the 99.2% gate was
    # measured on recordings -- but a menu-only way to say something the
    # pilot is already saying out loud is the wrong side of that trade.
    #
    # **`"cancel"` alone stays with `cancel_task`.** A bare "cancel" cannot
    # name which mode it means, and guessing is what the narrow tokens were
    # introduced to stop; the all-modes reading is the honest one for an
    # unqualified cancel, and its readback names everything it stopped.
    #
    # `"stop scan"`/`"stop watch"` do not collide with the `stop` token:
    # that one counts only when it is the entire transmission.
    "cancel_scan": ("cancel scan", "stop scan", "stop scanning"),
    "cancel_watch": (
        "cancel watch",
        "stop watch",
        "stop watching",
        "cancel follow",
        "stop following",
    ),
    # Voice-only. `report` carries five phrasings because it is the
    # command most likely to be said casually and differently each time.
    # "describe"/"describe contacts" added 2026-10-05 (sortie debrief,
    # `plans/sortie-2026-10-05-refinements/plan.md` Item 2): "describe" is
    # six letters and phonetically distinct from every existing anchor
    # verb (`scan`, `watch`, `follow`, `report`, `cancel`, `stop`,
    # `silence`), unlike bare "quiet" (rejected above) which sat a 0.889
    # `SequenceMatcher` ratio from the ordinary word "quite" and would
    # have falsely anchored on "quite a nice day for flying today".
    # Measured directly against `command_matcher.match_transcript` with
    # this phrasing wired in: no collision against any other verb anchor
    # word, and adversarial sentences ("describe the mission to me",
    # "describing the situation", "the scribe wrote it down") all come
    # back `token=None` -- none of them resembles a known phrase's word
    # sequence, the real defence per that module's docstring.
    "report_all": (
        "report",
        "report contacts",
        "what do you see",
        "describe",
        "describe contacts",
    ),
    # **Exactly one phrasing, and it counts only when it is the entire
    # transmission** (user direction, 2026-09-19: "Let's just use 'stop'
    # for this purpose. It's simple."). A "stop" inside a sentence --
    # "stop scanning north" -- is not the stop rule.
    #
    # The single phrasing is not an oversight. Admitting "stop talking"
    # or "quiet" as command phrasings while routing only on a bare "stop"
    # would contradict itself: the longer forms would trigger the same
    # behaviour through the command matcher, by the back door, and the
    # whole-transmission rule would no longer mean what it says.
    #
    # The known risk of that simplicity: `stop` aborts Petrovich's speech,
    # so a miss leaves him talking over something the player needs to
    # hear. It is a single short syllable, the hardest thing for a
    # recogniser to catch, and on clean synthetic speech it already came
    # back as "cloud" and "stock". With the alternates gone there is no
    # fallback word -- so if Stage 1's bench shows this token unreliable
    # on the user's own voice, the decision genuinely needs revisiting
    # rather than tuning around. Revisiting is cheap: adding a phrasing
    # is a handful of clips, not a re-recorded corpus.
    "stop_talking": ("stop",),
    # Standard aviation practice, and deliberately bidirectional: the
    # player says it when he missed what Petrovich said, and Petrovich
    # says it when recognition confidence falls below the band Stage 1's
    # bench measures. Asking beats both guessing and silence -- a crew
    # member who did not catch something says so.
    "say_again": ("say again", "repeat", "repeat that"),
    # Mutes Petrovich absolutely -- including urgent threat callouts --
    # until any dispatched command clears it (body-layer's own call,
    # `plans/silence-command/implementation.md`). A misfire here is worse
    # than most: it does not just fail to act, it makes the crew go quiet
    # near something the player never asked to stop hearing about, which
    # is why body-layer gates this token behind the elevated
    # `ACT_FLOOR_CANCEL` confidence floor (`voice_commands.CANCEL_TOKENS`)
    # rather than the ordinary act floor.
    #
    # **Three phrasings, not one -- and a fourth, bare "quiet", was
    # weighed and rejected, not merely not thought of.** "silence" is the
    # user's own word and must be present. "quiet"/"be quiet"/"shut up"
    # were candidates, measured against this file's own matcher
    # (`command_matcher.match_transcript`) with all four wired in:
    # "be quiet" and "shut up" cost nothing (no false command on
    # adversarial sentences that merely contain one of their words --
    # "be careful", "shut the door" come back `token=None`, and the
    # existing phrase table -- `cancel`/`stop`/`watch nearest`/`scan
    # left`/`follow nearest` -- is unaffected). Bare **"quiet" was
    # dropped**: as a one-word phrase it becomes its own verb-anchor word
    # (`VERB_ANCHOR_WORDS` is derived from each phrase's first word), and
    # "quiet" sits a 0.889 `SequenceMatcher` ratio from the ordinary
    # English word "quite" -- comfortably above `VERB_FLOOR` (0.5). That
    # turned `match_transcript("quite a nice day for flying today")` from
    # a clean anchor rejection into a false `verb_anchored=True`, which
    # broke `test_verb_anchor_rejects_non_command_speech`'s pinned
    # expectation (`test_command_matcher.py`) -- a real, measured
    # collision, not merely a theoretical one, and exactly the risk this
    # token's own addition was told to weigh phrase by phrase. "be quiet"
    # keeps the second word "quiet" without that risk, since only a
    # phrase's *first* word becomes an anchor. `"stop"` alone stays
    # `stop_talking`'s -- that token means "stop talking right now", this
    # one means "say nothing from here on"; a pilot who wants both says
    # both.
    #
    # **Unbenched, like every token added here**: no recordings of this
    # speaker saying any of these three phrasings exist in this corpus,
    # so recognition accuracy on his voice is unmeasured -- the same cost
    # that kept `cancel_scan`/`cancel_watch` off voice until 2026-09-23
    # (see those tokens' own comment above). This one is worth weighing
    # more carefully than most: it is a command reached for when busy and
    # not wanting to repeat it.
    "silence": ("silence", "be quiet", "shut up"),
    # The bare verb -- descriptor/clock/range are parsed slots
    # (`command_matcher.py`'s follow-slot fallback path), never enumerated
    # here. "follow nearest"/"follow nearest air defence" are NOT this
    # token's phrasings -- they are extra phrasings on `watch_nearest`/
    # `watch_nearest_air_defence` (Decision 2a, the free synonym), matched
    # by the ordinary phrase table before this token's fallback path is
    # ever reached.
    "follow": ("follow",),
    # The slotted crew query. Like `follow`, the slots are parsed
    # (`command_matcher.py`'s report-slot branch), never enumerated here --
    # these five phrasings are **recogniser bias hints only** (this
    # module's docstring: `PHRASES` is the prompt/grammar bias list, and
    # is deliberately not exhaustive), chosen to cover one example of each
    # slot shape: relative, clock + band, descriptor + cardinal, and the
    # `describe` verb on two of them so the corpus measures both verbs.
    #
    # **Bare `"report"`/`"describe"` are deliberately absent here** -- they
    # belong to `report_all` above and must keep resolving there (a
    # zero-slot query is still "report everything"). Adding either would
    # also collide in `normalized_phrase_index`, which raises rather than
    # letting one token silently shadow the other.
    "report": (
        "report left",
        "report right",
        "describe two o'clock near",
        "report armor north",
        "describe group far",
    ),
    # `select target`/`set target` (`plans/attack-run/plan.md` Decision
    # 14) -- like `report`, the slots are parsed (`command_matcher.py`'s
    # select-slot branch), never enumerated here; these two phrasings are
    # recogniser bias hints only, one per verb synonym.
    "select_target": ("select target armor north", "set target two o'clock"),
    # `drop target` (Decision 2) -- a plain, slot-free phrase, one exact
    # wording, matching `cancel_watch`'s own posture for a short command
    # with no recorded ambiguity to hedge against yet.
    "drop_target": ("drop target",),
    # `step [<count>] left/right/near/far` (`plans/attack-run/plan.md`
    # Decision 6) -- slots parsed (`command_matcher.py`'s step-slot
    # branch), never enumerated; these phrasings are recogniser bias
    # hints only, one per direction plus one with a count.
    "step": ("step left", "step right", "step 2 left", "step near", "step far"),
    # `engage [<what> <where>] [weapon]` (Decision 15) -- like
    # `select_target`, the what/where/weapon slots are parsed, never
    # enumerated; these phrasings are recogniser bias hints only.
    #
    # **`attack`/`attack-run` (the spec's own synonym verbs, `docs/
    # concept/Attacking target.md`) are deliberately NOT admitted here.**
    # `_derive_verb_anchor_words` would pick up `"attack"` as a
    # `VERB_ANCHOR_WORDS` member from either phrasing's first word, and
    # `difflib.SequenceMatcher(None, "tanks", "attack").ratio() ==
    # 0.545` -- just over `command_matcher.VERB_FLOOR` (0.5). That flips
    # `test_non_command_speech_enqueues_with_null_token`'s own pinned
    # adversarial sentence ("the tanks are on the ridge") from
    # `verb_anchored=False` (silently falls through to free speech) to
    # `verb_anchored=True, token=None` ("say again") -- a real behaviour
    # change for an ordinary descriptive remark, not a cosmetic one, and
    # one this implementer may not fix by rewriting a pinned test
    # (`AGENTS.md`'s own rule). `engage`/`engage target` cover the token
    # the plan's Stage 5 wiring actually dispatches; the `attack`
    # synonym is flagged here rather than silently dropped.
    "engage": ("engage", "engage target"),
    # `disengage` / `stop attack` / `abort` (Decision 2) -- a plain,
    # slot-free phrase, matching `drop_target`'s own posture.
    "disengage": ("disengage", "stop attack", "abort"),
    # `observ on` -- the cockpit's own name for the mode (the panel reads
    # "OBSERV"), said the way the readback itself says it back
    # (`_handle_observ_on`: "Observ on."). Two phrasings, not one, because
    # "OBSERV" is not an English word and a recognizer has no reason to
    # prefer its spelling over the real word it is homophonic with --
    # "observe" is the standard decoding of the same sound, so both are
    # admitted rather than betting on one. **Unbenched**, like every
    # token added here without a re-recorded corpus (the same cost this
    # module's docstring notes for `cancel_scan`/`cancel_watch`/
    # `silence`): no recordings of this speaker saying either phrasing
    # exist yet.
    "observ_on": ("observ on", "observe on"),
    # `observ off` -- same two-spelling reasoning as `observ_on` above.
    # **This is the direction the attack-run sortie feedback actually
    # cares about** (§2: Petrovich not stopping the sight when told to),
    # so this pair's reliability matters more than `observ_on`'s -- see
    # `VOICE_ONLY_TOKENS`' own comment on why that argues for the
    # *ordinary* `ACT_FLOOR`, not a stricter one.
    "observ_off": ("observ off", "observe off"),
    # `weapons armed` / `weapons safe` (`BL-B66`) -- the weapons safety
    # switches bar. One phrasing each, like `drop_target`/`radio_check` --
    # these are the user's own exact words, with no recorded ambiguity to
    # hedge against yet.
    "weapons_armed": ("weapons armed",),
    "weapons_safe": ("weapons safe",),
    # `mark here` -- writes ownship's current position (`plans/
    # bl8-mission-memory/plan.md` Decision 6). Plain, slot-free phrase,
    # matching `drop_target`'s own posture. "remember this location" is
    # the longer, less clipped way this speaker might actually say it --
    # phonetically distinct from every existing anchor verb (`scan`,
    # `watch`, `follow`, `report`, `cancel`, `stop`, `silence`, `select`,
    # `set`, `drop`, `step`, `engage`, `disengage`, `observ(e)`), so it
    # does not risk the "quiet"/"quite" collision `report_all`'s own
    # comment warns about.
    "mark_here": ("mark here", "mark this position", "remember this location"),
    # `mark target` -- writes the currently selected target's believed
    # position (reuses `select_target`'s notion of "currently selected").
    # Same posture as `mark_here` above.
    "mark_target": ("mark target", "remember target"),
    # `radio check` (`[[BL-B81]]`) -- a plain, slot-free phrase, matching
    # `drop_target`'s posture: one exact wording, no recorded ambiguity to
    # hedge against yet.
    "radio_check": ("radio check",),
    # `good <morning|day|evening|night> petrovich` -- like `follow`/
    # `report`, the slot (`time_of_day`) is parsed
    # (`command_matcher.py`'s greeting-slot branch), never enumerated as
    # four tokens; these four phrasings are recogniser bias hints that
    # also happen to be the closed set `parse_time_of_day` accepts, one
    # per `TIME_OF_DAY_WORDS` value below.
    "greeting": (
        "good morning petrovich",
        "good day petrovich",
        "good evening petrovich",
        "good night petrovich",
    ),
    # Routing, not commands -- see ROUTING_TOKENS.
    #
    # The wake word carries both the bare and the greeted form because a
    # player says both, often in the same sortie. It is also the one
    # entry here whose *misses* matter more than its confusions, so the
    # bench's per-clip listing is worth reading for this token even if
    # the headline accuracy looks acceptable.
    "wake_petrovich": ("petrovich", "hey petrovich"),
    # "disregard" is the formal radio equivalent and costs one more
    # recording to find out which of the three actually survives this
    # speaker's accent.
    "cancel_nevermind": ("nevermind", "never mind", "disregard"),
}

#: `report <compass>` -- the same eight directions `scan_bearing_*` uses,
#: under a different verb. The pairing is deliberate: "scan north" and
#: "report north" differ only in the verb, and confusing them swaps one
#: action for another rather than merely garbling a word. If the bench
#: finds that pair unreliable, the fix is a vocabulary change, and Stage 1
#: is when that is still cheap.
for _direction, _word in (
    ("n", "north"),
    ("ne", "northeast"),
    ("e", "east"),
    ("se", "southeast"),
    ("s", "south"),
    ("sw", "southwest"),
    ("w", "west"),
    ("nw", "northwest"),
):
    PHRASES[f"report_bearing_{_direction}"] = (f"report {_word}",)

#: `report <clock>` -- one phrasing each, unlike every other token here.
#: The discriminating content is the number word itself, which one carrier
#: phrase already isolates; a second carrier would multiply recording time
#: without adding evidence about the number. Numbers are the accent-fragile
#: part of this vocabulary, so what matters is takes per number, not
#: phrasings per number.
PHRASES["scan_bearing_deg"] = tuple(
    bearing_phrase("scan", d) for d in _SAMPLED_SCAN_BEARINGS
)
PHRASES["report_bearing_deg"] = tuple(
    bearing_phrase("report", d) for d in _SAMPLED_REPORT_BEARINGS
)

for _position in FORWARD_CLOCK_POSITIONS:
    PHRASES[f"report_clock_{_position}"] = (
        f"report {_CLOCK_WORDS[_position]} o'clock",
    )
    # `scan <clock>` -- Stage 5's ownship-relative o'clock scan family, one
    # phrasing each like its `report_clock_*` sibling: the number word is
    # the discriminating content, and a second carrier phrase would cost
    # recording time without adding evidence about it.
    PHRASES[f"scan_clock_{_position}"] = (f"scan {_CLOCK_WORDS[_position]} o'clock",)

assert set(PHRASES) == set(TOKENS), "PHRASES and TOKENS have drifted apart"
assert not set(LEGACY_F10_TOKENS) & set(VOICE_ONLY_TOKENS), "a token cannot be both"


def spoken_phrases() -> tuple[str, ...]:
    """Every phrasing for every token, flattened, in `TOKENS` order. This
    is the flat list both engines' grammars are built from and the list
    `tools/stt_bench.py` prints as recording prompts."""
    phrases: list[str] = []
    for token in TOKENS:
        phrases.extend(PHRASES[token])
    return tuple(phrases)


def token_for_phrase(phrase: str) -> str | None:
    """The token a known, exact phrasing belongs to, or `None` if `phrase`
    is not one of `PHRASES`' entries verbatim. A simple reverse lookup --
    fuzzy matching against unknown recognizer output is the bench's own
    job (`tools/stt_bench.py`), not this module's."""
    for token, phrasings in PHRASES.items():
        if phrase in phrasings:
            return token
    return None


def to_gbnf() -> str:
    """A minimal GBNF grammar restricting decoding to exactly this
    vocabulary's phrasings, for whisper.cpp's `--grammar` flag.

    whisper.cpp (and llama.cpp, which it shares grammar sampling with)
    accepts a GBNF grammar file with a `root` rule; a flat alternation of
    quoted literals is the simplest grammar that admits only our phrases
    and nothing else.

    **Verified against whisper.cpp 1.9.4 (Homebrew, arm64), 2026-09-19.**
    This grammar parses and constrains decoding as intended -- but only
    when the caller also passes `--grammar-rule root`, which
    `stt_engine.WhisperCliEngine` now does. The rule name here and
    `stt_engine.GRAMMAR_ROOT_RULE` must stay in agreement; a mismatch
    fails silently, leaving decoding unconstrained rather than erroring.
    """
    alternatives = " | ".join(f'"{phrase}"' for phrase in spoken_phrases())
    return f"root ::= {alternatives}\n"


#: Digit -> number-word, for the clock positions this vocabulary uses.
#: Recognizers transcribe "report three o'clock" as "report 3 o'clock"
#: (observed on both `ggml-base.en` and `ggml-small.en`, see
#: `research/2026-09-19-whisper-contract-and-grammar-probe.md`). `PHRASES`
#: spells the words out because that is what a person says, so something
#: has to bridge the two representations.
_DIGIT_WORDS: dict[str, str] = {
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
    "10": "ten",
    "11": "eleven",
    "12": "twelve",
}

#: Compass words a recognizer may split or hyphenate ("north west",
#: "north-west") where this vocabulary writes them solid ("northwest").
_COMPASS_JOINS: tuple[tuple[str, str], ...] = (
    ("north east", "northeast"),
    ("north west", "northwest"),
    ("south east", "southeast"),
    ("south west", "southwest"),
)

#: Apostrophe variants in "o'clock". A recognizer may emit a typographic
#: apostrophe, a straight one, or drop it entirely.
_OCLOCK_VARIANTS: tuple[str, ...] = (
    "o’clock",
    "o clock",
    "oclock",
)


def _collapse_repeats(words: list[str]) -> list[str]:
    """Reduce "scan west scan west scan west" to "scan west".

    Whisper loops on short utterances, especially when prompted, and
    emits the same phrase several times. The recognition itself is
    correct when that happens -- the words are right, there are just too
    many of them -- so collapsing recovers a clip that would otherwise
    score as a total miss. Two of the four errors in this project's best
    bench run were exactly this.

    Finds the shortest period that tiles the whole sequence, allowing the
    final repeat to be cut off mid-phrase, which is how these actually
    arrive. Requires at least two full repeats, so a genuine phrase with
    an incidental repeated word is left alone.
    """
    count = len(words)
    for period in range(1, count // 2 + 1):
        pattern = words[:period]
        if all(words[i] == pattern[i % period] for i in range(count)):
            return pattern
    return words


def normalize_for_match(text: str) -> str:
    """Fold recognizer output and a known phrasing onto common ground.

    Applied to **both sides** of a comparison -- raw recognizer text and
    the `PHRASES` entry it is being matched against -- so the two meet in
    the middle rather than one being bent toward the other.

    What it folds away is everything observed to differ without carrying
    meaning: surrounding whitespace and case, trailing punctuation
    (whisper returns `" Scan left."` where the phrase is `"scan left"`),
    typographic apostrophes, hyphenated or split compass words, and
    digits written where this vocabulary spells number words.

    **The digit case is the one that matters.** Without it every
    `report_clock_*` clip scores as a miss while having been heard
    perfectly, which on a bench report is indistinguishable from a
    recognition failure -- precisely the wrong conclusion to hand
    someone judging whether recognition works on their voice.

    Deliberately conservative: it does not stem, drop filler words, or
    reorder. Those are matching decisions, and they belong to the matcher
    that has to decide whether to *act* on a phrase, not to a
    normalization step shared with scoring.
    """
    normalized = text.strip().lower()
    for variant in _OCLOCK_VARIANTS:
        normalized = normalized.replace(variant, "o'clock")
    normalized = normalized.replace("-", " ")
    normalized = "".join(char for char in normalized if char.isalnum() or char in " '")
    normalized = " ".join(normalized.split())
    for split_form, solid in _COMPASS_JOINS:
        normalized = normalized.replace(split_form, solid)
    words: list[str] = []
    after_bearing = False
    for word in normalized.split():
        if after_bearing and word.isdigit():
            # A recognizer writes a spoken "one eight zero" back as "180"
            # (or "1.8.0", whose punctuation is already gone by here), so
            # after the word "bearing" a digit run is expanded back into
            # individual digit words. Without this a perfectly-heard
            # bearing scores as a total miss, which is the same class of
            # silent error the clock-digit bridging fixed -- a
            # representation difference reading as a recognition failure.
            words.extend(_DIGIT_NAMES[int(d)] for d in word)
            continue
        after_bearing = word == "bearing"
        words.append(_DIGIT_WORDS.get(word, word))
    return " ".join(_collapse_repeats(words))


def normalized_phrase_index() -> dict[str, str]:
    """`normalize_for_match`ed phrasing -> token, for scoring lookups.

    A collision here would mean two tokens becoming indistinguishable
    after normalization, which would silently make one of them
    unreachable, so it is an error rather than a last-write-wins dict.
    """
    index: dict[str, str] = {}
    for token in TOKENS:
        for phrase in PHRASES[token]:
            key = normalize_for_match(phrase)
            existing = index.get(key)
            if existing is not None and existing != token:
                raise ValueError(
                    f"normalization collapses {token!r} and {existing!r} "
                    f"onto the same text {key!r}"
                )
            index[key] = token
    return index


#: Number words a recognizer may return in place of digits, for the
#: bearing parser. Wider than `_DIGIT_NAMES` because whisper writes some
#: digits as words and others numerically in the same sentence.
_WORD_DIGITS: dict[str, str] = {name: str(i) for i, name in enumerate(_DIGIT_NAMES)}


class BearingParse:
    """Outcome of reading a numeric bearing out of a transcript.

    Three outcomes rather than two, and the third is the useful one.
    `degrees` set means a legal bearing was read. `degrees is None` with
    `heard` set means digits were found but they do not name a legal
    bearing -- which is a *detected* recognition error, not a silent one.
    Both `None` means no bearing was spoken at all.
    """

    __slots__ = ("degrees", "heard")

    def __init__(self, degrees: int | None, heard: int | None) -> None:
        self.degrees = degrees
        self.heard = heard

    def __repr__(self) -> str:
        return f"BearingParse(degrees={self.degrees}, heard={self.heard})"


def parse_bearing(text: str) -> BearingParse:
    """Read a bearing from recognizer output after the word "bearing".

    Accepts digits and number words interchangeably ("bearing 320",
    "bearing three two zero", "bearing 3 2 0"), because recognizers mix
    the two freely -- whisper returned "3" for a spoken "three" in one
    clip and spelled it out in another.

    **The 5 degree resolution is a checksum, and that is the point.**
    Bearings are constrained to multiples of five, so roughly four out of
    five possible mishearings land on a value that cannot be a real
    bearing. Those are returned as `heard` without `degrees`, so the
    caller can ask the player to say again rather than turning to a
    number nobody said. A wrong heading flown confidently is a far worse
    failure than one more readback, and this makes most of that class
    detectable for free.

    It cannot catch everything: a mishearing that lands on another
    multiple of five ("three two zero" heard as "three three zero") is
    indistinguishable from a correct reading here, and only the readback
    protects against it.
    """
    normalized = normalize_for_match(text)
    words = normalized.split()
    if "bearing" not in words:
        return BearingParse(None, None)

    digits: list[str] = []
    for word in words[words.index("bearing") + 1 :]:
        if word in _WORD_DIGITS:
            digits.append(_WORD_DIGITS[word])
        elif word.isdigit():
            digits.extend(word)
        else:
            break
    if not digits:
        return BearingParse(None, None)

    value = int("".join(digits))
    if value > 359 or value % BEARING_RESOLUTION_DEG != 0:
        return BearingParse(None, value)
    return BearingParse(value, value)


#: `follow`'s three slot parsers (`plans/watch-reporting/plan.md` Decision
#: 2b-i), siblings of `parse_bearing` above. Unlike `parse_bearing`, none
#: of the three is anchored on a single fixed marker word the way
#: `"bearing"` anchors a numeric heading -- `parse_clock` looks for a
#: number word immediately before `"o'clock"`, `parse_range_km` for one
#: immediately before a distance unit, `parse_descriptor` for any word in
#: the closed descriptor set, each scanning the whole normalised
#: transcript rather than requiring a fixed position.

#: Reverse of `_CLOCK_WORDS` -- number word -> forward-hemisphere hour.
_CLOCK_WORD_TO_HOUR: dict[str, int] = {
    word: hour for hour, word in _CLOCK_WORDS.items()
}


def parse_clock(text: str) -> int | None:
    """The clock-position slot -- a number word immediately before
    `"o'clock"` (`normalize_for_match` has already folded every apostrophe
    variant onto `"o'clock"` and, via `_DIGIT_WORDS`, a single recognised
    digit like `"3"` onto its word form `"three"`, so both spellings reach
    this function identically). Restricted to `FORWARD_CLOCK_POSITIONS`
    (via `_CLOCK_WORD_TO_HOUR`), the same no-omniscience reason every other
    clock-taking token in this vocabulary is restricted -- a rear-hemisphere
    hour cannot resolve here at all, by construction. `None` if no
    recognised clock phrase is found anywhere in `text`."""
    words = normalize_for_match(text).split()
    for index, word in enumerate(words):
        if word == "o'clock" and index > 0:
            hour = _CLOCK_WORD_TO_HOUR.get(words[index - 1])
            if hour is not None:
                return hour
    return None


#: Number words 1-20 for the range slot -- wider than `_DIGIT_NAMES`
#: (0-9), since a kilometre range legitimately runs up to
#: `crew_console`'s own cap. Recognisers spell small numbers as words and
#: larger ones as digits inconsistently (`parse_bearing`'s own docstring
#: makes the identical observation), so `parse_range_km` below checks both
#: forms rather than assuming one.
_RANGE_NUMBER_WORDS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}

#: Distance-unit words the range slot recognises -- "km"/"kilometre(s)"/
#: "klick(s)" (`plans/watch-reporting/plan.md` Decision 2b-i's own list),
#: both spellings of "kilometre" included since a recognizer trained on
#: American English may emit either.
_RANGE_UNIT_WORDS: frozenset[str] = frozenset(
    {"km", "kilometre", "kilometres", "kilometer", "kilometers", "klick", "klicks"}
)


def parse_range_km(text: str) -> int | None:
    """The range slot -- a number immediately before a distance-unit word.
    **Constrained to 1-20, with no checksum** (unlike `parse_bearing`'s 5
    degree resolution, which rejects roughly four in five mishearings):
    whole kilometres have no such redundancy, so "three" heard as "two" is
    a legal, undetectable value here -- the readback is the only
    protection. `None` if no recognised range phrase is found anywhere in
    `text`, or the number before the unit is out of range."""
    words = normalize_for_match(text).split()
    for index, word in enumerate(words):
        if word in _RANGE_UNIT_WORDS and index > 0:
            number_word = words[index - 1]
            value: int | None = None
            if number_word.isdigit():
                value = int(number_word)
            elif number_word in _RANGE_NUMBER_WORDS:
                value = _RANGE_NUMBER_WORDS[number_word]
            if value is not None and 1 <= value <= 20:
                return value
    return None


#: The closed descriptor vocabulary (`plans/watch-reporting/plan.md`
#: Decision 2b-ii) -- **exactly the words Petrovich himself speaks**,
#: `belief.speech._OP_CLASS_DISPLAY`'s vocabulary plus `"group"` (the
#: user's own example word, matching `cardinality.lo > 1`). A hand-synced
#: mirror, like every other cross-subproject vocabulary table in this
#: file (module docstring) -- `audio-adapter` cannot import `body-layer`'s
#: `belief.speech` module (module independence). Type names are
#: deliberately not admitted -- an open set cannot be enumerated into a
#: closed grammar, and a type-level descriptor only helps once a contact
#: is already type-classified (Decision 2b-ii's own reasoning).
DESCRIPTOR_WORDS: tuple[str, ...] = (
    "armor",
    "truck",
    "infantry",
    "sam",
    "aaa",
    "ship",
    "group",
)


def parse_descriptor(text: str) -> str | None:
    """The descriptor slot -- the first `DESCRIPTOR_WORDS` member found
    anywhere in the normalised transcript, or `None`. `DESCRIPTOR_WORDS`
    order is the tie-break when a transcript somehow contains more than
    one (not expected in practice for a single referring expression)."""
    words = set(normalize_for_match(text).split())
    for descriptor in DESCRIPTOR_WORDS:
        if descriptor in words:
            return descriptor
    return None


#: The two verbs the slotted `report` token admits (`plans/crew-query-path/
#: plan.md` Decision A) -- both fuzzy-tested at `command_matcher.VERB_FLOOR`,
#: so **every** slotted form works under either verb. `"describe"` shipped
#: 2026-10-05 as a bare `report_all` phrasing only; listing it here is what
#: makes it a substitutable verb rather than merely an anchorable one.
_REPORT_VERBS: tuple[str, ...] = ("report", "describe")


def report_verbs() -> tuple[str, ...]:
    """`_REPORT_VERBS`, for `command_matcher.py`'s report branch. A
    function rather than a re-exported name so the table has exactly one
    home, matching `DESCRIPTOR_WORDS`' own single-home posture."""
    return _REPORT_VERBS


#: The `where` slot's cardinal half -- the same eight compass words
#: `report_bearing_*`/`scan_bearing_*` already spell out, as a *slot*
#: rather than eight enumerated tokens. Hand-synced with body-layer's
#: `belief.crew_console._SECTOR_SCAN_LABELS` (module independence -- see
#: `DESCRIPTOR_WORDS`' identical note); a test on each side asserts its own
#: table's membership so a drift fails a test rather than a sortie.
SECTOR_WORDS: tuple[str, ...] = (
    "north",
    "northeast",
    "east",
    "southeast",
    "south",
    "southwest",
    "west",
    "northwest",
)


def parse_sector_word(text: str) -> str | None:
    """The cardinal `where` slot -- the first `SECTOR_WORDS` member found
    anywhere in the normalised transcript, or `None`.

    Matched **word by word against the whole word**, never as a substring:
    `normalize_for_match` has already folded `"north east"` onto
    `"northeast"`, and a substring test would let `"north"` match inside
    `"northeast"` and resolve the wrong sector. (This project has shipped
    that exact bug once before, in a coverage floor's bare-substring
    scan.) `SECTOR_WORDS` order is the tie-break, as in
    `parse_descriptor`."""
    words = set(normalize_for_match(text).split())
    for sector in SECTOR_WORDS:
        if sector in words:
            return sector
    return None


#: The `where` slot's ownship-relative half -- **this is `BL-B28`**
#: (`plans/crew-query-path/plan.md`'s first measured finding: there is no
#: `report_left`/`report_right` token at all, so `"report left"` resolved
#: to `report_bearing_e` at ratio 0.75 -- *report east*). The four values
#: are exactly body-layer's `perception.gaze.RelativeSector` literals, the
#: same table `belief.attention.project_relative_area` reads, so
#: `report left` and `scan left` agree on what "left" means by
#: construction. Hand-synced mirror, like `SECTOR_WORDS` above.
RELATIVE_WORDS: tuple[str, ...] = ("left", "right", "ahead", "full")


def parse_relative_word(text: str) -> str | None:
    """The ownship-relative `where` slot -- the first `RELATIVE_WORDS`
    member found anywhere in the normalised transcript, or `None`. Whole-word
    matching and `RELATIVE_WORDS` order as the tie-break, exactly as
    `parse_sector_word` above."""
    words = set(normalize_for_match(text).split())
    for relative in RELATIVE_WORDS:
        if relative in words:
            return relative
    return None


#: `greeting`'s closed slot vocabulary (`[[BL-B81]]`) -- hand-synced
#: mirror of body-layer's `belief.crew_console._GREETING_TIMES_OF_DAY`
#: (module independence -- see `DESCRIPTOR_WORDS`' identical note above),
#: which must accept exactly these four values and no others.
TIME_OF_DAY_WORDS: tuple[str, ...] = ("morning", "day", "evening", "night")


def parse_time_of_day(text: str) -> str | None:
    """The `greeting` slot -- the first `TIME_OF_DAY_WORDS` member found
    anywhere in the normalised transcript, or `None`. Whole-word matching
    and `TIME_OF_DAY_WORDS` order as the tie-break, exactly as
    `parse_sector_word`/`parse_relative_word` above."""
    words = set(normalize_for_match(text).split())
    for time_of_day in TIME_OF_DAY_WORDS:
        if time_of_day in words:
            return time_of_day
    return None


#: The `how far` slot's spoken vocabulary -> band name. Several spoken forms
#: per band because this is the slot the pilot phrases most loosely, and
#: the multi-word forms decision 12 gives (*"close in"*, *"medium
#: distance"*, *"far out"*) are all discriminated by their **first** word,
#: so a single word-level table covers them without a phrase matcher.
#:
#: The band *boundaries* (2 km / 5 km) are body-layer's, not this module's
#: -- a recogniser has no business knowing metres. `BAND_WORDS`' values are
#: the three band names that cross the seam; body-layer's
#: `belief.crew_console._REPORT_BAND_BOUNDS_M` is the hand-synced mirror
#: holding the numbers, with a membership test on each side.
#:
#: **`"close"` is the one collision worth measuring** (`plans/
#: crew-query-path/plan.md`'s Risks): it is phonetically near `"clock"`,
#: which the clock slot also consumes. Unbenched on this user's voice, like
#: every token added without re-recording the corpus.
BAND_WORDS: dict[str, str] = {
    "near": "near",
    "close": "near",
    "medium": "medium",
    "mid": "medium",
    "far": "far",
    "distant": "far",
    "long": "far",
}


def parse_band(text: str) -> str | None:
    """The `how far` slot -- the band of the first `BAND_WORDS` key found
    in the normalised transcript, in **transcript order** (unlike
    `parse_descriptor`/`parse_sector_word`, whose tie-break is their own
    table's order: a band has several synonyms per value, so "whichever
    the pilot said first" is the only ordering that means anything).
    `None` if no band word is present."""
    for word in normalize_for_match(text).split():
        band = BAND_WORDS.get(word)
        if band is not None:
            return band
    return None


#: `step`'s own direction slot (`plans/attack-run/plan.md` Decision 6,
#: `docs/concept/Attacking target.md`'s *"step [count]
#: left/right/near|closer|close/far|further/away"*) -- several spoken
#: forms per value, the same reasoning `BAND_WORDS` above gives, since
#: this is another slot with more than one synonym per value.
#: Deliberately reuses the same words `RELATIVE_WORDS`/`BAND_WORDS`
#: already carry for a *different* slot (`report`/`select_target`'s
#: `where`/`how far`) -- there is no collision because `step`'s own verb
#: anchors the branch before this table is ever consulted
#: (`command_matcher.py`'s step-slot branch), so "report left" and "step
#: left" are never compared against each other.
STEP_DIRECTION_WORDS: dict[str, str] = {
    "left": "left",
    "right": "right",
    "near": "near",
    "closer": "near",
    "close": "near",
    "far": "far",
    "further": "far",
    "farther": "far",
    "away": "far",
}


def parse_step_direction(text: str) -> str | None:
    """`step`'s direction slot -- the first `STEP_DIRECTION_WORDS` key
    found anywhere in the normalised transcript, **transcript order**
    (the same tie-break `parse_band` uses, for the identical reason: a
    direction has several synonyms, so "whichever the pilot said first"
    is the only ordering that means anything). `None` if no direction
    word is present."""
    for word in normalize_for_match(text).split():
        direction = STEP_DIRECTION_WORDS.get(word)
        if direction is not None:
            return direction
    return None


#: `step`'s optional count slot -- small number words only (1-9), unlike
#: `_RANGE_NUMBER_WORDS`' wider 1-20: a step count names how many units
#: to skip within one group, which this project's own measured undercount
#: (`BL-12`: 4 records for 6 real units) bounds well below a range in
#: kilometres.
_STEP_COUNT_WORDS: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
}


def parse_step_count(text: str) -> int | None:
    """`step [<count>] left/right/near/far`'s optional count slot -- the
    first number word or digit anywhere in the normalised transcript, or
    `None` when the player said no count at all (`_parse_step_slots`
    then defaults to 1, matching the spec's own `"[count]"` optional-
    bracket notation). Both digits (`"2"`) and number words (`"two"`) are
    recognised, mirroring `parse_range_km`'s identical two-form handling.
    """
    for word in normalize_for_match(text).split():
        if word.isdigit():
            value = int(word)
            if value >= 1:
                return value
        else:
            count = _STEP_COUNT_WORDS.get(word)
            if count is not None:
                return count
    return None


#: `engage`'s weapon slot (`plans/attack-run/plan.md` Decision 15) --
#: *"allow weapon token, but do not require it. Nothing consumes it yet,
#: but it will become important later"*. Three words, closed, since this
#: is naming one of the aircraft's own weapon classes, not an open set.
WEAPON_WORDS: tuple[str, ...] = ("guns", "rockets", "missiles")


def parse_weapon(text: str) -> str | None:
    """The weapon slot -- the first `WEAPON_WORDS` member found anywhere
    in the normalised transcript, or `None`. Whole-word matching and
    `WEAPON_WORDS` order as the tie-break, exactly as `parse_sector_word`/
    `parse_relative_word` above."""
    words = set(normalize_for_match(text).split())
    for weapon in WEAPON_WORDS:
        if weapon in words:
            return weapon
    return None


#: Framing sentence for `to_prompt`. Whisper's initial prompt conditions
#: the decoder on *style and domain* as much as on individual words, so
#: naming the setting does work that a bare word list does not: "this is
#: helicopter crew intercom" makes clipped imperatives plausible, which
#: is exactly the register these commands are spoken in.
_PROMPT_FRAMING = "Helicopter crew intercom, pilot to gunner."

#: Spellings the prompt should carry in a form other than the lowercase
#: one `recognised_words` returns. "Petrovich" is a proper noun and the
#: routing discriminator; a general-English decoder has no reason to
#: prefer it over "Petrovitch" or "petro which". "SAM"/"AAA" are spoken as
#: acronyms, and lowercase "sam" reads as a name -- the 2026-10-15 log has
#: "set target, long range, same ahead".
_PROMPT_DISPLAY_FORMS: dict[str, str] = {
    "petrovich": "Petrovich",
    "sam": "SAM",
    "aaa": "AAA",
}


def recognised_words() -> tuple[str, ...]:
    """Every distinct word the recogniser is expected to hear: each word of
    every `PHRASES` phrasing, then every slot table's words, lowercase, in
    first-seen order.

    This is the set `to_prompt` must carry in full (`test_vocabulary.py`
    asserts it). **A word the matcher acts on belongs in one of these
    tables**, never only as a literal in `command_matcher.py` -- a word
    whisper is not biased toward comes back as a near-homophone ("silence"
    as "violence", 2026-10-15) and the pilot gets "say again" (user
    direction 2026-10-23: vocabulary and prompt kept in sync as a rule).
    """
    sources: list[str] = [p for token in TOKENS for p in PHRASES[token]]
    sources += [
        *DESCRIPTOR_WORDS,
        *SECTOR_WORDS,
        *RELATIVE_WORDS,
        *TIME_OF_DAY_WORDS,
        *BAND_WORDS,
        *STEP_DIRECTION_WORDS,
        *WEAPON_WORDS,
    ]
    words: dict[str, None] = {}
    for source in sources:
        for word in re.findall(r"[a-z']+", source.lower()):
            words[word] = None
    return tuple(words)


def to_prompt() -> str:
    """An initial prompt biasing whisper toward this vocabulary.

    Unlike `to_gbnf`, this is a **soft** bias: it makes these words more
    likely without making anything else impossible. That difference is
    the entire reason this exists. A grammar cannot decline -- when the
    audio fits nothing, it must still emit something legal, so a
    mishearing becomes a confident wrong command. Measured on this
    project's own corpus, constrained decoding turned "watch nearest air
    defence" into "what do you see" at confidence 0.82, seven times over.
    A prompted decoder producing "what do you see" for that audio would
    have to actually hear it that way, and a mishearing still comes back
    looking wrong, which is what lets fuzzy matching reject it.

    **Every recognised word once, space-joined** -- not a sample of whole
    phrasings. whisper.cpp keeps only the last `n_text_ctx/2` = 224 prompt
    tokens and drops the front, so the prompt cannot simply list all 123
    phrasings (~300 GPT-2 tokens); sampling 24 of them instead left most
    commands added after the 2026-09-19 bench (silence, engage, set
    target, describe...) and every slot word (SAM, guns, closer...) out of
    the prompt entirely. The word list is ~135 tokens. Commas are omitted
    because each costs a token. Benched 2026-10-23 on the 252-clip corpus,
    `small.en`: 249/252 against the sampled prompt's 248/252, p90 0.86 s
    against 2.10 s (the sampled prompt provoked repetition loops such as
    "scan ahead, scan north, scan north, ..."); a phrase-fragment variant
    scored 247/252. The corpus predates the new commands, so this shows
    no regression on the old ones, not the gain on the new.
    """
    words = [_PROMPT_DISPLAY_FORMS.get(w, w) for w in recognised_words()]
    return f"{_PROMPT_FRAMING} {' '.join(words)}."
