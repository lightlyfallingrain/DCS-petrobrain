# BL-2.5 — session state / resume point

**Transient working file.** Delete at DoD; `plan.md`, `implementation.md`, `review.md` and
`todo/todo.md` are the durable records. Written 2026-09-09 to survive a context clear.

Branch: `feature/dcs-text-panel-output`, branched from local `main`. **Not merged** — merge needs
user approval per `CLAUDE.md`.

## Where this stands

| Stage | State |
| --- | --- |
| 1 — aircraft-layer transport | Done, reviewed, live-checked (collector → UDP datagram confirmed) |
| 2 — overlay Hook script + `.dlg` | **Passed live 2026-09-09** — window renders, lines appear |
| 3 — body-layer wiring | Done, reviewed, fixture-tested |
| 4 — live acceptance sortie | **Passed live 2026-09-09** — contact events render in-cockpit |
| Reviewer | **Approved, no required fixes** (`review.md`) |
| Refinement pass | **Done, unreviewed** (`f8cca80`, `499811b`, `cc4599e`) — see below |
| DoD | Not started; blocked on the confirmation sortie below |

Commits: `7a336f0` (plan) → `9b8115b` (stage 1) → `e380126` (stage 2) → `482ce2a` (stage 3) →
`6675192` (implementation.md) → `d0a0988` (agent memory) → review commit → `43872b5` (output-target
decision) → `ee46c10` (BL-2.6 scheduled) → `eedb1d7` (grading intent).

## The refinement pass in flight

After live acceptance the user raised that the result **imitates** DCS's native radio message panel
rather than being it. Decision (user, 2026-09-09): **keep the overlay, restyle it** — not a switch
to `net.dostring_in` → `trigger.action.outText`. Rationale recorded in `plan.md`, section
"Output-target decision, revisited after live acceptance". The rejected path stays documented and
remains available (DCS-gRPC uses it in production).

**Done 2026-09-09, not yet reviewed and not yet flown.** What was built, against the three tasks
originally specified (kept below since they are still the acceptance criteria for the sortie):

- **Restyle** — `headerHeight = 0` removes the title bar and close button together; the `Box`/`Panel`
  child dropped and window `bkg` set fully transparent (`0x00000000`), per-line text sub-skin `bkg`
  nilled, so text floats over the scene. Position `(20, 50)`, chosen so the rendered text origin
  lands within a few px of `gameMessages.dlg`'s own real `(29, 59)`. `draggable = true` kept —
  compatibility with `headerHeight = 0` confirmed from that same real file. Near-white + 1px black
  shadow was already correct, unchanged.
- **Contact id** — `format_event_for_overlay` now emits `"<contact id>: <kind>, <summary>"`, reusing
  `console.py`'s existing `"<id>: ..."` convention.
- **Clipped line** — new `apply_content_size()` calls `calcSize()` after every `addText()` and
  resizes to the real reported content height, clamped `[60, 380]px`. The plan's one-time diagnostic
  promoted into the live sizing mechanism instead of a bigger guessed constant. **This is genuinely
  new runtime behaviour and the most load-bearing unverified piece of the pass.**

Grounded in real shipped files: all window chrome, position, legibility values, and the
`headerHeight=0` + `draggable=true` compatibility — from `Scripts/UI/gameMessages.dlg`. The
implementer's own judgement, flagged as such: the `MIN/MAX_CONTENT_HEIGHT_PX` bounds and the choice
to make `calcSize()` a live mechanism.

**Six-identical-lines question, partly resolved**: `lifecycle_event_kind` makes a same-contact
re-fire of `CONTACT_DETECTED` structurally impossible — it fires only when `previous_certainty is
None`, true exactly once per contact. So the six lines were either six genuine contacts, or
association-gate churn minting duplicate contacts for one object. Not investigated further, per
instruction; the contact-id fix makes it diagnosable on the next sortie. **Watch for it.**

Original task spec, retained as the sortie's acceptance criteria:

1. **Restyle the overlay to read like DCS's native message feed.** Currently 420×200, top-left,
   with a "Petrobrain Overlay" title bar, an X close button, and an opaque dark panel — all
   inherited from SRS. Wanted: no title bar, no close button, no opaque panel; text reading
   directly over the scene. Ground the values in the real shipped files — DCS's own
   `Scripts/UI/gameMessages.dlg` and `$DCS_INSTALL_PATH/dxgui/` skins — not invented numbers. The
   user flies over pale desert, so glyph shadow/outline for legibility matters more than the panel
   background did. **The DCS install is read-only**: read/grep only, never write under
   `$DCS_INSTALL_PATH`.
2. **Defect — overlay lines carry no contact id.** `belief.console.format_event_for_overlay` emits
   `"<kind>: <summary>"`, so six distinct contacts and one contact re-firing six times render
   identically (visible in the user's screenshot: six identical `CONTACT_DETECTED: OP_ARMORED,
   observed, currently visible` lines). Include the contact id, matching however `belief/console.py`
   already renders ids for the `contacts`/`show C17` commands. **Open question**: whether those six
   lines were six real contacts or a re-fire loop is unresolved — if a re-fire bug is suspected,
   route it to the debugger with the user's log rather than fixing speculatively.
3. **Defect — the window clips its last line** at 420×200 (6th line cut off mid-height). A full
   line should be shown or not shown, never half-rendered. The plan's runtime self-diagnostic
   (`calcSize()` / `getTextLinesCount()`) is the honest way to size this rather than guessing.

Also to update: `aircraft-layer/WORKFLOW.md` (currently describes "420x200px by default, top-left
corner of the screen, draggable" and a titled window) and `body-layer/CLAUDE.md`.

The DCS-side artifacts cannot be verified without a live DCS — mark changed visual behaviour
UNVERIFIED, same discipline as the original stage 2.

## Next steps, in order

1. Reviewer pass on the refinement work (`f8cca80`, `499811b`) — **not yet run**.
2. **User flies one short confirmation sortie** — chrome gone, contact ids on the lines, no clipped
   line. This is the only step that needs the user.
3. DoD, then merge on user approval.
4. Architect pass on **BL-2.6 — Classification refinement** (`todo/todo.md` Milestones), then
   Implementer → Reviewer → DoD per AGENTS.md Auto-Advance. Its full findings and the user's
   "grading is the intent" confirmation are already in the todo entry; do not rediscover them.

## Verification

```sh
ruff format --check <sub>/src <sub>/tests && ruff check <sub>/src <sub>/tests
mypy <sub>/src            # body-layer: run from inside body-layer/ (CWD-resolution note)
pytest <sub>/tests -q     # expect 67 aircraft-layer, 210 body-layer (pre-refinement counts)
```

Commit messages end with:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01UdbeASCrPmbHS9oGnumUm1
```
