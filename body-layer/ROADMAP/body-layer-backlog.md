# Body Layer — Backlog

The backlog index for this subproject. Split out of `body-layer/ROADMAP.md` on 2026-09-27 and
converted to one file per entry on 2026-10-09. **`body-layer/ROADMAP/body-layer-roadmap.md`
remains this subproject's source of truth for milestone status; this list is its backlog and
nothing else.**

The 2026-09-27 split was not cosmetic, and the reason still holds for the per-entry split that
replaced it. Both files are in the knowledge-graph corpus, whose semantic extraction cache is
keyed per file on content, so *any* edit re-extracts the whole file through an extraction
subagent. `ROADMAP.md` was ~21,900 words — 11,700 of stable milestone history plus 8,600 of
backlog that changes almost every merge — so adding one backlog line re-billed the milestone
history too. Apart from the cost, 1,900 lines was more than anyone wanted to scroll to find an
open item. Per-entry files take that argument to its conclusion: editing one backlog item now
re-extracts one item.

Item IDs are unchanged and stay `BL-B<n>`; see root `CLAUDE.md`, "Backlog Management", for the
never-reuse rule. A new one takes the next unused number; numbers are never reused or renumbered,
`[x]` items included. **Read the highest existing number rather than counting items** — the
mechanical check is now a directory listing:

```sh
ls body-layer/ROADMAP/ | grep -oE '^BL-B[0-9]+' | sort -V | tail -1
```

Entry files live in `body-layer/ROADMAP/` alongside this subproject's milestone and work-item
entries, distinguished only by the `-B` in their ID — see `docs/DOC_CONVENTIONS.md` for the
directory layout, ID scheme and link form this follows. The index carries links and titles only;
status lives on each entry, so this list cannot drift out of sync with it.

**Listed in numeric ID order, not document order.** The ID is the primary handle for a backlog
item — it is what a commit message, a plan or a sortie debrief cites — so a reader arriving with
an ID in hand finds it by scanning rather than by searching. (The source file's own order had
`BL-B30` and `BL-B31` ahead of `BL-B29`, which numeric order quietly repairs; nothing was
renumbered.)

Find the open ones with `grep -l '#status/open' body-layer/ROADMAP/BL-B*.md`, and the rest of the
status vocabulary in `docs/TAGS.md`.

## Items

