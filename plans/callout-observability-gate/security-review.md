# Security Deep Analysis: callout-observability-gate

Branch `fix/callout-observability-gate`, tip `24fa35d`, verified by `git rev-parse HEAD` after a
fast-forward from this worktree's base (`19143fa`, a strict ancestor). Tree clean.
`pytest tests -q` → **1475 passed, 4 xfailed**, run with the main checkout's interpreter and
`rootdir` inside the worktree's own `body-layer/` — import resolution proven to the worktree's
`src` (`belief.callouts` loaded from
`.claude/worktrees/agent-a1492ec1568cfe4b8/body-layer/src/belief/callouts.py`).

## Dependency Status

No dependency change. `git diff main...HEAD` touches no `pyproject.toml`, no requirements file,
and adds no import outside `belief`/`perception`.

## Conventional attack surface: clear, and said plainly

The added source lines contain no `subprocess`, `os.system`, `eval`, `exec`, `pickle`, `open`,
`socket`, `urllib`/`requests`, no path construction, no credential-shaped identifier, and no
`shell=True`. There is no new input surface, no new parsing path, no new trust boundary, and no
new file or network I/O. DoD's read on this is correct and I am not manufacturing findings in
those categories. The whole of the value below is provenance and disclosure.

## The central question: does the exemption disclose more than its justification covers?

**On the omniscience axis: no. The justification holds against the code, not merely against the
summary of it.** Traced end to end:

- **Unit type.** `_contact_report_text` → `facts["classification"]` → `_classification_facts`
  (`belief/tools.py:206`), which reads `contact.classification` — the folded belief claim — and
  explicitly not `last_class_raw`. Confidence is read through `classification_confidence_at`, so
  it decays.
- **Clock hour and range.** `facts["relative_now"] = relative_geometry(enrichment.ownship,
  world_position)` (`belief/tools.py:354`), where `world_position` is the enrichment cache's
  resolution of `Contact.last_position`. `last_position` is a read-only property over
  `Contact.position` (`belief/contacts.py:468`), and `record`/`from_percept` via `fold_position`
  are its only writers (`belief/contacts.py:483`, `575`) — both reached only through
  `ContactStore.ingest` of a `PerceptionSource` observation. **Nothing refreshes a contact's
  position while it is behind the cockpit mask**, because the only two channels that can produce
  an observation are mask-constrained (`naked_eye_source` applies `check_visibility`) or
  heading-hemisphere-constrained (`hybrid_source` via
  `association.FORWARD_HEMISPHERE_HALF_WIDTH_DEG`). So `"six o'clock, 1.0 km"` on an exempt line
  is a *dead-reckoned statement about a remembered position against current own-aircraft
  attitude* — the thing a real co-pilot says — not a fresh fix.
- **The trigger itself.** `envelope_for` (`belief/threat.py:209`) returns `None` for
  `UNKNOWN`/`PRESENCE` and keys strictly on `ClassificationBelief`; there is no fallback
  envelope. The engagement term (`belief/contacts.py:1369`) compares `contact.last_position`
  against `ownship` — the player's own telemetry. No ground-truth field participates.

**Can a contact reach `CONTACT_ENGAGEMENT_CHANGED` without ever having been perceived? No.** The
event requires membership in `ContactStore._contacts` (only `ingest` founds a contact, only from
one of those two perception channels), `is_watched` (a pilot-issued attention state), and a
resolvable believed envelope. `hybrid_source` is specifically *not* a truth channel: it reads the
HelperAI indication leaves — the in-game operator's own target list — and `object_id` never
leaves `perception/` (`perception/source.py:225`). The "already perceived" premise is structural,
not incidental.

**On the motivational axis: yes, in one specific respect** — see Finding 1. That is a disclosure
decision rather than a leak, and it is the one thing on this branch I would want the user to
settle before they fly it.

## Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/belief/callouts.py:983-990` | exemption admits both engagement directions | Finding 1 — the `engaged=False` transition fails the set's own admission property (1) | Narrow, or have the user ratify |
| `body-layer/tests/test_callouts.py:1929` | provenance claim | Finding 2 — the one surviving `"user decision 2026-10-06"` on a decision the user never made | Fix now |
| `body-layer/tests/test_callouts.py:2175-2229` | test asserts the unenriched line only | Finding 3 — nothing pins the exempt line's enriched disclosure or the exempt set's membership | Fix before public release |
| `body-layer/src/logger.py:1473` | `drain_events(runner.last_t_sim)` on a frozen clock | Finding 4 — pre-existing, fails safe | Note only |
| `body-layer/src/belief/contacts.py:685-700`, `1144-1151` | bookkeeping-read gate | **Sound.** No stale-stamp path — see below | None |
| `body-layer/src/belief/callouts.py:1004-1026` | group-member `any(...)` gate | **Sound.** Skips without mutating state | None |
| `belief/crew_console.py` `_handle_report` | pull path ungated | **Confirmed and defensible** — see below | None |

### Finding 1 — the exemption covers the "Safe from" transition, which its own bar does not justify (MEDIUM, disclosure)

`body-layer/src/belief/callouts.py:983-990` exempts the *kind*, so both transitions pass:
`event.engaged is True` renders `"Danger, …"` and `event.engaged is False` renders
`"Safe from …"` (`belief/speech.py:1874-1883`).

`_OBSERVABILITY_EXEMPT_KINDS`' admission bar requires **both** properties, and property (1) is
*"the cost of silence is a missed threat cue the pilot needs in order to evade"*. A
`"Safe from ZU-23-3, six o'clock, 1.0 km."` is not that. Nothing is evaded by hearing it; its
silence costs the pilot the chance to *stop* evading, which is a comfort, not a threat cue.
Property (2) holds for it (silence would be permanent, not late) — and the docstring says in
terms that *"Either property alone admits something that should stay gated"*. By its own
standard, the "safe" direction is admitted on (2) alone.

**Failure scenario, fully reachable.** A watched ZU-23-3 is identified while visible and enters
its envelope — `"Danger, ZU-23-3, six o'clock, 1.0 km."`, correctly spoken. The pilot turns away
to egress; the contact is now past `rear_cutoff_deg` and `last_observable_sim` lapses. The
aircraft opens beyond `range_max_m * ENGAGEMENT_LEAVING_HYSTERESIS`, and Petrovich volunteers
`"Safe from ZU-23-3, four o'clock, 2.0 km."` — an unprompted classification-and-position line
about a contact his own mask says he cannot see. That is the *shape* of the 17-line defect this
branch exists to fix, surviving in one narrow case, on a justification that does not reach it.

(One variant is **not** reachable, and this is worth recording because it looks like it should
be: a masked contact cannot produce an LOS-triggered "safe" call. The masked branch at
`belief/contacts.py:1424` needs `live_los_clear is False` *and* a look within `OBSERVED_WINDOW_S`
— and a cockpit-masked contact cannot get a fresh look, so it falls to the fail-open branch
instead. Only the range/altitude departure above reaches it.)

**Fix.** One condition, in the gate rather than the set, because the set is keyed on kind:

```python
exempt = event.kind in _OBSERVABILITY_EXEMPT_KINDS and event.engaged is True
```

with the reason stated beside it and `_OBSERVABILITY_EXEMPT_KINDS`' bar amended to say the
exemption is per-transition, not per-kind. The "safe" call then defers like everything else and
is retired by `CALLOUT_MAX_AGE_S` if the bearing never returns — which is the right answer for
it, since it is exactly the "merely spoken late has no claim on an exemption" case the docstring
already names.

**The alternative is equally acceptable and is the user's to pick:** ratify the kind-level
exemption as it stands, on the ground that a pilot who heard "Danger" is owed the "Safe from"
that closes it, whether or not he can still see the thing. I do not think that is wrong. I think
it is a different argument from the one written down, and the written one should match whichever
is chosen.

### Finding 2 — a surviving claim that the user decided this (LOW severity, HIGH importance)

