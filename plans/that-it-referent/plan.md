### Goal

When a player command uses "it" or "that" instead of naming a contact, resolve it to the
contact/group Petrovich last spoke about (bare), or to a qualified match among his recent
mentions (type/clock/group-qualified) — on existing contact-taking command tokens only, no new
tokens, no new pronouns.

**Process note, so the record is honest:** a fork dispatched to survey the code (not to design)
went beyond its brief and wrote and committed its own plan to this same path (`844ed9f4`). Its
measured facts independently agreed with this pass's own, and several of its mechanics were
genuinely better than this pass's first draft (`_report_scope`'s `restrict_to_ids` reuse, the
`_print` call-site audit table, the Co-moving Fields table for `where_is_it`'s one-shot signal
pair) — adopted below with attribution where it matters. Two of its claims were checked against
running code and found wrong (see Design, "watch", and the ambiguity tie-break) and are corrected
here, not carried over. This plan, not `844ed9f4`, is the one the user should treat as current;
`844ed9f4` stays in history rather than being rewritten.

### Facts this plan is built on (measured, 2026-10-26 — re-checked against running code, not just read)

- `CrewConsole._print` (`body-layer/src/belief/crew_console.py:4728`) is the single speech funnel,
  ~26 call sites. It already threads optional per-call metadata through with `None` defaults
  (`attack_run_fields`, `correlation_id`) — the same shape this plan adds a `mentions` kwarg to.
- `_speak_or_defer`/`_PendingPositionalReply`/`drain_pending_positional_replies`
  (`crew_console.py:1757-1834`) is what actually *calls* `_print` for every positional readback
  (`select_target`, `mark_target`, `step`, `follow`, `watch_nearest*`, `report`) — the deferred
  `render` closure already has its `contact_id` bound at *dispatch* time, but `_print` only runs at
  the later tick the channel is actually clear. **Recording a mention inside `_print` itself,
  not at dispatch, is what gives "the last line wins" (explore-notes Decision 2) for free**: speak
  order and mention order become the same thing by construction, with no extra bookkeeping for
  the deferred-vs-immediate distinction.
- `_strip_filler`/`find_contact` (`belief/utterance.py`) already strip a leading "that"/"the" and
  do a **type** search ("that shilka") — a different, pre-existing mechanism, not a referent, and
  untouched by this plan.
- `command_matcher.normalize_for_match`/`FILLER_WORDS` (`audio-adapter/src/command_matcher.py:208`)
  deliberately do **not** strip "it"/"that" — measured and commented as carrying meaning. Both
  words survive into any new slot parser untouched; no normalisation change needed.
- **Verified by running `match_transcript` directly** (not assumed): `"watch that"`, `"watch it"`,
  `"follow it"`, `"target it"`, `"mark it"` all return `verb_anchored=True, token=None` today —
  every one of them anchors (`"watch"`/`"follow"`/`"mark"` are all real first words of existing
  phrasings, so `VERB_ANCHOR_WORDS` already contains them) and then fails the phrase table, which
  `classify_response` turns into `"say_again"`, **never** `"fallthrough"` to the brain-escalation
  path. This matters: all five of these phrasings must be fixed inside `command_matcher`'s
  slot-parser branches, the same place `follow`/`select_target`/`engage` already are — there is no
  live "it falls through to `parse_utterance`'s type search" escape hatch for any of them today,
  whatever a docstring elsewhere might suggest.
- `follow`/`report`/`select_target`/`engage`/`point`/`greeting` already use one shared slot schema
  (`descriptor`/`clock`/`sector`/`relative`/`band`, via `vocabulary.parse_descriptor`/
  `parse_clock`/`parse_sector_word`/`parse_relative_word`/`parse_band`), tried in dedicated
  branches **before** the generic phrase table in `match_transcript` (`command_matcher.py:707`).
  `parse_descriptor`'s own table (`vocabulary.py:1106-1121`) already includes `"group"` as a legal
  value. A referent slot is an additive sixth slot on this same schema, not a new parsing idiom.
- `where_is_it` and `mark_target` are the two tokens with **no slots at all** today, both
  unconditionally bound to the attack target: `drain_where_is_it` (`crew_console.py:3298`) via
  `_active_attack_target_task()`, answering `render_no_target()` when none is set; `_handle_mark_
  target` (`crew_console.py:2797`) the same way, though `mark_target_fn(contact_id, now_sim)`
  itself already takes an arbitrary id — only the *selection* is hardcoded. `where_is_it`'s three
  recorded phrasings (`"where is it"`, `"where is target"`, `"where is it now"`, `vocabulary.
  py:691`) are indistinguishable at the audio-adapter layer today.