- [[BL-B1]] — Threat-database follow-on extraction
- [[BL-B2]] — `OP_SRSAM`'s internal range spread
- [[BL-B3]] — Class-level threat rollup joined 3 of ~19 rows
- [[BL-B4]] — `alt_ok` has no hysteresis counterpart
- [[BL-B5]] — Two non-blocking hardening items from watch-reporting
- [[BL-B6]] — `OP_LRSAM` folded into the air-defence command classes
- [[BL-B7]] — F10 radio-menu command input
- [[BL-B8]] — F10 command vocabulary and ownship-relative sectors
- [[BL-B9]] — F10 Watch Nearest reply in contact-report format
- [[BL-B10]] — Movement detection
- [[BL-B11]] — Threat-based report prioritisation
- [[BL-B12]] — Coalition/IFF for contact reports
- [[BL-B13]] — Own perception end-to-end, dropping DCS ambient detection
- [[BL-B14]] — Contact report fine tuning
- [[BL-B15]] — Petrovich's voice has no character
- [[BL-B16]] — Cross-channel contact duplication
- [[BL-B17]] — `certainty`/classification fusion is last-writer-wins
- [[BL-B18]] — Overlay clips its last line at 420×200
- [[BL-B19]] — Overlay has no dismiss affordance
- [[BL-B20]] — Sector coverage
- [[BL-B21]] — More frequent glances at a watched contact
- [[BL-B22]] — Pull-only briefing-derived belief
- [[BL-B23]] — `ContactStore` never pruned
- [[BL-B24]] — Ambiguous reacquisition candidates after a long gap
- [[BL-B25]] — Merge-echo predicate evaluated at the wrong tick
- [[BL-B26]] — Group member facts gathered three times per tick
- [[BL-B27]] — `say again` fires on unaddressed cockpit speech — **DROPPED 2026-10-16**: incorrect STT, not unaddressed speech — a different problem
- [[BL-B28]] — `report right` is not recognised
- [[BL-B29]] — `cancel all` is not in the vocabulary
- [[BL-B30]] — The poll loop runs at ~0.7 Hz against a specified 5 Hz
- [[BL-B31]] — Nothing notices when the live LOS feed is absent
- [[BL-B32]] — `POST /speak` synthesizes TTS inside the poll body
- [[BL-B33]] — Five sequential HTTP GETs with no connection reuse
- [[BL-B34]] — Stale "5 Hz" docstrings
- [[BL-B35]] — Unbounded `response.read()` on peer HTTP calls
- [[BL-B36]] — Speech-log retention, declined
- [[BL-B37]] — Four `assert`s doing real runtime work
- [[BL-B38]] — Two loops still walk every contact ever founded
- [[BL-B39]] — A log that disabled itself reads as one that stopped
- [[BL-B40]] — The last 1.6× of `group_salient_ids`' hoist
- [[BL-B41]] — Callout keeper elected per contact, suppressing per event
- [[BL-B42]] — The LOS sightline cap binds over a dense city
- [[BL-B43]] — Drop `PLAYER_BUBBLE` rows from the detection trace
- [[BL-B44]] — Remove the detection lines below the eyesight graph
- [[BL-B45]] — The `"Safe from <threat>"` close-out call
- [[BL-B46]] — `logger`'s own logger propagates
- [[BL-B47]] — `_is_air_defence` cannot recognise a class-level SAM
- [[BL-B48]] — Infantry is an unbounded cohesion bridge between non-infantry contacts
- [[BL-B49]] — A narrow `report` query is priced as `report_all`
- [[BL-B50]] — Group callout suppression is defeated by any two alternating lines
- [[BL-B51]] — Three copies of the air-defence class set, one drift guard
- [[BL-B52]] — The wake word strips the slots off a `report` command
- [[BL-B53]] — The *what* slot takes seven singular words, and the user's own examples miss
- [[BL-B54]] — `report six o'clock` answers about eight o'clock
- [[BL-B55]] — Position uncertainty is optic-blind, and the 9K113 slice depends on it
- [[BL-B56]] — A fourth copy of the air-defence vocabulary, outside the new guard
- [[BL-B57]] — A class-level installation belief gets a non-zero plausible speed
- [[BL-B58]] — A within-group fold's position drift can widen a cluster enough to absorb an unrelated contact
- [[BL-B59]] — The same fold drift that absorbs an unrelated contact also evicts a real member
- [[BL-B60]] — A misclassified fast mover is now tracked worse than before the fold-displacement bound
- [[BL-B61]] — `group_matches` test 4 cannot tell kinds apart at class level (5th `BL-B47`-family occurrence)
- [[BL-B62]] — The ownship-relative observation channel is general, and only `BL-14` uses it
- [[BL-B63]] — A selective fast lane for ownship telemetry and the currently-selected target
- [[BL-B64]] — the 9K113 sight, entry 1 of 3: perception (spec at `docs/concept/9K113.md`)
- [[BL-B65]] — weapons safety circuit switch — folded into [[BL-B66]] 2026-10-21
- [[BL-B66]] — the 9K113 sight, entry 2 of 3: effectors — power-up, OBSERV, safety bar (slew loop split to [[BL-B80]])
- [[BL-B67]] — the 9K113 sight, entry 3 of 3: the ATGM attack run
- [[BL-B68]] — belief survives a DCS mission restart, because nothing resets it `[>]` deferred
- [[BL-B69]] — the object-permanence shortcut skips the spatial gate with no distance check
- [[BL-B70]] — attack-run guidance: what to say and when (2026-10-15 sortie §1/§2/§4/§8/§9)
- [[BL-B71]] — the least-capable-optic guidance ladder (2026-10-15 sortie §6/§7)
- [[BL-B72]] — a firing unit gives itself away, out to the player bubble (detection only)
- [[BL-B73]] — gun fire makes its firer visible out to the player bubble
- [[BL-B74]] — a SAM launch's smoke trail shows where the launcher was
- [[BL-B75]] — smoke and flare markers as emitters, if DCS exports them `[>]` deferred
- [[BL-B76]] — `", obstructed"` has no live caller: `live_los_clear` is never `False`
- [[BL-B77]] — One hedge, two registers: the group line's hardcoded `"A couple of contacts."`
- [[BL-B78]] — `speech.py`'s module docstring still documents the pre-brevity hedge register
- [[BL-B79]] — `remember_location`'s `label` needs a bound before any dispatcher calls it
- [[BL-B80]] — the 9K113 slew loop: pointing the sight on the player axis (split from [[BL-B66]])
- [[BL-B81]] — radio check: an ordinary command whose answer proves intercom and Petrobrain are up
- [[BL-B82]] — no scanning before takeoff, replacing the on-ground silence default
- [[BL-B83]] — idle 9K113 searches the mission objective area when in range (deferred: no objective datum at runtime)
- [[BL-B84]] — 9K113 search depth adapts to terrain (deferred; perception already handles LOS per look)
- [[BL-B85]] — a contact stuck at `presence` forever can fully starve the sight's search cycle
- [[BL-B86]] — above ~3.6–4 km AGL the sight's idle search cycle goes fully idle — **DECLINED 2026-10-25**: outside the operating envelope
- [[BL-B87]] — `_pending_positional_replies` has no size bound, unlike every other queue in this codebase
- [[BL-B88]] — `join_voice_latency.py` crashes whole on one malformed JSONL line
- [[BL-B89]] — 9K113 scanning procedure: points of interest, not band sweeps (done, merged `92da214a`)
- [[BL-B90]] — configurable cockpit effector sequences: named registry + per-trigger sequence files (after [[BL-B80]])
- [[BL-B91]] — effector-registry TOML renderer did not escape control characters in free-text fields (fixed)
- [[BL-B92]] — `test_connection_reporter_*` tests order-dependent under pytest-randomly (fixed, merged `27f9821f`)
- [[BL-B93]] — `test_tuning.py` autouse fixture leaves the tuning registry empty for later tests
- [[BL-B94]] — named, checked catalogue of state params (light level as the example) `[>]` deferred
- [[BL-B95]] — event-driven behaviour scripting in Lua (was: behaviour trees) `[>]` deferred
- [[BL-B96]] — crew pipeline by default: no mode flags, F10 and overlay removed, `logger` → `body` (done, merged `af9254d5`)
- [[BL-B97]] — attack-run LOS: "eyes on" means line of sight, and "where is it?" (2026-10-24 sortie F2/F3)
- [[BL-B98]] — 9K113 sight returns to dead-ahead after a glance-away instead of staying at its last position (done, folded into BL-B89)
- [[BL-B99]] — Petrovich POV debug view: optic FOV and detections in angle space (done, merged `7796206d`)
- [[BL-B100]] — a wake-prefixed question still defeats `parse_utterance`'s own grammar (found during `[[AA-B7]]` DoD, 2026-10-25)
- [[BL-B101]] — terrain avoidance from flight-path elevation while Petrovich flies (deferred, split from [[BL-16]])
- [[BL-B102]] — "that"/"it" in a command means the contact Petrovich last talked about (done, merged `3a9a1a18`, needs flight)

