# PB-1.5 recon: LoGetWorldObjects filtering/cost, and an ambient (non-scope) detection signal

**Date:** 2026-09-08
**DCS version:** not re-verified this session — same install as `2026-09-07-petrovich-perception-export.md` /
`2026-09-08-pb1-live-spike-results.md` (Mi-24P module, HelperAI device ID 6, ASP17 device ID 2
confirmed there)
**Theatre:** n/a (Lua API / cockpit-indication questions, not terrain-specific)

### Question

Two unverified DCS-internals questions blocking the PB-1.5 ("naked-eye visual spotting" channel)
plan:

1. Can `LoGetWorldObjects` be constrained at the export layer (radius/category/coalition
   argument), or is 5 Hz polling of the full global object table unconditionally expensive?
2. Does any HelperAI/cockpit indicator signal reflect a target being noticed **without** the crew
   slewing the ASP-17 sight — i.e. is there a real DCS-sourced gate for "naked-eye" detection, or
   must PB-1.5 rely entirely on a synthetic range/FOV/LOS heuristic?

### Findings

**Q1 — filtering/cost**

- `LoGetWorldObjects(arg)` takes **0–1 arguments**; the only documented argument is a **category
  string**, not a radius or coalition filter: `"units"` (default), `"ballistic"` (unguided
  munitions — bombs/shells/rockets), `"airdromes"`. No radius-around-a-point argument and no
  coalition/IFF filter argument exist in this call's documented signature. — **evidence:**
  documented — **source:** `win-mac-sync/from-windows/Export.lua.reference-file-from-DCS-installation.lua`
  lines 624–629, the stock reference comment block shipped with this DCS install (primary
  source, already local, checked first per instructions).
- Community corroboration: a Hoggit-wiki-adjacent search and the `asherao/DCS-ExportScripts`
  GitHub project both describe the same two-argument set (`"units"`/`"ballistic"`) with no
  distance/coalition filter mentioned anywhere. No third-party project found that pre-filters
  server-side — every consumer (Tacview, DCS-ExportScripts, LiveMap, etc.) calls it unfiltered
  and does its own client-side filtering after the fact. — **evidence:** forum/community-claim,
  moderately corroborated (multiple independent sources agree) — **source:** WebSearch results
  citing `wiki.hoggitworld.com/view/DCS_export`, `github.com/asherao/DCS-ExportScripts`,
  `github.com/Serious-Uglies/LiveMap`.
- Performance: real, but not quantified for realistic object counts. Tacview's own wiki states
  `LoGetWorldObjects()` "could be quite inefficient and can slow down the whole simulation," that
  it "is not possible to split it over several frames," and separately notes "DCS World
  programmers have been working to optimize `LoGetWorldObjects` so it takes just a few percent of
  the frame" — i.e. ED has already done some of this optimization internally, but no number is
  given for what "few percent" means at what object count, and no source gives a concrete
  FPS-vs-object-count curve. — **evidence:** forum-claim-unverified (single source, Tacview
  wiki, no primary confirmation) — **source:** `tacview.fandom.com/wiki/FPS_Loss_While_Recording_Your_Flight_in_DCS_World`
  (via WebSearch summary; not independently fetched/read in full this session).
- Two direct ED-forum threads (`forum.dcs.world/topic/133284-logetworldobjects`,
  `forum.dcs.world/topic/302542-how-to-use-logetworldobjects-only-for-my-aircraft`) look directly
  on-topic for this question but returned HTTP 403 to WebFetch — consistent with this project's
  known `forum.dcs.world` fetch-blocking (`aircraft-layer` memory:
  `.claude/agent-memory/investigator/forum-dcs-world-fetch.md`). Not read this session.

**Q2 — ambient/naked-eye detection gate**

- The prior spike (`2026-09-08-pb1-live-spike-results.md`, finding 1) is the strongest evidence
  available and is directly on point: across ~4000 live samples over 4 flights, HelperAI's
  `list_indication(6)` leaves `middle_list_text` / `lower_list_text` / `lower_lower_list_text`
  populated with real classification text **only once a target was actively selected**, and the
  `crosshair` child (predicted to carry `hdg_text`/`az_text`/`el_text`) stayed empty
  (`children are {}`) across every sample in every flight, including flights where the sight was
  actively used. — **evidence:** reproduced-locally (live DCS probe, already run) — **source:**
  `2026-09-08-pb1-live-spike-results.md`.