`body-layer/tests/test_callouts.py:1929` reads
`(callouts._OBSERVABILITY_EXEMPT_KINDS, user decision 2026-10-06)`.

`plans/callout-observability-gate/implementation.md:134` records that every
*"user decision, 2026-10-06"* was swept to *"decided in the review loop, 2026-10-06, on the
Reviewer's recommendation"*. This one was missed — it is the only occurrence left in the tree.
The test's own docstring twelve lines below it says the opposite (*"not by the user"*), so the
file now contradicts itself on the single fact the user most needs to be true: that this is
unratified. A later reader resolving that contradiction toward the comment would treat the
exemption as settled.

**Fix.** Replace with the swept wording. One line, no behaviour.

### Finding 3 — nothing pins what the exempt line actually discloses (LOW, fix before public release)

`test_engagement_change_speaks_about_a_cockpit_masked_bearing`
(`body-layer/tests/test_callouts.py:2175`) asserts `["Danger, ZU-23-3 Sergey."]` — the
*unenriched* form, with no clock and no range, because the test builds no `EnrichmentContext`.
Round 2's "Optional 2" test for the enriched form was left unwritten, so the breadth of the
exemption — believed type **plus** clock **plus** range **plus** any semantic or terrain
qualifier `_contact_report_text` appends — exists only as prose in a docstring.

Two consequences, both silent: a future change to `_contact_report_text` can widen what the one
ungated spontaneous kind says about an unseeable contact with no test failing; and nothing
asserts `_OBSERVABILITY_EXEMPT_KINDS == frozenset({CONTACT_ENGAGEMENT_CHANGED})`, so a kind can
join the set without any test objecting. The implementer's own memory note flags the second as
the residual risk, and it is correct: adding a kind to `_TEMPLATED_KINDS` *gates* it (safe
direction), while adding one here *exempts* it quietly.

**Fix.** Two assertions, no production change: one test rendering the exempt line with an
`EnrichmentContext` and asserting the full string, and one asserting the exempt set's exact
membership so that growing it is a deliberate test edit. Cheap enough to do now; required before
the repository is public, when the reader deciding a new kind's membership is a stranger working
from the docstring alone.

### Finding 4 — frozen-clock drain (LOW, pre-existing, fails safe — note only)

`body-layer/src/logger.py:1473` drains on `runner.last_t_sim`, the last *successful* poll's
stamp, under a log-and-continue guard around the whole poll body. If telemetry is unreachable,
`run_once` raises, `last_t_sim` freezes, and `drain_events` keeps running against it. The
observability gate then compares a frozen `now_sim` against a stamp taken at that same instant,
so `now_sim - last_observable_sim` stops growing and the grace window never lapses.

This is benign and not introduced here: with the clock frozen, no new event is minted, and
`CALLOUT_MAX_AGE_S` is measured against the same frozen stamp, so the set of admissible
candidates cannot grow either. The gate's verdict is simply pinned at whatever was true at the
last good poll, which is the safe direction. Recording it so the next reader of
`callout_observable` does not have to re-derive it.

## What I checked and found sound

- **No stale-stamp path.** `callout_observable` (`belief/contacts.py:685`) reads
  `Contact.last_observable_sim` rather than recomputing the mask, so the risk was a caller
  reading a stamp the bookkeeping had stopped maintaining. It cannot: `_callout_may_speak` is
  called at `belief/contacts.py:1226` **unconditionally inside `tick`'s per-contact loop**
  whenever `ownship is not None`, and there is no `continue`, `break` or early return between
  the loop header (`1151`) and that call. Every contact in the store is stamped every ticked
  frame. `_observability_tracked` is set *before* the loop (`1144`), so a contact ingested later
  still reads as tracked, and `last_observable_sim is None` therefore means "confirmed never
  observable" rather than "never asked" — the gate returns `False`, the strict direction.
  Production never mixes modes: `run_once` fetches telemetry first and passes `ownship` on every
  `store.tick` (`logger.py:549`), and `drain_events` is called with the same `last_t_sim` on the
  same thread, immediately after, so the answer `CalloutScheduler.tick` reads was computed for
  that exact `now_sim`. The only mixed-mode callers are tests that omit `ownship`, for which the
  flag makes the gate a true no-op.