**Brain-layer backlog items moved out of this index on 2026-10-17** (user direction: *"Put brain
milestone and backlog items under brain layer in folder. Same logic as other layers."*). `BR-B1`,
`BR-B2` and `BR-B3` now live in `brain-layer/ROADMAP/`, indexed by
`brain-layer/ROADMAP/brain-layer-roadmap.md`, and the two `BR-B` / `BL-B` sequences are
independent. This directory holds `BL-`, `BL-B` and `BL-W` only — which is also what makes a
prefix-agnostic mint safe to get wrong here now, rather than merely documented as dangerous.

## Two entries worth knowing about before you read them

- **`BL-B23` carries two records, both verbatim.** Its entry file was created by the Stage 2
  conversion of `body-layer/ROADMAP.md`, which had its own `BL-B23` row, and Stage 3 then appended
  `body-layer/BACKLOG.md`'s own copy of the same item. The two agree on every fact and each holds
  material the other does not; the entry opens with a note saying so. It is the only entry in this
  directory that was reconciled rather than simply extracted.
- **`BL-B34` carries two checkbox blocks, and the second is its own superseded text.** The source
  file held `BL-B34` (resolved) immediately followed by a block headed `BL-B34 (original text)` —
  the same ID twice, deliberately, because the resolution contradicted the original finding's
  premise. Since the filename is the ID alone, both blocks live in `BL-B34.md`, in source order,
  with their original checkbox states (`[x]` then `[ ]`) untouched.
