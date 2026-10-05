---
name: crew-query-path-design
description: The report/describe slotted-command plan (2026-10-06) — the measured BL-B28 wrong-direction match, why landmark where is blocked on STT not WM-B1, and the pull-vs-push observability split
metadata:
  type: project
---

`plans/crew-query-path/plan.md` designs `report|describe [what] [where] [how far]` (explore-notes
decisions D12/D13). Four things in it were only knowable by measuring or reading, and each reverses
something a plan or backlog item asserted.

**`BL-B28` is a silent wrong-direction match, not a recognition asymmetry.** Measured against
`command_matcher.match_transcript`: `"report left"` → `token='report_bearing_e'` (ratio 0.75,
`ambiguous=True`) — *report east*. `"report right"` → `None`. `"scan left"`/`"scan right"` → 1.0
each. Root cause: there is **no own-ship-relative frame on the report side at all** — `PHRASES` has
`scan_left`/`scan_right` but the report family is cardinals + clock hours only. The backlog read it
as "a missing right-hand form"; the left side was the dangerous one.

**Why:** one of two words differing is enough to clear `MATCH_FLOOR` (0.6) at 0.75.
**How to apply:** never diagnose a left/right or synonym asymmetry from the *outcome* words
(`confirm` vs `say_again`) — run the matcher. It took one 15-line probe script. And `confirm` is not
evidence of success: it can be a confirm prompt for the wrong action.

**A phrase-table synonym is not a verb substitution.** `0caa39e` added `"describe"` to
`PHRASES["report_all"]`, which makes it an *anchorable* verb (`VERB_ANCHOR_WORDS` derives from
first words) but **not** substitutable: `"describe two o'clock near"` → `None` while
`"report two o'clock near"` → `report_clock_2`. Every slotted form breaks under the synonym.
**How to apply:** when adding a verb synonym, check the slot/family forms, not just the bare phrase.

**The landmark `where` slot is blocked on open-vocabulary STT, not on `WM-B1`.** `WM-B1` is `[x]`
done (`fix/latin-place-names`, 2026-10-02, needs only a rebuild) and
`query.search.find_place_by_name` exists. The actual blocker is `vocabulary.py`'s own standing rule:
an open set cannot be enumerated into a closed grammar. The typed console path takes it today; voice
waits for free speech.
**How to apply:** the brief I was handed said WM-B1 was open. Check the roadmap row, not the brief.

**Pull and push need opposite observability answers, and nothing said so before.**
`contacts._callout_may_speak` (the D11 gate) must **not** filter a `report` answer — belief survives
the aircraft turning away, and the pilot asked. The invariant bites only on *absence* claims
(`render_no_view` already exists for this) and *freshness* (`_PHRASING_CERTAINTY` +
`decay.OBSERVED_WINDOW_S`). The plan states this explicitly because D11's own implementer will
otherwise apply the gate uniformly and break the query path.

**Constants that already existed and must not be re-invented** (rule 3a, and it paid off twice
here): `decay.OBSERVED_WINDOW_S` (= `SCAN_CYCLE_PERIOD_S`, assertion-pinned) is the freshness bound;
`callouts.CALLOUT_GROUP_CLOCK_SPAN_HOURS = 1` is already documented as "two clock positions this
close read as the same direction to a listener", which is exactly the clock-filter widening; and
`callouts.speech_duration_s` (0.6 + words/2.5) converts a seconds budget to words — so the answer
budget was derived from the user's chosen mock's own 24-word length rather than guessed.

See also [[project_los_fixed_literal_command_channel]] for the other `follow`-slot precedent, and
[[project_watch_reporting_design]] for `_resolve_follow_target`'s three-valued descriptor verdict,
which the report filter reuses.
