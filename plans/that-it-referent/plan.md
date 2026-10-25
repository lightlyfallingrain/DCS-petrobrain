### Goal

When a player command uses "it" or "that" instead of naming a contact, resolve it to the
contact/group Petrovich last spoke about (bare), or to a qualified match within his recent
mentions (typed/clock/group-qualified) — on existing contact-taking command tokens only, no new
tokens, no new pronouns.

### Facts this plan is built on (measured, 2026-10-26)

- `CrewConsole._print` (`body-layer/src/belief/crew_console.py:4728`) is the single speech funnel,
  26 call sites. It already threads optional per-call metadata through
  (`attack_run_fields`, `correlation_id`) with `None` defaults — the same shape this plan adds
  `mentions` to.
- `_strip_filler`/`find_contact` (`belief/utterance.py`) already strip a leading "that"/"the" and
  do a **type** search ("that shilka") — not a referent, and not touched by this plan except for
  one fallback (Stage 4).
- `command_matcher.normalize_for_match`/`FILLER_WORDS` (`audio-adapter/src/command_matcher.py:208`)
  deliberately do **not** strip "it"/"that"/"this" — measured and commented as carrying meaning.
  So both words survive into every slot parser untouched; no normalization change needed to see
  them.
- `follow`/`report`/`select_target`/`engage`/`point`/`greeting` already use the same five-slot
  schema pattern (`descriptor`/`clock`/`sector`/`relative`/`band`, parsed by `vocabulary.
  parse_descriptor`/`parse_clock`/`parse_sector_word`/`parse_relative_word`/`parse_band`) tried in
  dedicated branches **before** the generic phrase table in `match_transcript`
  (`command_matcher.py:707`). `DESCRIPTOR_WORDS` already includes `"group"`
  (`vocabulary.py:1114`), and `crew_console._parse_target_slots` already treats
  `descriptor == "group"` as a first-class value. A referent slot is an additive sixth slot on
  this same schema — no new parsing idiom.
- `where_is_it` is the one token with **no slots at all** today — always bound to the attack
  target (`CrewConsole.drain_where_is_it`, `crew_console.py:3298`, via
  `_active_attack_target_task()`), answering `render_no_target()` when none is set. Its three
  recorded phrasings (`"where is it"`, `"where is target"`, `"where is it now"`,
  `vocabulary.py:691`) all currently mean the same thing.
- `mark_target` also has **no slots** (`crew_console.py:2797`) and is unconditionally bound to the
  attack target, but its underlying write (`self.mark_target_fn(contact_id, now_sim)`) already
  takes an arbitrary `contact_id` — only the *selection* is hardcoded, not the mechanism.
- `follow`'s resolved winner already gets its group-mates tagged `"watch"` via
  `_mark_watched_with_group` (`crew_console.py:2589`) whenever the winner belongs to a
  multi-member group — i.e. "follow a group" already reduces to "follow one contact, watch the
  rest" today, for the non-referent case. `select_target`/`engage`'s slotted branch does the
  identical reduction (`crew_console.py:2753`/`:3047`).
- `speech.group_membership_state` (public, `speech.py:2643`) already returns
  `(member_contact_ids, leading_contact_id, differentiated)` for a `Group`, where
  `leading_contact_id` is computed by `_leading_index` — **the widest resolvable engagement
  envelope** (`belief.threat.envelope_for`), i.e. the existing "most threatening member" selection
  decision 3 asks for. No new selection logic needed — reuse this function.
- `crew_console._report_scope` (`crew_console.py:3899`) is the one true "which contacts match
  descriptor/clock/sector/relative/band" filter, already shared by `report` and
  `_resolve_attack_target`. It filters over **every current contact** — it has no notion of "only
  these candidate ids."
