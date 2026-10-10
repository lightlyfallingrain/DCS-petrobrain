# Security Deep Analysis: BL-13 — the crew query path (Stages 1–3)

Branch `feature/bl13-crew-query-path`, tip `a44401e96e7745df49b0ef26651d5645a1a16b56`.
Worktree HEAD was `e2e2164` (stale, as assumed); fast-forwarded to `a44401e`. Whole feature
reviewed, `e2e2164..a44401e`, both review rounds.

Checks run with the **main checkout's** venv binaries (`/Users/sg/Code/DCS-petrobrain/<sub>/.venv/bin/…`)
because `.venv` is gitignored and so absent from the worktree; cwd was each subproject inside the
worktree, so `mypy`'s CWD-only config discovery and pytest's `pythonpath` resolved against the
reviewed tree. audio-adapter: ruff clean, mypy clean, **255 passed / 1 skipped**. body-layer: ruff
clean, mypy clean, **1604 passed / 4 xfailed**. Both as expected.

### Dependency Status

No dependency change. `git diff --stat e2e2164..a44401e -- '*pyproject.toml' '*requirements*'` is
empty. Decision E honoured: no in-process cross-subproject import added — `crew_console.py` and
`speech.py` gain no `query`/`world_model` import, audio-adapter imports nothing from body-layer, and
the token crosses as `{token: "report", slots: {...}}` over the existing HTTP/JSON channel.

### Required Fixes

**1. The summary's freshness qualifier is all-or-nothing and droppable, so the common
mixed-staleness scene speaks up-to-120-second-old belief as a flat present-tense claim.**
`body-layer/src/belief/speech.py:899` (`all_stale = all(_is_stale(...))`), consumed at
`speech.py:930`, with the only partial hedge at `speech.py:754-787`
(`_summary_deferral_clause`) and its drop at `speech.py:938-944`.

Decision D names freshness as one of the two places the no-omniscience invariant bites on a *pull*,
and `render_report_summary`'s own docstring says *"Freshness is spoken, not implied."* It is spoken
in exactly one case — when **every** in-scope contact is older than `OBSERVED_WINDOW_S`. In-scope
contacts are everything not `lost`, i.e. up to `LOST_THRESHOLD_S` = **120 s** old, and
`OBSERVED_WINDOW_S` is **16 s** — equal to one whole scan cycle. So one contact refreshed in the
current cycle removes the qualifier from the whole answer, including contacts seen two minutes ago.
With more than one contact in scope that is the steady state, not an edge case: the honest
"Last I saw" fires mainly on the narrow single-contact query, and is absent from the broad query the
feature exists to serve.

Measured against the shipped renderer (not quoted from a plan):

```
mixed, 1 fresh + 1 stale (119 s):
  About eight units, mostly infantry, 1 o'clock through 2 o'clock, inside 2 kilometres.
  Still checking the infantry group.

mixed, 1 fresh + 3 stale (118–119 s), two SAM tiers:
  About twelve units, mostly infantry, 1 o'clock through 4 o'clock, inside 2 kilometres,
  and one short range SAM, one long range SAM.          [22 words — deferral dropped]
```

In the second case three of four contacts were last seen about two minutes ago, two of them air
defence, and the answer carries **no freshness signal anywhere**: the deferral clause would have
pushed it to 27 words, so the budget dropped it. Even when it survives it is not a freshness
qualifier — it names one stale contact (and `stale[0]` is `get_contacts` order, so the *least*
stale one), and *"still checking"* asserts an inspection in progress rather than a memory.

