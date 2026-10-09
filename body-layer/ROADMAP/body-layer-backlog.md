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
ls body-layer/ROADMAP/ | grep -oE '^BL-B[0-9]+' | sort -t B -k3 -n | tail -1
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
- [[BL-B27]] — `say again` fires on unaddressed cockpit speech
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
