### Goal
Add a clock-position and range fragment (e.g. "11 o'clock, 3.0 km") to the one-line contact
`summary` string, so it appears in the in-game overlay (replacing today's format there) and in
the console, whenever enrichment data is available.

### Answers to the open questions (decided, not escalated — local/reversible formatting choices)

1. **Format**: extend the existing summary, don't replace its shape. Today's
   `_contact_summary` already carries classification + certainty + recency (`"truck, tracked,
   last seen 17s ago."`) — `plans/body-layer/plan.md` §3.4's own worked example shows exactly
   this blended shape ("BMP, last saw it ... Should be around four o'clock, two and a half
   kilometres."). The user's "truck 11 o'clock, 3 km" example is illustrative of the *new
   fragment*, not a request to drop certainty/recency — nothing in either message asks for that
   information to disappear. Append `", <clock> o'clock, <range> km."` after the existing
   sentence (and after the "Being watched." suffix, if present).
2. **Range units**: no existing km-rounding helper anywhere in the codebase (checked
   `naked_eye_source.py`'s `_quantise_range_m`, which is a classification-bucket helper, not a
   display formatter, and unrelated). Add one small helper, round to 1 decimal km
   (`f"{range_m / 1000:.1f}"`), e.g. `"3.0 km"`, `"0.4 km"`.
3. **Visible vs. not-visible**: always render when `relative_now` is present, regardless of
   `visible`. Bearing/range don't stop being useful the instant a contact is currently seen —
   the field name is `relative_now` (this instant's geometry), not "last known," and gating it
   on visibility would add a branch with no basis in the data model.
4. **Live-path wiring**: verified, no gap. `logger.py`'s `ConsolePerceptionRunner.run_once`
   (L243-249) lazily builds `EnrichmentContext` whenever `world_model_conn`/`theatre` are set,
   and `--world-model-db` is a required argument for `--console` mode (`body-layer/CLAUDE.md`
   "Running the live logger"). So in the live `--console --overlay` path enrichment is always
   populated by the time any event fires — this is a formatting change only, no plumbing fix
   needed.

### Affected Modules / Files
- `body-layer/src/belief/tools.py` — `_contact_summary` gains an optional `relative_now:
  dict[str, object] | None = None` parameter; `_contact_result` passes
  `facts.get("relative_now")` into it (facts is already built first, so this reuses the one
  `relative_geometry()` call `_add_enrichment_facts` already made — no second computation). Add
  a small private `_format_range_km(range_m: float) -> str` helper alongside it.
- `body-layer/src/belief/console.py` — no code change expected. `format_event_for_overlay` and
  `_format_contact_line`/`_format_contact_block` already read `result["summary"]` verbatim, so
  once `_contact_summary` includes the clock/range fragment, both the overlay and the console
  `contacts`/`show <id>` output pick it up automatically — this is the "one summary field" seam
  the module docstring already commits to. Docstring comment near `format_event_for_overlay`'s
  existing `semantic` note may want a one-line addition acknowledging `summary` now also carries
  relative geometry, for a future reader's benefit.
- `body-layer/tests/test_tools.py` — extend/add cases: `_contact_summary`/`_contact_result` with
  and without `relative_now`, clock values at boundary angles (0/360 wrap, already exercised by
  `_clock_position`'s own tests in `test_enrichment.py` — just confirm the summary fragment
  matches), range formatting at sub-km and multi-km values.
- `body-layer/tests/test_console.py` — extend `format_event_for_overlay` tests to assert the
  clock/range fragment appears in the mirrored line when `enrichment` is supplied, and that the
  line is byte-for-byte unchanged when it is not (preserves the existing no-enrichment-means-
  no-change guard already tested there).

### Implementation Plan
1. Add `_format_range_km` to `tools.py`, plus the clock/range fragment logic inside
   `_contact_summary` (new optional param, no-op when `None`).
2. Wire `_contact_result` to pass `facts.get("relative_now")` through — facts must be built
   before summary now, so check/adjust that ordering in `_contact_result` if needed.
3. Run body-layer's test suite; add/extend the unit tests listed above (pure string-formatting
   tests, no live DCS needed, consistent with the subproject's replay-first testing rule).
4. Manual/live acceptance: confirm via `--console --overlay` against a live or recorded session
   that the in-cockpit overlay line now shows the clock/range fragment, per this project's
   pattern of live-acceptance findings feeding back into `console.py`'s docstring (see the
   BL-2.5 "contact id" and "CONTACT_CLASSIFICATION_CHANGED" precedents already in that file).

### Risks & Unknowns
- Overlay line length: BL-2.5's channel is a fixed-duration DCS text message feed with unknown
  practical line-length/wrap behavior (flagged as unverified in that plan). Appending a fragment
  makes every mirrored line longer; if overlay legibility turns out to be a real constraint,
  that's a live-acceptance finding for this feature too, same posture as BL-2.5's own unresolved
  items — not blocking this plan, but worth watching on the first live test.
- Clock position rounds to the nearest of 12 buckets (`_clock_position`, already existing,
  unchanged here) — coarse by design, not something this feature should try to refine.

### Second-order effect
None identified — this is a display-formatting change over an existing enrichment field; it
does not add new belief state, new events, or a new channel, so it does not narrow or unblock
any later BL-x milestone.