The exposure is the project's core product property, not a conventional security one, and the
LAN-only framing does not discount it (the task's own scoping says so): the pilot is told a SAM is
at 3 o'clock inside 2 km, in the same register used for something seen a second ago, on the strength
of a two-minute-old belief. Deciding to fly on that is exactly the decision the invariant exists to
keep honest.

**This is a gap in Decision D's argument, not an implementation slip** — the plan specified the
all-stale prefix and specified the deferral as the first thing the budget drops, and the
implementation did both faithfully. Neither is a partial-freshness mechanism, and nothing in the
plan noticed that the partial case is the common one. So the fix needs the user's wording call
before it is written (he owns the drop order and the register), and the smallest shape that closes
it is: a qualifier that fires when **any** in-scope contact is stale, phrased distinctly from the
all-stale prefix, and **not** in the droppable tail. Keeping it inside the 25-word budget is the
tuning question; dropping the only honesty marker to stay inside it is what must stop.

Not asked for, and deliberately not: per-contact certainty vocabulary, which would turn the summary
back into the enumeration the user rejected.

### Observations (no action required)

| Location | Finding | Assessment |
|---|---|---|
| `audio-adapter/src/command_matcher.py:566-581` (report branch; `_parse_report_slots` at `:459`) | `"repeat left"` resolves to `token="report"`, `slots={'relative': 'left'}`. `ratio("repeat","report")` = 0.67 clears `VERB_FLOOR` (0.5), a slot parses, and the branch returns before the phrase table where `say_again` lives. | Measured. Not a required fix: it needs a stray slot word alongside a misheard "repeat", the outcome is a report instead of a repeat (recoverable in one utterance), and it is the same early-return shape the pre-existing `follow` branch has. Worth a line in the next bench pass. |
| `audio-adapter`, all five slot parsers | Each parser re-runs `normalize_for_match`, so an anchored report transcript normalises 5× where it previously normalised once. `normalize_for_match` is itself super-linear in length (2 ms at 1 kB, 0.45 s at 20 kB, 7.5 s at 200 kB). | Not reachable with a long input: `match_transcript` is called only on `stt_engine.transcribe` output (`server.py:256`), never on client-supplied text, so length is bounded by clip duration. The absent request-size cap on `/transcribe` is the pre-existing item already recorded from the 2026-09-26 audio-adapter audit, unchanged by this feature. |
| `body-layer/src/belief/crew_console.py:675-691` | The confirm readback appends any `str` slot value verbatim, so an arbitrary string from a non-adapter LAN client reaches the spoken readback. Filtering validates (`_handle_slotted_report`, `crew_console.py:1742-1801`); the readback does not. | Same property the pre-existing `follow` readback has (`crew_console.py:663-674`), LAN-only, speech-only, no state change. Note the new branch is the *stricter* of the two: it membership-checks `clock` against `_CLOCK_REPORT_LABELS`, where `follow`'s unguarded `_CLOCK_REPORT_LABELS[follow_clock]` would `KeyError` on an out-of-range int from the seam. |
| `body-layer/src/belief/speech.py:695-752` | `_summary_air_defence_clause` counts **contacts**, not believed units, so a contact holding four SAMs is announced as "one short range SAM". | Under-claims, which is the safe direction, and the tier (the decision-relevant part) is still named. |
| `body-layer/src/belief/crew_console.py:2052-2064`, `1961` | Live-path `assert isinstance(...)` on `relative_now["clock_position"]`/`["bearing_deg"]`/`["range_m"]`, and a bare `relative_now["range_m"]` index in `_band_label_for`. | Not externally driveable: that dict is only ever produced by `enrichment.relative_geometry`, whose types are fixed. The crew-text poll cycle also wraps the dispatch in `except Exception` + `logger.exception` and continues (`logger.py:1624-1726` (`except` at `:1717`)), so the unguarded-poll-loop class recorded from earlier passes does not apply here. |

### What cleared, and how

- **No new read of a truth source.** Every input the summary aggregates is belief: `classification`
  and `cardinality` off the lattice, `last_seen_ago_s` off `contact.last_seen_sim`, and
  `relative_now` from `relative_geometry(enrichment.ownship, world_position)` where
  `world_position` derives from `contact.last_position` through the enrichment cache
  (`tools.py:354`). Ownship's own state is legitimately known. The pull path adds no path from
  ground truth into speech; what it inherits is whatever belief already holds, which is the
  separately-filed `hybrid_source` question and not this feature's.
- **Decision D's presence-claim argument holds.** `_report_scope` reads `get_contacts` and drops
  `certainty == "lost"` (`crew_console.py:2043-2046` (verified)); `contacts._callout_may_speak` is correctly
  **not** applied, so a believed contact is reported qualified rather than withheld. Exposure is
  bounded by belief, not by nothing — the filters only ever narrow that set.
- **Absence claims.** `render_no_view` is extended to `relative` and compared on the wedge centre
  against `rear_cutoff_deg`, applied rather than hardcoded `False` even though all four
  `RelativeSector`s are forward today, so widening the wedge table cannot silently start claiming
  "left, clear" about an unseeable direction. The remaining false `render_clear` for a
  never-looked-at forward direction is Stage 4's, unbuilt and out of scope.
- **The seam is validated, twice.** `logger.py:1499-1505` rejects a `slots` payload that is not a
  dict of `int | str` (bools excluded) before dispatch; `_handle_slotted_report` then validates each
  value against the table that owns it on this side and **drops** an unrecognised one, widening the
  answer rather than raising mid-query. Two *where* slots are rejected adapter-side as a detected
  recognition error; body-layer's clock→sector→relative precedence covers a non-adapter caller.
- **Malformed-input sweep on the new parsers.** Empty string, punctuation, non-Latin script, mixed
  case, `"report clock"`, `"report close"`, `"report left north"`, and every phrase in the table
  whose first word clears `VERB_FLOOR` against either report verb: no exception on any of them, and
  the two-where case returns the intended `token=None, verb_anchored=True`.
- **Legacy-token shadowing is intended and now measured:** on the live voice path `"report north"`
  and `"report two o'clock"` now resolve to `token="report"` with slots rather than to
  `report_bearing_n`/`report_clock_2`. The legacy tokens remain reachable from their other four
  consumers. Not a finding; recorded because it is a behaviour change to shipped commands that a
  later reader of the bench corpus will trip over.

### Verdict

**CHANGES REQUIRED** — one required fix (freshness in the mixed-staleness case). Everything else
clears.