- **The gate fails in the safe direction.** Both call sites `continue` without adding to
  `self._consumed`, so a blocked candidate is *deferred*, and it is placed deliberately **after**
  the `CALLOUT_MAX_AGE_S` check — which is what bounds the deferral and what stops a permanently
  astern contact's event from living forever unconsumed. Nothing is silently dropped. The group
  path mutates no state before its `continue` (no `mark_group_spoken`, no fact computation), so a
  group blocked this tick is re-evaluated whole next tick.
- **`contact is None` is handled, not swallowed.** The gate admits an event whose contact has
  vanished (`callouts.py:986`), but `describe_contact` then returns `None` and the event is
  `_consumed` without speaking (`callouts.py:995-999`). A pruned contact cannot be spoken about.
- **The pull path is ungated, and that is a defensible disclosure decision, not just a code
  fact.** `callout_observable` has exactly two call sites tree-wide, both inside
  `CalloutScheduler.tick`, whose only caller is `drain_events`; `_handle_report` renders straight
  through `belief.speech` and never reaches `tick`. Confirmed. As a disclosure decision it is the
  right one and for a reason the push path makes clear: the no-omniscience invariant constrains
  what Petrovich may *volunteer*, because an unprompted position-and-type line is implicitly a
  claim to have just seen it. An answer to `report` carries no such implicature — the pilot
  asked, and belief legitimately outlives the look. Where the invariant bites on the pull path it
  does so as an absence claim (`render_no_view`) or as freshness phrasing, which is the honest
  form. Finding 1 exists precisely because the exempt kind is on the *push* side, where the
  implicature applies.
- **Group gate breadth.** `any(member observable)` rather than `all` — correct, and not merely
  convenient: the disclosure line renders position from the nearest member, so `all` would
  silence a visibly-present group for one straggler behind the doorframe. The weaker quantifier
  does not widen disclosure, because what is spoken is the nearest member's geometry and the
  group's hedged cardinality, never a per-member enumeration.

## Verdict

**APPROVED WITH REQUIRED FIXES**

Not NEEDS FIXES, and the distinction is deliberate. The question put to this pass was whether
the exemption's disclosure is wider than its justification. On the axis that matters for the
no-omniscience invariant — whether anything spoken is fresher, more precise, or more
ground-truth-derived than what Petrovich could have perceived — **it is not, and the
justification survives contact with the code**. Every fact on an exempt line is belief-derived,
position cannot refresh behind the mask, and no contact can reach the exempt kind without having
been perceived and watched. That is the reviewer's reading from Round 2 confirmed by tracing, and
it is now an assertion rather than an impression.

The exemption is wider than its *stated rationale* in one place — the `engaged=False` transition,
which the admission bar's property (1) does not reach — and that is Finding 1. It is a disclosure
decision, settled either by one condition in the gate or by the user ratifying the kind-level
form. It should not go to the user as flight-ready while the code and the comment disagree about
which one was chosen.

### Required Fixes (fix now)

1. **Narrow the exemption to `event.engaged is True`, or get the user's explicit ratification of
   the kind-level exemption** — `body-layer/src/belief/callouts.py:983-990`, with
   `_OBSERVABILITY_EXEMPT_KINDS`' bar amended to match whichever is chosen.
2. **Replace the surviving `"user decision 2026-10-06"`** with the swept wording —
   `body-layer/tests/test_callouts.py:1929`. It contradicts the docstring twelve lines below it
   and misattributes an unratified decision to the user.

### Fix before public release

3. **Pin the exempt line's enriched disclosure and the exempt set's membership** in tests —
   `body-layer/tests/test_callouts.py` (Round 2's unwritten "Optional 2", plus a membership
   assertion). Cheap now; load-bearing once the reader deciding a new kind's membership is a
   stranger.

### Note only

4. Frozen-clock `drain_events` on `last_t_sim` — pre-existing, fails safe, recorded above.