- This session's re-read of `win-mac-sync/from-windows/HelperAI_page_common.lua` (primary source,
  the UI-definition file that builds device 6's element tree) surfaces **two list leaves the
  prior spike's probe never explicitly logged**: `upper_list_text` (line 924–932) and
  `upper_upper_list_text` (line 914–922). These sit in the *same* 5-line list structure as
  `middle_list_text`/`lower_list_text`/`lower_lower_list_text` (all five share
  `middle_list_holder` as a common ancestor, all five are driven by the same
  `{{"show_list"}}` / `{{"show_list_VR"}}` controller gating the whole holder element) — so by
  construction they almost certainly share the same population gate as the three already tested,
  but this was never directly observed under an unselected-but-visible-target condition. —
  **evidence:** inferred (structural, from primary-source Lua) — **source:**
  `win-mac-sync/from-windows/HelperAI_page_common.lua` lines 879–952.
- The UI-definition Lua files (`HelperAI_page_common.lua`, `HelperAI_indicator.lua`,
  `HelperAI_page.lua`, `elements_defs.lua`, `indicators_list-grepped.lua`) contain only element
  wiring (positions, textures, controller names) and **zero comments or logic describing when any
  controller value changes** — confirming, again, that the actual detection/gating logic is
  native/compiled and unreachable from any local Lua source. This matches the prior session's
  "Reverse-engineering scope decision" (out of scope). — **evidence:** documented (absence
  confirmed by direct read) — **source:** files listed above, read in full or via targeted grep
  this session.
- `indicators_list-grepped.lua` (the full Mi-24P indicator/device registration list) shows no
  other device plausibly carrying an independent ambient ground-target detection signal:
  `9K113_CAM` (Shturm ATGM seeker camera), `PKV`, `ASP17`, `ControlsIndicator`, `MapDisplay`,
  `HelperAI_indicator` (device 6, already tested), `g_panel` (gunner control panel),
  `crew_indicator`, `AI_Wheel` (Petrovich command-wheel UI). None of the untested ones are
  plausible naked-eye-detection candidates by name/purpose — `9K113_CAM` is missile-seeker-specific
  (weapon-select-gated, same family of gate as ASP-17), the rest are control/mode UI, not
  detection UI. — **evidence:** inferred (from device list + names, not individually probed) —
  **source:** `win-mac-sync/from-windows/indicators_list-grepped.lua`.