- `Contact.last_position`/`position: PositionEstimate` (`contacts.py:262`) is a believed-position
  accessor that works whether or not the contact is currently observed — satisfies decision 4 ("use
  belief if not visible") with no new accessor needed.
- `tuning.py` pattern for a new scalar: `tuning.real("<module.path>.<NAME>", default, lo=, hi=,
  status="judgement")` (e.g. `belief/decay.py:76`'s `IDENTITY_HALF_LIFE_S`).
- `speech.render_unable(reason)` (`speech.py:490`) is the existing "unable, `<reason>`" renderer —
  reused verbatim for decision 7, no new phrasing primitive.
- The existing `"<unit type>[, <clock> o'clock, <range> km][ <semantic fact>]."` pattern
  (`speech.py:2101`/`:2232`/`:3289`, built from `describe_contact`'s own `facts`) already carries
  clock/range/world-reference text — the shape decision 1's `"<o'clock> <distance in km> <world
  ref>"` answer needs, reused rather than invented.

### Affected Modules / Files

- **`body-layer/src/belief/referent.py` (new)** — `Mention` (`kind: Literal["contact","group"]`,
  `id: str`, `t_sim: float`), `ReferentMemory` (`record`, `recent(now_sim)`, `last(now_sim)`,
  window-pruned by `REFERENT_WINDOW_S`), and `resolve_referent(...)` — the one resolver every
  referent-bearing command calls (see Design below). `REFERENT_WINDOW_S` tunable declared here.
- **`body-layer/src/belief/crew_console.py`** — `CrewConsole._print` gains an optional `mentions:
  list[Mention] | None = None` kwarg, recording into a new `self._referent_memory:
  ReferentMemory` field. Each `_print` call site that has a known subject in scope passes it
  (audited list below). `_report_scope` gains an optional `restrict_to_ids: Collection[str] |
  None = None` so `resolve_referent` can reuse its filter predicate instead of a second copy.
  `_handle_where_is_it`/`drain_where_is_it`, `_handle_follow`, `_handle_select_target`,
  `_handle_engage` each gain the referent branch (Stages 2-3).
- **`body-layer/src/belief/utterance.py`** — Stage 4 only: `find_contact`'s caller falls back to
  `resolve_referent` when `_strip_filler` leaves nothing to search on.
- **`body-layer/src/mission_memory/marks.py`/`crew_console._handle_mark_target`** — Stage 4 only:
  referent-selected contact_id in place of the hardcoded attack-target lookup.
- **`audio-adapter/src/vocabulary.py`** — `REFERENT_WORDS = ("it", "that")` and `parse_referent
  (text) -> str | None`, next to `parse_descriptor`.
- **`audio-adapter/src/command_matcher.py`** — `_parse_follow_slots`/`_parse_select_slots`/
  `_parse_engage_slots` each gain a `referent` slot (additive, same shape as the existing five).
  New `_parse_where_is_it_slots` and its own matcher branch (new `_WHERE_VERB = "where"`), ordered
  with the other slotted branches before the phrase table.
- Tests in both subprojects per stage (see below).

### Design

**One resolver, reused everywhere.** `resolve_referent(store, memory, now_sim, *, explicit_target:
bool, descriptor, clock, sector, relative, band, active_attack_target_id: str | None) ->
tuple[str | None, list[str]]` (contact id or failure lines, mirroring `_resolve_follow_target`'s/
`_resolve_attack_target`'s own return shape so callers don't branch differently):

1. `explicit_target=True` (the literal word "target" was heard) — not this resolver's concern at
   all; the caller keeps today's attack-target binding unchanged. This is how "where is target"/
   "mark target" keep meaning exactly what they mean today.
2. Otherwise, prune `memory.recent(now_sim)` to the window. Empty → `render_unable("nothing to
   refer to").text` (decision 7).
3. No qualifier (`descriptor`/`clock`/`sector`/`relative`/`band` all `None`) → `memory.last(now_sim)`
   (decision 2, "the last line wins").
4. A qualifier present → filter `memory.recent(now_sim)`'s candidate ids through
   `_report_scope(..., restrict_to_ids=<those ids>)` (decision 2's "search the recent mentions for
   a match"). Zero matches → `render_unable("no match for that")`. More than one → ask (reuses the
   existing ambiguity-refusal shape `_resolve_follow_target`'s docstring already names as this
   project's standing answer to a tie it does not want to break itself).
5. **Decision 2's target-priority clause**: before returning a qualified match, if
   `active_attack_target_id` is itself among the matches, it wins over any other match — "if
   attack target is AAA which would take priority."
6. **Group → single-contact reduction (decision 3)**: whatever step 3-5 resolved, if it is a
   `Mention(kind="group")`, resolve to `speech.group_membership_state(...)`'s own
   `leading_contact_id` (most-threatening member) — reusing the exact selection speech.py already
   uses for group disclosure, not a second "which member" rule. This also *is* "that group" (a
   verb that cannot take a bare group — none in scope can — gets the group's lead member, and
   `_mark_watched_with_group`'s existing group-mate tagging covers "the rest of the group" for
   every caller that already calls it). No separate group-id return path is needed: every existing
   consumer (`follow`, `select_target`, `engage`, `where_is_it`, `mark_target`) only ever wanted a
   contact id.

**Mention recording is centralized in `_print`, not duplicated at each call site.** `_print(lines,
now_sim, mentions=[...])` records once per logical reply/line-batch — satisfies decision 1 ("every
line... the last line wins") and avoids the `BL-B71` failure class (a construction/call site
silently not carrying a co-moving piece of state forward) by making the recording a property of
the one funnel rather than per-caller discipline alone. Callers that pass nothing record nothing —
safe default — but the **audit is still required**, because a caller that has a subject and
forgets to pass it is exactly the silent miss this plan must not reproduce. Grepping the 26
`self._print(` call sites (`crew_console.py:1624` through `:4609`), the ones with a known subject
to pass:

| call site (approx. line, pre-plan) | subject |
|---|---|
| callouts / group disclosure (`drain_events` path, `:1831`/`:2106`/`:2231`) | event's `contact_id`/`group_id` |
| `_act`'s `describe_contact`/`set_attention` readback (`:4700`/`:4707` via `_print` callers) | `parse.referenced_contact_id` |
| `_handle_follow`'s deferred readback (`:2606`) | resolved `contact_id` |
| `_handle_select_target`'s deferred readback | resolved `contact_id` |
| `_handle_engage`'s deferred readback | resolved `contact_id` |
| `drain_attack_run`'s steering line (decision 2: "attack-run steering lines included") | `state.last_contact_id` |
| `drain_where_is_it`'s answer | the contact it just answered about (target or referent) |
| `_handle_mark_target`'s echo | the marked `contact_id` |
| report/describe replies (`_handle_report`/`_handle_slotted_report`) | every contact in `scope.facts`, as a batch |

Lines with **no** subject (silence ack, config-error line, usage/say-again lines, radio check,
greeting, `render_lost_contact`, `render_no_target`) pass nothing — a `lost`/`no target` answer
must not plant a referent for a contact that no longer resolves.

### Co-moving Fields

`where_is_it_requested`/a new `where_is_it_slots` are a one-shot request pair, set together on
command and consumed together by `drain_where_is_it` — the same shape existing one-shot signals
(`requested_optic`) already use, and the shape `BL-B71`'s own miss was in.

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| `where_is_it_requested` | external (voice command `where_is_it`) | `_handle_where_is_it` sets it | both `True` |
| `where_is_it_slots` | external (voice command `where_is_it`) | `_handle_where_is_it` sets it | holds the same dispatch's slots, never a stale previous command's |
| `where_is_it_requested` | internal (`drain_where_is_it`) | consumed | reset to `False` |
| `where_is_it_slots` | internal (`drain_where_is_it`) | consumed | reset to `None` in the same call, never left holding a consumed request |

### Implementation Plan

1. **Core mechanism.** `belief/referent.py`: `Mention`, `ReferentMemory`, `REFERENT_WINDOW_S`
   tunable (`tuning.real("belief.referent.REFERENT_WINDOW_S", 60.0, lo=15.0, hi=180.0,
   status="judgement")`), `resolve_referent`. `_print` gains `mentions`; audit and wire every call
   site in the table above. `_report_scope` gains `restrict_to_ids`. Unit tests: window pruning,
   bare-last, qualified-filter, target-priority tie-break, group→lead-member reduction, ambiguous
   refusal, expired/empty → `render_unable`.
2. **`where_is_it`.** `vocabulary.REFERENT_WORDS`/`parse_referent`; `command_matcher.
   _parse_where_is_it_slots` (explicit-"target" flag, else the five-slot qualifier) and its
   matcher branch. Body: `_handle_where_is_it(slots)` stores `where_is_it_slots` alongside the
   existing one-shot flag; `drain_where_is_it` branches on `explicit_target` (old behavior,
   unchanged) vs. referent (calls `resolve_referent`, then renders `describe_contact`'s facts
   through the existing clock/range/world-ref pattern — reuse, do not invent a new renderer).
   Tests: "where is it"/"where is that" during an active run resolve to the engaged target exactly
   as before unless something else was mentioned more recently; "where is that AAA" resolves to
   the AAA even with a target engaged; "where is target" is untouched; expired → "unable."
3. **`follow`/`select_target`/`engage`.** Add the `referent` slot to `_parse_follow_slots`/
   `_parse_select_slots`/`_parse_engage_slots` (a bare referent alone now makes the slots dict
   non-empty, where today it would be `None` and fall through to "say again"/bare-engage-resume).
   Body: each handler's "no slots at all" branch is replaced with "no slots **and** no referent";
   when a referent was heard, call `resolve_referent` instead of `_resolve_follow_target`/
   `_resolve_attack_target`. **Decided here, local/reversible**: "engage it"/"engage that" is
   treated identically to an engage with an explicit descriptor/clock — select-then-engage the
   resolved contact — rather than colliding with bare `engage`'s "resume the already-selected run"
   meaning, since a heard referent is itself a positive signal the player means a specific contact.
   Tests per the user's own examples: "target that/it" after "unit in 11 o'clock group is armor";
   "follow that group"; "engage that 11 o'clock armor, missiles" (qualified, picks the 11 o'clock
   group over the 2 o'clock one from the same `describe` batch).
4. **(Separate, smaller, cuttable without touching 1-3) `mark_target` and the `watch` family.**
   `mark_target` gains the same explicit-"target"-vs-referent split as `where_is_it`, routing the
   resolved contact id into the existing `mark_target_fn(contact_id, now_sim)` call unchanged.
   `"watch that"/"watch it"` do not go through `command_matcher` at all today — they are a bare
   verb with no recognized token, so they reach the brain-escalation path
   (`utterance.find_contact`/`_strip_filler`) and fail as a type search on empty text. Fallback:
   when `_strip_filler` leaves nothing (or the type search finds nothing), try
   `resolve_referent` before giving up. No audio-adapter change needed for this one — it is not a
   `command_matcher` token.

### Risks & Unknowns

- **Mention-recording completeness is an audit, not a mechanism** — the funnel (`_print`) makes a
  forgotten subject *safe* (nothing recorded, not a crash), but a forgotten subject is still a
  silently-missing referent. The table above is the audit's starting point; Reviewer should re-grep
  `self._print(` after Stage 1 lands, the same discipline `BL-B71`'s retro asked for.
- **"Where is it" changes meaning for existing players mid-run** who say "where is it" expecting
  the target: in practice the attack-run steering chatter keeps re-mentioning the target every few
  seconds (decision 2 explicitly includes steering lines), so bare "where is it" still resolves to
  the target almost all the time once engaged — the divergent case is exactly the one the user
  asked for ("where is that AAA" when AAA isn't the target).
- **`group_membership_state` returns `None` when fewer than two members still resolve** — the
  referent resolver must fall back to any single resolvable member of the group rather than
  failing outright in that case (a group that's shrunk to one live contact is still a valid
  referent).
- Stage 4's `mark_target`/`watch`-family extension is smaller and lower-certainty (neither was in
  the user's own examples); cutting it costs nothing to Stages 1-3.

### Second-order effect

Establishes `belief/referent.py`'s `Mention`/`ReferentMemory` as the one place "what was Petrovich
just talking about" lives — any future conversational-memory feature (BL-10/SRS free-speech
follow-ups, `plans/brain-layer/explore-notes.md` §4) has a state param to read rather than
reinventing a second notion of "recency," so it narrows rather than complicates that later work.

### Decisions Requiring User Input

- Whether to build Stage 4 (`mark_target`/`watch` family) now or defer it — not illustrated in the
  user's own examples, and the explore notes left it open. Recommend building it: it's cheap given
  Stage 1's mechanism, and cutting it later costs nothing already spent on Stages 1-3.