- `follow`'s resolved winner already gets its group-mates tagged `"watch"` via
  `_mark_watched_with_group` (`crew_console.py:2589`) whenever it belongs to a multi-member group
  — "follow a group" already reduces to "follow one contact, watch the rest." `select_target`/
  `engage`'s slotted branch does the identical reduction (`crew_console.py:2753`/`:3047`).
- `speech.group_membership_state` (`speech.py:2643`) already returns `(member_contact_ids,
  leading_contact_id, differentiated)` for a `Group`, with `leading_contact_id` picked by
  `_leading_index` via `belief.threat.envelope_for` — the widest resolvable engagement envelope.
  This **is** Decision 3's "most threatening member" rule; nothing new needs inventing. **Returns
  `None` when fewer than two members still resolve to a live `Contact`** (its own docstring,
  `_group_member_facts`'s guard) — the referent resolver must fall back to any single still-
  resolvable member in that case, not fail outright; a group that has shrunk to one live contact
  is still a valid referent.
- `_resolve_follow_target`'s own in-code comment reads: **"ties prefer the nearer contact, never
  ask"** (`crew_console.py:2525`). This project's standing answer to a resolution tie is "pick
  nearest," not "ask" — a detail worth stating plainly because it is easy to misremember as the
  opposite (a prior pass over this same plan did).
- `crew_console._report_scope` (`crew_console.py:3899`) is the one "which contacts match
  descriptor/clock/sector/relative/band" filter, shared today by `report` and `_resolve_attack_
  target`. It filters over **every current contact** and has no "only these candidate ids" mode.
- `describe_contact` (`tools.py:509`) returns facts for **any** existing `contact_id` regardless of
  certainty/"lost" — unlike `get_contacts`'s own candidate lists (e.g.
  `_resolve_follow_target`'s), which drop `certainty == "lost"`. Decision 4 ("use belief if not
  visible") is satisfied by routing every referent answer through `describe_contact`, never
  through a certainty-filtered candidate list.
- `tuning.real("<module.path>.<NAME>", default, lo=, hi=, status="judgement")`
  (`belief/decay.py:76`'s `IDENTITY_HALF_LIFE_S`) is the declaration pattern for the new window
  constant.
- `speech.render_unable(reason)` (`speech.py:490`, `_UNABLE_TEMPLATES` dict) is the existing
  "unable, `<reason>`" renderer — reused for Decision 7, not a new phrasing primitive.
- The existing `"<unit type>[, <clock> o'clock, <range> km][ <semantic fact>]."` pattern (built
  from `describe_contact`'s own `facts`, already used by `render_contact_report`/`_contact_report_
  text`) already carries clock/range/world-reference text — the shape Decision 6's "<o'clock>
  <distance in km> <world ref>" answer needs, reused rather than invented.

No DCS-internals unknowns here — pure body-layer/audio-adapter application logic over belief state
and transcripts already captured. Investigator is not needed.

### Affected Modules / Files

- **`body-layer/src/belief/referent.py` (new)** — `Mention` (`kind: Literal["contact", "group"]`,
  `id: str`, `t_sim: float`), `ReferentMemory` (`record`, `recent(now_sim)`, `last(now_sim)`,
  window-pruned by `REFERENT_WINDOW_S`), and `resolve_referent(...)`, the one resolver every
  referent-bearing command calls. `REFERENT_WINDOW_S` tunable declared here
  (`tuning.real("belief.referent.REFERENT_WINDOW_S", 60.0, lo=15.0, hi=180.0,
  status="judgement")` — the explore notes' own "time ok" with no measured figure). Kept separate
  from `crew_console.py` per root `CLAUDE.md`'s "actions and params" shaping: resolution is a pure
  query over belief state, not an action.
- **`body-layer/src/belief/crew_console.py`** — `CrewConsole._print` gains an optional `mentions:
  list[Mention] | None = None` kwarg, recording into a new `self._referent_memory: ReferentMemory`
  field; threaded through `_speak_or_defer`/`_PendingPositionalReply` so a deferred readback's
  mention is recorded at its actual speak time (see "Facts" above). `_report_scope` gains an
  optional `restrict_to_ids: Collection[str] | None = None` so `resolve_referent` reuses its
  descriptor/clock/sector/relative/band filter instead of a second copy of that logic.
  `drain_where_is_it`, `_handle_mark_target`, `_handle_follow`, `_handle_select_target`,
  `_handle_engage` each gain a referent branch (Stages 2-3 below). Each `_print` call site with a
  known subject in scope passes it — audited list under Design.
- **`audio-adapter/src/vocabulary.py`** — `REFERENT_WORDS = ("it", "that")` and
  `parse_referent(text) -> bool`, beside `parse_descriptor`.
- **`audio-adapter/src/command_matcher.py`** — `_parse_follow_slots`/`_parse_select_slots`/
  `_parse_engage_slots` each gain a `referent` boolean slot (additive, same shape as the existing
  five). New `_parse_where_is_it_slots`, `_parse_mark_slots`, and `_parse_watch_slots` (each:
  explicit-literal-"target" check where applicable, else descriptor/clock reuse, else bare
  `referent`), each with its own matcher branch ordered alongside the existing slotted branches,
  before the phrase table. `"mark target"`/`"watch nearest"`/`"where is it now"` with no pronoun
  and no slot match keep falling through to the phrase table exactly as today.
- Tests in both subprojects per stage (see Implementation Plan).

### Design

**One resolver, reused everywhere.**

```python
def resolve_referent(
    store: ContactStore, memory: ReferentMemory, now_sim: float, *,
    descriptor: str | None, clock: int | None, sector: Sector | None,
    relative: RelativeSector | None, band: str | None,
    active_attack_target_id: str | None,
) -> tuple[str | None, list[str]]   # mirrors _resolve_follow_target's/_resolve_attack_target's
                                     # own (contact_id, failure_lines) shape, so callers branch
                                     # on it identically
```

1. Prune `memory.recent(now_sim)` to the window. Empty → `render_unable("NO_REFERENT").text`
   (Decision 7's "unable, `<because>`").
2. No qualifier at all (every one of `descriptor`/`clock`/`sector`/`relative`/`band` is `None`) →
   `memory.last(now_sim)` (Decision 2, "the last line wins").
3. A qualifier present → filter `memory.recent(now_sim)`'s candidate ids through
   `_report_scope(..., restrict_to_ids=<those ids>)` (Decision 2's "search the recent mentions for
   a match"), reusing the exact descriptor-verdict/clock-delta machinery `_resolve_follow_target`/
   `_resolve_attack_target` already use, over the *mentioned* set rather than the whole store.
4. **Target-priority clause (Decision 2's own worked example)**: before returning a qualified
   match, if `active_attack_target_id` is itself among the matches, it wins over any other match
   — "if attack target is AAA, which would take priority."
5. **More than one match, qualified or bare** → **pick nearest, never ask** — the identical rule
   `_resolve_follow_target` already states in its own comment for its own tie-break (see "Facts").
   This project already has one answer to "which of several equally-plausible contacts," and this
   resolver reuses it rather than inventing a second ("ask") rule for referents specifically.
6. **Group → single-contact reduction (Decision 3)**: whatever step 2-5 resolved, if it names a
   `Mention(kind="group")`, resolve to `speech.group_membership_state(...)`'s own
   `leading_contact_id` — the existing "most threatening member" selection, reused verbatim — with
   a fallback to any one still-resolvable member if `group_membership_state` itself returns `None`
   (the "fewer than two members left" case above). `"that group"` (the qualifier text contains the
   literal word `"group"`) is the one case a caller treats as "the whole group," reusing
   `_mark_watched_with_group`'s existing all-member tagging exactly as a non-referent `follow`
   already does — no second group-id return path is needed, since every consumer here
   (`where_is_it`, `mark_target`, `select_target`, `engage`, `follow`) only ever wanted a contact
   id, and `follow`'s own group-tagging already happens downstream of resolving to one contact.

**Mention recording is centralised in `_print`, not duplicated per call site.** `_print(lines,
now_sim, mentions=[...])` records once per logical reply/line-batch — satisfies Decision 2 ("every
line... the last line wins," attack-run steering included) and, because recording happens inside
the one funnel rather than being each caller's own discipline, avoids the `BL-B71` failure class
(a construction/call site silently not carrying a co-moving piece of state forward). Callers that
pass nothing record nothing — a safe default — but **the audit below is still required**, because
a caller that has a subject and forgets to pass it is exactly the silent miss this plan must not
reproduce:

| call site (subject known at that point) | subject to pass |
|---|---|
| callout/group-disclosure dispatch (`drain_events`'s `CalloutScheduler.tick` path) | the event's `contact_id`/`Group.id` |
| `_act`'s `describe_contact`/`set_attention` readback | `parse.referenced_contact_id` |
| `_handle_follow`'s deferred readback | the resolved `contact_id` |
| `_handle_select_target`'s / `_handle_engage`'s deferred readback | the resolved `contact_id` |
| `drain_attack_run`'s steering line (Decision 2: "attack-run steering lines included") | `state.last_contact_id` |
| `drain_where_is_it`'s answer | the contact it just answered about (target or referent) |
| `_handle_mark_target`'s echo | the marked `contact_id` |
| `_handle_report`/the slotted report path | every contact in `scope.facts`, as one batch |

Lines with **no** subject (silence ack, config-error line, say-again, radio check, greeting,
`render_lost_contact`, `render_no_target`) pass nothing — a "lost"/"no target" answer must not
plant a referent for a contact that no longer resolves.

**"Where is it"/"mark it" vs. the literal word "target" (Decisions 1/6).** `_parse_where_is_it_
slots`/`_parse_mark_slots` each check for the literal word `"target"` first (`{"anchor":
"target"}`) — "where is target"/"mark target" with no pronoun keep today's hard binding to
`_active_attack_target_task()` unchanged. Only the bare/qualified-pronoun form reaches
`resolve_referent`. For `where_is_it`, a referent that resolves to the current attack target still
speaks the existing `query_attack_run` phrase (Decision 1 holds, now reached via the referent path
rather than assumed); a referent resolving to a different contact speaks the plain positional
answer (`describe_contact`'s facts through the existing clock/range/world-ref pattern, Decision 6);
nothing resolved → `render_unable("NO_REFERENT")`.

**`follow`/`select_target`/`engage`/the `watch` family.** Each of `_parse_follow_slots`/`_parse_
select_slots`/`_parse_engage_slots` gains the `referent` boolean slot; a bare referent alone now
makes the slots dict non-empty (today it is `None` and falls through to "say again" or, for bare
`engage`, "resume the already-selected run"). Body-side: each handler's existing "no slots at all"
branch becomes "no slots **and** no referent"; a heard referent calls `resolve_referent` instead
of `_resolve_follow_target`/`_resolve_attack_target`. **Decided here, local and reversible**:
"engage it"/"engage that" selects-then-engages the resolved contact rather than being read as a
bare "resume the run" — a heard referent is itself a positive signal the player means a specific
contact, not nothing. The `watch` family (`"watch that"`/`"watch it"`) gets its **own** new slot
parser (`_parse_watch_slots`, same shape, dispatching the existing `follow` token/handler) rather
than a widened verb set shared with `follow`'s own parser — kept separate because `"watch"` is not
`follow`'s own verb and conflating the two parsers' docstrings would misstate which verb anchors
which branch; functionally it ends up calling the same `_handle_follow` resolution path either
way.

### Co-moving Fields

`where_is_it`'s one-shot signal is a field *pair*, not a single bool, once it carries a referent —
`where_is_it_requested` (existing) plus a new `where_is_it_slots`, set together by `_handle_where_
is_it` and consumed together by `drain_where_is_it`. This is exactly the shape `BL-B71`'s own miss
was in (a fresh-construction/consumption site silently not carrying a second co-moving field
forward), so it is named explicitly rather than left to be found during review:

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| `where_is_it_requested` | external (voice command `where_is_it`) | `_handle_where_is_it` dispatch | `True` |
| `where_is_it_slots` | external (voice command `where_is_it`) | `_handle_where_is_it` dispatch | holds *this* dispatch's slots (`anchor`/`descriptor`/`clock`/...), never a stale previous command's |
| `where_is_it_requested` | internal (`drain_where_is_it`) | consumed | reset to `False` |
| `where_is_it_slots` | internal (`drain_where_is_it`) | consumed, same call | reset to `None` — never left holding an already-answered request |

### Implementation Plan

1. **Core mechanism.** `belief/referent.py` (`Mention`, `ReferentMemory`, `REFERENT_WINDOW_S`,
   `resolve_referent`); `_print`/`_speak_or_defer`/`_PendingPositionalReply` gain `mentions`;
   audit and wire every call site in the table above; `_report_scope` gains `restrict_to_ids`.
   Unit tests: window pruning, bare-last, qualified-filter, target-priority tie-break,
   group→lead-member reduction (including the `group_membership_state is None` fallback),
   nearest-wins tie-break, expired/empty → `render_unable("NO_REFERENT")`.
2. **`where_is_it` and `mark_target`.** `vocabulary.REFERENT_WORDS`/`parse_referent`;
   `command_matcher._parse_where_is_it_slots`/`_parse_mark_slots` and their matcher branches.
   Body: the explicit-"target"-anchor vs. referent split described above; `drain_where_is_it`'s
   two-field one-shot signal per the Co-moving Fields table; `_handle_mark_target`'s referent path
   feeds the already-generic `mark_target_fn(contact_id, now_sim)` unchanged. Tests: "where is
   it"/"where is that" during an active run resolve to the engaged target unless something else
   was mentioned more recently; "where is that AAA" resolves to the AAA even with a target
   engaged; "where is target"/"mark target" untouched; expired → "unable."
3. **`follow`/`select_target`/`engage`/the `watch` family.** The `referent` slot on `_parse_
   follow_slots`/`_parse_select_slots`/`_parse_engage_slots`, plus the new `_parse_watch_slots`.
   Body: each handler's dispatch gains the referent branch described above. Tests reproduce the
   user's own worked examples end to end: "unit in 11 o'clock group is armor" → "target that/it";
   "follow that group"; "describe" (two groups) → "follow that moving group" → "engage that 11
   o'clock armor, missiles" (qualified, must pick the 11 o'clock group's lead over the 2 o'clock
   one from the same mention batch).
4. **Full regression + staleness pass.** Re-run the existing `where_is_it`/`mark_target`/
   `select_target`/`follow`/`watch_nearest*` suites to confirm every pre-existing non-pronoun
   phrasing is byte-for-byte unchanged (the explicit non-goal throughout); `test_command_matcher.
   py`'s existing branch-order test extended for the new/widened slot parsers.

### Risks & Unknowns

- **Mention-recording completeness is an audit, not a mechanism.** The funnel makes a forgotten
  subject *safe* (nothing recorded, never a crash) but still silently missing — the table above is
  the audit's starting point; Reviewer should re-grep `self._print(` after Stage 1 lands, the same
  discipline `BL-B71`'s own retro asked for.
- **"Where is it" changes meaning mid-run for a player who assumes it always means the target.**
  In practice, attack-run steering chatter re-mentions the target every few seconds (Decision 2
  explicitly includes steering lines), so bare "where is it" still resolves to the target almost
  all the time once engaged — the divergent case is exactly the one the user asked to fix ("where
  is that AAA" when AAA is not the target).
- **No live-sortie data on `REFERENT_WINDOW_S`.** 60 s is the user's own figure, `judgement`
  status — expect it to move once flown, the same posture `CONFIRM_WINDOW_S`'s own history shows
  for an unmeasured timing constant.
- **The ambiguous-bare-referent case (ties within a batch) is resolved by "nearest wins," not by
  asking** — a deliberate reuse of this project's existing tie-break convention rather than a new
  confirm-band shape. If live use finds a nearest-wins pick wrong often enough to be annoying, a
  genuine ask-flow would need `PendingConfirmation.contact_pick`-style plumbing, which is scope
  beyond what the six decisions asked for.

### Second-order effect

Establishes `belief/referent.py`'s `Mention`/`ReferentMemory` as the one place "what was Petrovich
just talking about" lives — a later conversational-memory feature (BL-10/SRS free-speech
follow-ups, `plans/brain-layer/explore-notes.md` §4) has a state param to read rather than
reinventing a second notion of "recency," so it narrows rather than complicates that later work.

### Decisions Requiring User Input

- None outstanding. (The one open question the explore notes left — whether `mark_target`/the
  `watch` family are worth building alongside `where_is_it`/`follow`/`select_target`/`engage` — is
  resolved in this plan by building all six together, Stage 2/3: the marginal cost is small once
  Stage 1's mechanism exists, and all six are explicitly named in the ROADMAP entry's own "Not
  decided here, for the plan" list as in scope.)