- Forum evidence (search-snippet only — `forum.dcs.world` 403'd WebFetch again this session, same
  as Q1) is directionally consistent with "list is selection/weapon-mode-gated, not ambient":
  - Thread `topic/388039` ("Mi-24 Petrovich Target list constant refreshing issue"): described as
    a bug where the target list "generated by Petrovich AI **when using missiles**" refreshed too
    fast to select — i.e. this list's population is tied to ATGM/weapon-selection mode, not a
    passive "anything spotted" state. A later DCS changelog snippet ("Petrovich AI target list
    refresh interfering with user choosing the target - Fixed") corroborates the bug existed and
    was fixed, without adding detail on the ambient-detection question.
  - Thread `topic/366508` ("Petrovich Not Spotting Targets After Latest Update") — **retracted,
    see Session 3 correction below.** The WebSearch snippet available at the time this bullet was
    first written was misleading; the full thread (pasted by the user in Session 3) shows the
    "acknowledges searching... doesn't list anything" symptom was a genuine detection bug (ED
    confirmed root cause: mission fog set to `Auto` blinded Petrovich outright; a separate,
    still-live LOS bug was also discussed), not evidence of two independent channels (audio vs.
    text) firing out of step. Do not use this thread to support an audio/list-text channel-split
    hypothesis — see Session 3 addendum.
  - `topic/388039` was **not** independently re-read in Session 3 (only 366508, 278063, and
    334079 were pasted by the user) — its finding above still rests on a search snippet only. Per
    this project's standing rule (`forum-dcs-world-fetch.md`), treat it as a lead, not settled
    evidence, until read directly.

### Reproducible Test

Not run this session (no live DCS access from here; per the user's standing execution-boundary
rule, live DCS sessions are run by the user). Two things would close the remaining gaps, both
extensions of the already-built PB-1 spike harness (`win-mac-sync/to-windows/Export.lua`):

1. **Close the `upper_list_text`/`upper_upper_list_text` gap.** Add both leaf names to the
   existing HelperAI dump/log path (same mechanism already logging `middle_list_text` etc. — see
   `plans/pb1-perception-logger/plan.md` stage 1's harness) and fly one short sortie with a Ural
   truck visible-but-unselected, then selected. Expect (per the structural inference above) both
   leaves to stay empty until selection, matching the three already-tested leaves — but this has
   not been directly observed and would upgrade "inferred" to "reproduced-locally."
2. **Directly settle the audio-vs-list-text question raised by thread 366508.** During a sortie,
   have the user note the exact in-game moment Petrovich's voice callout fires (the "truck, 2
   o'clock" cue) against the debug-log timestamp, and check whether *any* `list_indication(6)`
   leaf (not just the three-to-five list-text leaves — the full recursive dump, as already
   captured by `debug_dump("LoGetWorldObjects()", ...)`'s sibling call for HelperAI) changes
   value at that exact moment, before any scope/weapon selection happens. A single sortie with a
   few naked-eye-only passes (never touching the ASP-17 slew) would be a clean, minimal test: if
   nothing in the dump changes at the moment of the voice line, that's a clean "confirmed absent"
   for any Lua-readable ambient gate.

### Possible Approaches

Given the current evidence, PB-1.5 most likely needs to assume **no real DCS-sourced ambient
detection gate exists** and design accordingly, with a path to upgrade later if the live probe
above finds otherwise:

- **Default (recommended) design**: naked-eye channel is a synthetic plausibility heuristic layered
  on unfiltered `LoGetWorldObjects` data — range + FOV cone (crew's actual look direction/cockpit
  view angle) + terrain LOS — exactly the "materially weaker defense of omniscience" case flagged
  in the task background. Mitigate the omniscience concern architecturally rather than via a real
  gate: keep the heuristic conservative (tight FOV, short max range, real LOS check against
  terrain — not just object existence), and treat its output as a *lower-confidence* tier
  explicitly distinguishable from the scope channel's real gate, so downstream memory/dialogue
  code can weight or word them differently (e.g. hedge naked-eye callouts, don't hedge
  scope-confirmed ones).
- **Do not block PB-1.5 on the two probes above** — they're cheap, low-risk, and worth running
  opportunistically (e.g. folded into the next live test session for something else), but neither
  is likely to reverse the conclusion given how consistent the existing evidence already is (empty
  crosshair every sample across 4 flights; forum reports independently describing an empty list
  despite "clearly visible" targets).
- **If probe 2 above ever finds a real per-frame signal correlated with the voice callout** (even
  a boolean/param-handle flip with no text), that would upgrade the naked-eye channel to a real
  gated signal matching PB-1's scope channel's design — worth a fast follow-up plan revision if it
  happens, not worth delaying PB-1.5 to chase now.

**Q1 recommendation**: filter Lua-side by manual distance check before building the JSON payload,
even though no native radius/coalition argument exists. Rationale: (a) it's cheap to add now while
touching this code path anyway, (b) it caps payload size and downstream parsing cost regardless of
what `LoGetWorldObjects`'s own per-call cost turns out to be, and (c) the evidence on native-call
cost is directionally "can be a problem, ED has partially mitigated it, no hard numbers" — not
strong enough to justify leaving an unbounded object list flowing through the pipe at 5 Hz when a
cheap guard is available. Do **not** rely on the category argument (`"units"`) for this — it's
already the default and doesn't reduce count within the units category. This is a recommendation,
not a decision — Architect should confirm against PB-1.5's actual realistic mission object-count
expectations before finalizing.

### Session 2 addendum (2026-09-08, later same day) — new evidence from a user-supplied screenshot

The user supplied a screenshot of a YouTube video showing the Mi-24P's on-screen radio-message
panel (normally top-right, top-of-screen in the screenshot's VR layout) displaying, in sequence:
`OBSERV OFF` → `9 CONTACTS, 1 O'CLOCK` → `OBSERV ON` → `CAN'T MOVE SIGHT YET`. This changes the
picture for Q2 materially and is treated as a new finding, not a revision of the above.

- **`9 CONTACTS, 1 O'CLOCK` is exactly the ambient/naked-eye signal Q2 was looking for** — per the
  user's own account, this fires from naked-eye spotting ("this is the eyeball sight detection, it
  happens"), not from a scope-selection event, and it carries structured content (a contact
  **count** and a **clock-position bearing**), which is richer than anything seen in the
  `list_indication(6)` text tree tested in Session 1. This is a real, observed, in-game signal —
  **evidence: reproduced-locally is too strong a label (not yet captured via Lua), so classify as
  forum/user-observation-confirmed** — **source:** user-supplied screenshot (primary observation).
  (An earlier draft of this bullet cited a WebSearch summary of `topic/278063-observation-switch/`
  claiming a "roughly 10-second calibration delay" — that number does not appear in the actual
  thread text and was a WebSearch-summary artifact, not a real citation. Retracted; see Session 3
  correction below for what that thread actually says.)
- **This is DCS's native subtitle/caption system, not a mission-scripted `trigger.action.outText`
  message.** A WebSearch of `forum.dcs.world/topic/126891-how-to-disable-radio-message-subtitles/`
  (title-and-snippet only) confirms DCS has a dedicated `SUBTITLE` audio option that toggles
  on-screen text captions for radio/AI-voice transmissions independent of the audio itself — this
  is the generic mechanism rendering the panel in the screenshot, used across multiple modules for
  AI-voice-tied captions, not something specific to a Lua UI element we've already read. —
  **evidence:** forum-claim-unverified (search snippet only) — **source:** WebSearch summary of
  the thread above; not fetched directly (403, see below).
- **No documented Lua Export/hook API exists to read this subtitle/message text directly.** The
  full callback and function list on Hoggit's `DCS_server_gameGUI` page (fetched and read in full
  this session) — `onMissionLoadBegin/End`, `onSimulationStart/Stop/Frame/Pause/Resume`,
  `onGameEvent`, `onPlayerConnect/Disconnect/...`, `send_chat`/`recv_chat`, `log`/`trace`, etc. —
  contains nothing that fires on a displayed subtitle/caption or exposes its text. This is the
  server-side hook API (different scope from the mission-scripting/export environment already
  used elsewhere in this project), but it's the most plausible place such a hook would live if one
  existed, and it doesn't. — **evidence:** documented absence (direct read of the full page) —
  **source:** `wiki.hoggitworld.com/view/DCS_server_gameGUI`.
- **New, not-yet-examined lead: `devices.PKV`.** `indicators_list-grepped.lua` line 3 registers a
  `Mi24::ccPKV` indicator at `PKV/Indicator/PKV_init.lua` — position index 1 in the same
  0-indexed registration order that correctly predicted `ASP_17V`'s device ID (2) and
  `HelperAI`'s device ID (6) in Session 1's live spike. `PKV` is a plausible fit for the
  periscope/observation-sight subsystem specifically (`OBSERV ON/OFF`, `CAN'T MOVE SIGHT YET` all
  read as periscope-state text, not HelperAI-detection text) — this device's Lua source has never
  been fetched from the Windows install and was not part of any prior session's file list. Whether
  `9 CONTACTS, 1 O'CLOCK` itself is also on this device's tree, on HelperAI's tree (untested
  leaves `upper_list_text`/`upper_upper_list_text` from the main findings above are still
  candidates), or on neither (subtitle-only, no Lua mirror) is unresolved — **evidence:**
  inferred (structural, from device registration order) — **source:**
  `win-mac-sync/from-windows/indicators_list-grepped.lua` line 3, cross-referenced against
  Session 1's confirmed device-ID-by-position method
  (`2026-09-08-pb1-live-spike-results.md`).

**Revised recommendation for Architect**: do not treat Q2 as settled "confirmed absent" on the
strength of Session 1 alone — this screenshot is real evidence that a genuine ambient, non-scope
detection signal exists and is richer than assumed (count + clock bearing, not just a
classification string). Whether it's *Lua-exportable* is still open. Two concrete next steps, in
priority order:

1. **Fetch `PKV/Indicator/PKV_init.lua` and any sibling files under `PKV/Indicator/`** from the
   Windows DCS installation (same retrieval pattern already used for `asp17/*.lua` — see
   `win-mac-sync/WORKFLOW.md` or however those were originally pulled) and read them the same way
   `ASP_17V_page.lua` was read in the prior session, to see if `OBSERV`/`CAN'T MOVE SIGHT YET`/a
   contact-count-and-clock-bearing controller exists in this device's element tree.
2. **Live probe**: extend the existing debug-log harness to dump `list_indication(1)` (PKV,
   hypothesis) alongside the existing `list_indication(6)` (HelperAI) full recursive tree, across
   a sortie with naked-eye-only passes (no scope slew), and check both trees at the exact moment a
   `"N CONTACTS, H O'CLOCK"` line appears on screen/in audio. This is the same class of probe
   described in Reproducible Test item 2 above, now with a second, better-motivated device
   candidate (1, not just 6) and a concrete string pattern to match against rather than a vague
   "does anything change."

If probe 2 finds the count/bearing mirrored in an exportable param or text leaf, this reverses the
"no real gate" conclusion for the naked-eye channel entirely — worth a fast plan revision rather
than defaulting straight to the synthetic-heuristic fallback.

### Session 3 addendum (2026-09-08, later same day) — three forum threads read in full

The user pasted the full text of three threads that were search-snippet-only in Session 2. None
of them settle the PKV/Lua-exportability question, but two of them correct claims made earlier in
this document on the strength of WebSearch summaries alone — recorded here as the project's
"don't blur search-snippet into fact" rule in action.

- **`topic/278063-observation-switch` (read in full).** About a July 2021 key-binding change (the
  "Observation Switch" command moved to the Gunner position after a patch), not about the text
  strings in the screenshot at all. Confirms "Petro aft short" closes the sight/protection doors,
  and one reply (`dfpoor`) mentions waiting "3 seconds for the doors to open" after commanding
  Petrovich to search — a real number, but for door-open latency after a weapon-mode switch, not
  necessarily the same thing as the screenshot's `CAN'T MOVE SIGHT YET` slew-calibration message.
  **The "~10-second calibration delay" claim in the Session 2 addendum came from a WebSearch
  summary artifact with no basis in the actual thread text — retracted.** This thread neither
  confirms nor rules out the PKV hypothesis; it's simply not informative for that question. —
  **evidence:** documented (thread read in full) — **source:** `topic/278063-observation-switch`,
  pasted by user, 2026-09-08.
- **`topic/366508-petrovich-not-spotting-targets-after-latest-update` (read in full) — corrects a
  Session 2/main-findings misreading.** The actual bug (BIGNEWY/ED confirmed root cause,
  2024-12-26): Petrovich AI "does not see the targets when fog is in Auto mode" — i.e. mission fog
  set to `Auto` blinded Petrovich's own detection outright; a separate, longstanding LOS bug
  (units/terrain blocking sight lines from certain angles only) was also discussed as a secondary
  cause. **This is not evidence of two independent channels (a voice/audio channel vs. the
  `list_indication` text channel) firing out of step** — the "he says searching but list stays
  empty" symptom described in the OP's post was Petrovich genuinely finding nothing (a rendering/
  detection bug), not a text-channel failing to mirror a real detection. The main-findings bullet
  above citing this thread as support for an audio/list-text split has been retracted inline. This
  thread is **not usable evidence either way** for the Q2 architectural question — it neither
  confirms nor denies that `9 CONTACTS, 1 O'CLOCK`-style ambient callouts have a Lua-readable
  companion. — **evidence:** documented (thread read in full; supersedes the search-snippet-based
  citation) — **source:** `topic/366508-...`, pasted by user, 2026-09-08.
- **`topic/334079-text-message-generation-from-exportlua-or-hook-functions` (read in full).** OP
  asks whether an on-screen message can be *generated* (sent) from `export.lua`/a hook function
  (not from mission scripting). Single reply (`cfrag`) suggests untested:
  `dostring_in()` with `"trigger.action.outText('some text')"` might work from that context. No
  confirmation either way, and this is about **writing** to the on-screen message queue, not
  **reading** what DCS's own native subtitle/caption system displays — orthogonal to the question
  of whether `9 CONTACTS, 1 O'CLOCK` can be read from Lua. Mildly useful only as confirmation that
  the on-screen message queue itself is `trigger.action.outText`-shaped and reachable from a hook
  context in principle, which doesn't help intercept a different (native voice-caption) writer
  into the same queue. — **evidence:** documented (thread read in full, but inconclusive even
  within itself — OP never confirmed the suggestion worked) — **source:** `topic/334079-...`,
  pasted by user, 2026-09-08.

**Net effect on the recommendation**: unchanged. None of these three threads bear on whether
`devices.PKV` (or any other device) mirrors the ambient contact-count/clock-bearing text as an
exportable Lua value. The two concrete next steps from the Session 2 addendum (fetch
`PKV/Indicator/PKV_init.lua` from Windows; live-probe `list_indication(1)` alongside
`list_indication(6)` during a naked-eye-only pass) remain the only paths that can actually answer
the question — forum research is now exhausted for this specific sub-question, not just
rate-limited by 403s.

### Unresolved

- No confirmed, quantified per-call cost of `LoGetWorldObjects` at realistic object counts
  (~50–200 units) — only qualitative "can be inefficient, partially optimized by ED" claims from a
  single secondary source (Tacview wiki). The two most on-topic ED forum threads are unread (403
  blocked); paste-in-manually is the fallback per project convention if the user wants a stronger
  source than the Tacview-wiki summary before finalizing the filtering design.
- `upper_list_text` / `upper_upper_list_text` population behavior is inferred from shared
  structure, not directly observed under an unselected-target condition.
- Whether Petrovich's ambient callout (`9 CONTACTS, 1 O'CLOCK`, and the "truck, 2 o'clock"-style
  voice line) has *any* Lua-readable companion signal at all (vs. being a pure native
  subtitle-system event with no exported state) is the single most architecturally important open
  question, and — after Session 3's full-thread reads — is now supported by **no forum evidence
  either way** (the thread previously cited for this, topic 366508, turned out on full read to be
  about an unrelated fog-rendering bug, not a channel-separation observation; see Session 3
  addendum). This is a genuinely open question with zero indirect evidence now, not a
  weakly-supported one. A live probe (Reproducible Test #2, refined by the Session 2 addendum to
  target `list_indication(1)`/PKV specifically) is the only way to settle it.
- Four forum threads found and still not read this session, all 403-blocked to WebFetch:
  `topic/133284-logetworldobjects`, `topic/302542-how-to-use-logetworldobjects-only-for-my-aircraft`
  (both Q1/performance), `topic/388039-mi-24-petrovich-target-list-constant-refreshing-issue`,
  `topic/288960-petrovich-target-list` (both Q2/list-gating). `topic/278063-observation-switch`,
  `topic/366508-petrovich-not-spotting-targets-after-latest-update`, and
  `topic/334079-text-message-generation-from-exportlua-or-hook-functions` were read in full in
  Session 3 (see addendum) and did not resolve the core question. If the user wants the remaining
  four upgraded from search-snippet to read evidence, they'd need to be opened manually and pasted
  back per this project's standing rule.
- Whether `devices.PKV` (indicator registration position 1) is the actual source of the
  `OBSERV`/`CAN'T MOVE SIGHT YET`/contact-count-and-clock-bearing subtitle text is an inferred
  hypothesis only — `PKV/Indicator/PKV_init.lua` and its sibling files have never been fetched
  from the Windows install in this project. This is the single highest-value next artifact to
  pull, per the Session 2 addendum above.

---

## Session 4 Addendum (2026-09-09) — PKV_init.lua read

**File:** `PKV_init.lua`, fetched from Windows DCS install to
`win-mac-sync/from-windows/PKV_init.lua` (1277 bytes). No sibling PKV files (`PKV_base_page.lua`,
`PKV_page.lua`) came over in this sync — only the init/registration file.

### Findings

- `PKV_init.lua` confirms `indicators_list-grepped.lua` registration: `devices.PKV` is indicator
  registration position 1 (`indicators[2]` in the 1-indexed dump, immediately after `9K113_CAM`),
  consistent with the slot-position method that previously correctly predicted `ASP17=2` and
  `HelperAI=6`. — **evidence:** reproduced-locally (file read) — **source:**
  `win-mac-sync/from-windows/PKV_init.lua`, `indicators_list-grepped.lua`.
- `PKV_init.lua` itself is purely a **page/mode registration shell**: it defines
  `indicator_type = COLLIMATOR`, page IDs (`PAGE_OFF`/`PAGE_ON`), master modes (`SIGHT_OFF`/
  `SIGHT_ON`), a `pages_by_mode` state machine, and points `page_subsets` at two *other* files —
  `PKV/Indicator/PKV_base_page.lua` (subset `SIGHT_BASE`) and `PKV/Indicator/PKV_page.lua` (subset
  `SIGHT_COMMON`) — which carry the actual controller/indicator/text definitions (by analogy with
  how `HelperAI_indicator.lua` similarly just dispatches into `HelperAI_page_common.lua`, where
  the real `list_indication` controller tree lives). Neither `PKV_base_page.lua` nor
  `PKV_page.lua` has been fetched yet. — **evidence:** reproduced-locally (file read) — **source:**
  `win-mac-sync/from-windows/PKV_init.lua` lines 14-34.
- `grep -il "contact|o'clock|oclock|count"` across every `.lua` file currently synced from
  Windows (`PKV_init.lua`, `elements_defs.lua`, `Export.lua.reference-file...`,
  `HelperAI_page_common.lua`, `HelperAI_page.lua`, `HelperAI_indicator.lua`,
  `indicators_list-grepped.lua`) returns **zero matches**. No contact-count or clock-bearing
  string/controller/param exists in any file read so far, including the previously-read
  `HelperAI_page_common.lua`. — **evidence:** reproduced-locally (grep) — **source:** local grep
  over `win-mac-sync/from-windows/*.lua`.
- No shared param handle referencing detection/contact state was found in `PKV_init.lua` — it
  contains no `get_param_handle` calls or controller definitions at all (that machinery, if
  present for PKV, lives in the two unfetched page files).

### Verdict

**Inconclusive — PKV_init.lua neither confirms nor refutes the hypothesis.** It's the wrong
layer: it's a mode/page dispatcher, not the indicator's text-tree definition. The file that would
actually carry (or rule out) a `list_indication`-style contact-count/bearing controller is
`PKV/Indicator/PKV_page.lua` (and possibly `PKV_base_page.lua`), neither of which has been synced
from Windows yet.

**Two remaining paths, either sufficient to resolve this:**
1. **Fetch `PKV/Indicator/PKV_base_page.lua` and `PKV/Indicator/PKV_page.lua`** from the DCS
   install (same directory as `PKV_init.lua`) and grep them the same way — this is the direct
   continuation of the file-reading approach that already correctly narrowed the search to `PKV`.
2. **Live probe**, if the file read is inconclusive or unavailable: call `list_indication(1)`
   (device index 1 = PKV, per the registration table) alongside the already-working
   `list_indication(6)` (HelperAI), sampled continuously during a flight segment where the crew
   makes an **unaided (no scope-slew) naked-eye spot** that produces the `"N CONTACTS, H O'CLOCK"`
   subtitle. Compare: does `list_indication(1)`'s returned string tree contain a count/bearing
   field at the moment the subtitle fires, or does it stay static/empty through the event? This is
   the only test that can distinguish "PKV mirrors the ambient callout as exported state" from
   "the callout is a pure native-audio/subtitle event with no Lua-readable companion at all."

Given the zero-evidence result across every file read so far (Session 3's forum exhaustion +
Session 4's file read), the live probe is now the higher-value next step over chasing more static
files, unless the two missing PKV page files are trivial to pull in the same sync pass.

### Unresolved

- `PKV_page.lua` / `PKV_base_page.lua` content — unread, would directly answer the question.
- Whether `list_indication(1)` returns anything at all outside of PVK's mechanical
  on/off/slew-limit state remains untested live.

---

## Session 5 Addendum (2026-09-09, Windows machine) — PKV page files read (hypothesis refuted), and the ambient-callout vocabulary found

**Machine:** Windows (direct DCS install access, no Dropbox sync needed).
**DCS version:** `2.9.29.27278` (`/mnt/f/Games/DCS World/autoupdate.cfg`).
**Files fetched** (DCS install → `win-mac-sync/from-windows/`): `PKV_base_page.lua`,
`PKV_page.lua`, `PKV_definitions.lua`, plus four previously-unread HelperAI files —
`HelperAI.lua`, `HelperAI_sound.lua`, `HelperAI_lengths_ng.lua`, `HelperAI_reporting_names.lua`.

### Finding 1 — the PKV hypothesis is **refuted**

`PKV_page.lua` (17 lines) and `PKV_base_page.lua` (77 lines) contain **no text elements, no
`list_indication` tree, and no detection-related controllers**. PKV is purely the PKV-gunsight
*reticle renderer*: `PKV_page.lua` draws one collimated texture element (`pkv_grid`) with a single
controller `{{"SightBrightness"}}`; `PKV_base_page.lua` adds two hidden mesh polys
(`SymbologyBox`, `total_field_of_view` — a 32-vertex circle at `TFOV = 110` mrad, both
`isvisible = false`); `PKV_definitions.lua` is a texture-element helper factory. There is no
`get_param_handle`, no `ceStringPoly`, no count/bearing anything.

**Conclusion:** `devices.PKV` does not mirror the ambient contact callout. The Session 2 structural
inference (registration position 1 = periscope/observation subsystem = plausible source) was
wrong — PKV is the sight *optics*, not the observation *logic*. — **evidence:**
reproduced-locally (full file read) — **source:** `win-mac-sync/from-windows/PKV_page.lua`,
`PKV_base_page.lua`, `PKV_definitions.lua`.

Corollary: the live probe of `list_indication(1)` proposed as Session 4's step 2 is now **low
value** — there is no string tree on that device to return. Deprioritize it.

### Finding 2 — the `"N CONTACTS, H O'CLOCK"` callout is **real, and its full vocabulary is in plain Lua**

`HelperAI_lengths_ng.lua` (never read in any prior session) is a WAV-duration precomputation table
that hands `filenames_for_c` / `times` to native code. Its `filenames` list is, in effect, **the
complete enum of Petrovich's composed-speech fragments**, each annotated with its C-side enum name
in a trailing comment. The ambient spotting callout is assembled at runtime from these fragments —
which is exactly why Sessions 1–4 found no literal `"CONTACTS"` / `"O'CLOCK"` string anywhere.

The vocabulary (verbatim enum names from the comments):

| Dimension | Fragments |
|---|---|
| Detection event | `OP_SEE_AIR`, `OP_SEE_GROUND` (`Op_AirDetected`, `Op_GroundDetected`) |
| Acknowledgement | `OP_ROGER` (`Op_RogerSearch`) |
| Bearing | `OP_A1H` … `OP_A12H` — 12 clock positions |
| Range | `OP_D100M`…`OP_D1000M` (100 m steps), `OP_D1_1p5k`…`OP_D4p5_5k` (500 m steps), `OP_D5_6k`…`OP_D9_10k` (1 km steps), `OP_D10k` (beyond) — **24 buckets** |
| Elevation | `OP_TARGET_HIGHER`, `OP_TARGET_LOWER` |
| Count | `OP_1UNIT`, `OP_2UNITS`, `OP_3UNITS`, `OP_TO5UNITS`, `OP_5TO7UNITS`, `OP_8TO10UNITS`, `OP_ABOUT15UNITS`, `OP_MORETHAN15UNITS` |
| Formation | `OP_SINGLE`, `OP_GROUP` |
| Ground class | `OP_ARMORED`, `OP_TRUCK(S)`, `OP_INFANTRY`, `OP_SRSAM`, `OP_MRSAM`, `OP_LRSAM`, `OP_SPAAG`, `OP_ZU23`, `OP_GROUPSOMETHING`, `OP_SHIP(S)` |
| Air class | `OP_HELI(S)`, `OP_COMBATHELI(S)`, `OP_TRANSPORTHELI(S)`, `OP_UNMANNED`, `OP_PROPPLANE(S)`, `OP_JET(S)` |
| Other | `OP_LAUNCH`, smoke colours (`OP_WHITESMOKE`…`OP_BLACKSMOKE`) |

The user's observed `9 CONTACTS, 1 O'CLOCK` is `OP_8TO10UNITS` + `OP_A1H`. — **evidence:**
reproduced-locally (full file read) — **source:**
`win-mac-sync/from-windows/HelperAI_lengths_ng.lua` lines 20–120.

Note the sound-*event* catalogue in `HelperAI_sound.lua` (`observ_on`, `target_acq`,
`still_searching`, `sight_blocked`, …, ~100 CPG events, one `.ogg` per event) is a **separate,
non-composed** channel and contains **no** contact-count/bearing event. The ambient callout lives
only in the composed `_lengths_ng` fragment bank. This distinction matters: the two channels are
wired differently, and only the composed one carries structured perception content.

### Finding 3 — DCS's own naked-eye detection model constants (directly reusable for PB-1.5)

`HelperAI.lua` (72 lines, never read in any prior session) is a plain-Lua tuning-constant file for
the Petrovich AI, and it exposes ED's actual detection parameters:

```lua
group_criterion              = 20      -- units, grouping threshold
min_angular_radius_for_group = 0.05    -- rad
scan_rad_around_point        = 2500    -- m
min_angular_radius = { lowres = 0.0043, medres = 0.008, hires = 0.02, iff = 0.025 }  -- rad
min_contrast_f               = 0.001
extra_eyesight_ratio         = 4.0
min_fog_transparency         = 0.3
slowpoke_search_radius       = 15
atgm_range_114 = 4500 ; atgm_range_120 = 6000
```

`min_angular_radius` is precisely a **range-by-target-size curve**, expressed as ED intends it: a
target is detectable when its angular radius exceeds a threshold that varies by recognition tier
(`lowres` = "something is there" ≈ 0.0043 rad → a 6 m truck detectable to ~1.4 km; `medres`,
`hires` = classification tiers; `iff` = friend/foe tier, the strictest). Combined with
`min_contrast_f`, `min_fog_transparency`, and `extra_eyesight_ratio`, this is a far better basis
for PB-1.5's plausibility filter than an invented heuristic. — **evidence:** reproduced-locally
(full file read) — **source:** `win-mac-sync/from-windows/HelperAI.lua`.

### Finding 4 — exhaustive negative on a literal callout string

`grep -rIi` for `contact` / `o'clock` / `oclock` across: the entire `Mods/aircraft/Mi-24P/` tree
(all Lua), the Mi-24P `l10n/en/LC_MESSAGES/messages.mo` (65 strings, cockpit-options only), **all**
`l10n/en/*.mo` files in the DCS install (only `dcs.mo` carries the 376 `pAi:` reporting names — no
count/bearing template among them), and `strings`/`strings -el` over `Mi24.dll` and
`CockpitMi24.dll` — **zero matches** for a contact-count or clock-bearing template. Finding 2
explains why: there is no template, only concatenated audio fragments composed natively.
— **evidence:** reproduced-locally (grep/strings) — **source:** local searches this session.

### Verdict / impact on PB-1.5

1. **A real ambient (naked-eye) detection channel unambiguously exists in DCS**, with a
   well-defined perceptual granularity that DCS itself considers correct for a crew member:
   coarse class, clock bearing, bucketed range, bucketed count, higher/lower. This is a strong
   anti-omniscience template — arguably *better* than what PB-1.5's plan currently proposes,
   because it is ED's own model of what the co-pilot can perceive, not ours.
2. **It is still not shown to be Lua-exportable.** The fragment bank is consumed by native code
   (`filenames_for_c`); no `list_indication` tree, param handle, or export hook has been found
   that mirrors the composed callout. The PKV lead is now closed. The remaining untested leaves
   are HelperAI's `upper_list_text` / `upper_upper_list_text` (Session 1's structural inference
   says they share the selection gate, unverified), and any `get_param_handle` on device 6.
3. **Design consequence, either way:** even if the callout proves unexportable, PB-1.5 should
   model its synthetic filter on the constants in Finding 3 and quantise its output to the
   vocabulary in Finding 2, so the naked-eye channel produces the same shape of belief DCS's own
   crew AI does. That decouples the design from the exportability question — a later live probe
   that finds a real signal would then be a *source* upgrade, not a redesign.

### Unresolved (carried forward)

- Whether **any** exported Lua value changes at the moment the ambient callout fires. The
  remaining test is the Session-1-style live probe on device 6 (full recursive `list_indication(6)`
  dump incl. `upper_list_text`/`upper_upper_list_text`, plus a `get_param_handle` sweep), timed
  against a naked-eye-only spot with the ASP-17 never slewed. `list_indication(1)`/PKV is now
  **ruled out** and should be dropped from that probe.
- Q1 (`LoGetWorldObjects` cost/filtering) is unchanged from the main findings: no native radius or
  coalition argument; Lua-side distance guard recommended.
