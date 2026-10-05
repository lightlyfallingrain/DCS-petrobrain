# Cross-cutting / unscoped backlog

Split out of `todo/todo.md` on 2026-09-27. **`todo/todo.md` remains the source of truth for User
priority tasks and session-scoped notes; this file holds the cross-cutting backlog — items that do
not yet belong to one subproject's roadmap.**

Same reason as `body-layer/BACKLOG.md`: both files are in the knowledge-graph corpus, whose semantic
extraction cache is keyed per file on content, so editing the priority section re-extracted 21
backlog items along with it and vice versa. These two sections change on different rhythms — the
priority list most sessions, the backlog when something is found and parked — which is exactly the
case where one file costs twice.

States are the same as `todo/todo.md`'s: `[ ]` open · `[~]` in progress · `[x]` done · `[?]` decision
needed · `[>]` deferred. Item ids are `X-B<n>` and are never reused or renumbered (root `CLAUDE.md`,
"Backlog Management").

Items here are `X-B<n>`. A new one takes the next unused number; numbers are never reused or
renumbered, `[x]` items included (root `CLAUDE.md`, "Backlog Management").

### Added 2026-09-26

- [ ] **X-B1 — Make an unhandled thread exception fail the test suite, not just warn it.**
  `pyproject.toml` declares no `filterwarnings`, so `PytestUnhandledThreadExceptionWarning`
  warns and the run still reports "178 passed". Raised by the reviewer on
  `feature/aircraft-layer-hardening`, twice, and it is worth doing because **that warning is
  the mechanism that caught the original bug** on that branch: a background thread died with
  an `AttributeError`, every assertion in the test still passed, and only the warning said
  otherwise. A dead daemon thread that leaves a green suite is exactly the failure this
  project keeps meeting in the air. Affects every subproject's test config, not one file —
  which is why it is here rather than on a branch.

- [ ] **X-B2 — `CollectorServer.open()` never resets `self._shutting_down` to `False`.** Latent, not
  live: `__main__.py` opens once and closes once at exit, and no test reuses an instance
  across a cycle, so nothing exercises it today. But if an instance is ever reopened it would
  **permanently swallow real `accept()` failures** — turning the loud-failure guard back into
  the silent death it was built to prevent. One line in `open()`. Flagged non-blocking by the
  reviewer on 2026-09-26; worth taking the next time that file is touched.

- [ ] **X-B3 — `test_unexpected_accept_error_is_logged_loudly_and_the_loop_recovers` simulates
  shutdown by poking `server._socket = None` rather than calling `close()`**, so it never
  sets `_shutting_down` and its simulated-shutdown branch now exercises a dead code path.
  Harmless today (the assertion is `any(...)`, not an exact count) and purely cosmetic drift —
  worth fixing only if that test is edited for another reason.

### Added 2026-09-25 (user)

- [x] **X-B4 — Probe whether DCS's own `land.isVisible` / `land.getIP` tests trees, and what a call costs.**
  **CLOSED 2026-10-01** (merge `306ae05`) — answered in full, including the tree half. Details below.
  User direction, 2026-09-25, arising from the vegetation-model decision recorded in
  `body-layer/ROADMAP.md` ("Detection under real world conditions", factor 1). **Gates the 9K113
  half of that decision and nothing else** — the statistical model for naked eye and binoculars
  does not depend on the answer, so this probe blocks one channel, not the work.

  **The question, precisely.** `Scripts/AI/Detection.lua` sets `trees_LOS_test_T4 = true` and every
  installed theatre is Terrain-4, so **ED's AI detection** samples tree geometry for line of sight.
  That is *not* the same claim as **the scripting API** doing so. Our own
  `query.line_of_sight.line_of_sight_clear` samples the bare terrain mesh, which makes us strictly
  more permissive through forest than the engine — so if `isVisible` does see trees, it closes a
  known gap for the one channel that can afford to call it.

  **Deliverables:**
  - Does `land.isVisible(from, to)` account for trees, or terrain only? A vehicle in dense forest,
    ray passing through canopy, is the discriminating case.
  - Does `land.getIP` return the blocking point, and is it more useful? It distinguishes "a ridge"
    from "the treeline 200 m short of the target", which the sight channel would want to *say*, not
    merely know.
  - Per-call cost, at realistic candidate counts.
  - Can a result return synchronously, or must it come back through a side channel? **This one was
    left open when the mission-bridge probe item was closed** — it was never the blocker there
    (velocity is a push), and it is the blocker here (LOS is a question).

  **The transport is not in question.** `net.dostring_in("scripting", …)` has been in production
  since 2026-09-13 (`petrobrain-f10-commands-hook.lua`, 1 Hz). This probe is about what the
  function answers and what it costs, not about reaching it.

  **Two weather questions ride the same bridge and should be probed in the same session** (user,
  2026-09-26, from the condition measurements):
  - **Can meteorological visibility be read?** It is a *ceiling* on detection for every instrument,
    not a per-optic multiplier — the user's own framing, and the measurements show it: in rain 2 the
    9K113 wide and narrow fields both detect at exactly 3.7 km despite very different magnification.
    `Export.lua` has no fog or weather getter (confirmed by reading the shipped file), so this
    bridge is the only candidate. `world.weather.getFogThickness()` is the named target. ED's own
    representation is a **time series** (`fog2.manual = {{time, visibility, thickness}, …}`), so
    whatever is built samples rather than reads once.
  - **Can *where* it rains be read?** *"Rain and clouds are not uniform in DCS. Moving will get you
    in and out of rain."* Whether any API exposes the spatial distribution is open, and it is the
    harder question: an ownship-local visibility figure is sampled in the right place but says
    nothing about whether the target sits under a squall. If nothing exposes it, the fallback is an
    ownship-local reading applied scene-wide, with the limitation stated rather than hidden.

  Investigator pass plus a probe on the Windows box. **Run it before the 9K113 slice is scoped, not
  during it** — if the answer is terrain-only, that slice's LOS design collapses and the
  statistical model has to cover every channel instead.

  **WIDENED 2026-09-29 (user), and the probe is now written and deployed.** User: *"we could also
  check if it is possible to get data for trees and buildings from DCS. That would be valuable for
  LOS, if we can get that data."* That is a second question alongside the original one, and the
  two have different answers in prospect:

  - **Test it per ray** — `land.isVisible` / `land.getIP`, DCS answering "can A see B" including
    whatever it counts as occluding. A query, not data.
  - **Extract it as data** — `world.searchObjects(Object.Category.SCENERY, …)` for buildings, into
    the world model as ordinary `StoredFeature` rows. Trees are almost certainly not scenery
    objects (terrain-baked), so for them the per-ray test is likely the only route.

  **Read from the install, 2026-09-29:** `Scripts/AI/Detection.lua`'s `visual_detection` sets
  `objects_LOS_test = true`, `trees_LOS_test = false`, `trees_LOS_test_T4 = true`, and every
  installed theatre is Terrain-4 — so **ED's AI** does test buildings and trees. That says nothing
  about the scripting API, which is native (nothing in `Scripts/` defines `land.isVisible`; only
  `ScriptingSystem.lua`'s `class(SceneryObject, Object)`), so it can only be measured live.

  `aircraft-layer/dcs-export/petrobrain-elevation-cost-probe-hook.lua` (deployed) answers all of
  it on the next sortie, with a **desert control** — the same 40-pair terrain-only-vs-`isVisible`
  comparison run over Mezzeh and over Deir ez-Zor, because terrain-sampling error appears in both
  and subtracts out while buildings and trees do not. A near-zero urban-minus-desert gap means
  `isVisible` is terrain-only and this item's 9K113 half collapses, which is why the control is
  there rather than assumed away.

  **If `isVisible` is cheap and does see objects, the prize is larger than this item assumed**: it
  could replace our elevation-grid LOS outright rather than supplement it, which would also make
  the SRTM-resolution question (X-B26) much less pressing. The probe times it at 1/50/200 rays per
  bridge call for exactly that reason.

  **ANSWERED 2026-09-29, six flights. `land.isVisible` is terrain-only — it does NOT test
  buildings or trees.** Forty rays fired deliberately through forty buildings whose positions came
  from `world.searchObjects` itself, 60 m either side at 2 m AGL: **0 blocked, 40 clear**. The
  controlled sweep agrees, 0/40 in both the ownship area and the desert control. Full results:
  `aircraft-layer/research/2026-09-29-bridge-terrain-probe-results.md` Findings 12-14.

  This reconciles with `Detection.lua` rather than contradicting it: `objects_LOS_test` and
  `trees_LOS_test_T4` govern **ED's AI detection**, a different code path from the scripting API.

  **So the hope above is dead** — `isVisible` sees exactly the bare terrain mesh we already see,
  and routing occlusion through it would buy a bridge call and nothing else. X-B26 is not relieved.

  **What it opens instead, and this is the better outcome:** we now have the raw material to do
  occlusion *better* than DCS's own scripting API offers. `world.searchObjects` returns 590 objects
  in a 600 m radius with positions and type names (denser and more authoritative than OSM
  footprints), and world-model already holds 44,811 OSM landcover polygons for trees. The missing
  piece is **extent** — scenery carries no dimensions (`getDesc` is
  `life/_origin/category/typeName/displayName`, and `life` is hit points), so a type-name → size
  table built once offline over a finite catalogue is what stands between here and a real occluder
  layer. **That is a new workstream, not a tweak** — file it before starting it.

  Costs settled across three flights: `getHeight` 0.8-1.1 us/point (a full 2,601-point M8 chunk is
  2.0 ms), `isVisible` 10.6 us/ray. Scenery search is superlinear and is the one to watch: 126
  objects at 300 m costs 1 ms, 590 at 600 m costs **18 ms** — keep it at or below 300 m.

  **FULLY CLOSED 2026-09-29 after ten flights — and the answer turned positive on a different
  call.** The user asked whether *any* DCS call accounts for buildings and trees. Dumping the live
  API surface (rather than answering from memory or the wiki) named
  `world.VolumeType.SEGMENT`, and it works:

  - **A SEGMENT volume search returns the buildings the sightline passes through**, with an
    open-ground control returning zero — so it intersects rather than merely proximity-matches.
  - **It is a true 3D test**: 6 hits at 2 m AGL, **0 at 15 m and above**, and 2 on a realistic
    200 m-to-2 m slant. Flying *over* a town is not blocked; looking *down through* it is.
  - **8.7 us per sightline** — *cheaper* than `land.isVisible`'s 10.6 us, which sees only terrain.
    200 candidates with full building occlusion cost 1.9 ms, ~1% duty at 5 Hz.
  - **No type-name → size table needed** — DCS does the intersection.

  So `land.isVisible` is a dead end (terrain-only *and* dearer), and **trees have no DCS route at
  all** — they are not scenery objects, so no volume search will ever find them. OSM landcover is
  not a fallback for trees, it is the only source. Full results:
  `aircraft-layer/research/2026-09-29-bridge-terrain-probe-results.md` Findings 15-21.

  What remains is build work, not research — see `X-B31` (renumbered from X-B28 at merge:
  the Mac had independently filed X-B28 the same day, and ids are never reused).

- [ ] **X-B31 — Build the occluder layer: buildings from DCS, trees from OSM.** Falls out of X-B4,
  2026-09-29, and is build work with the research already done rather than a question.

  Today `query/line_of_sight.py` samples bare terrain and nothing else, so Petrovich sees through
  towns and forests. Three sources are now in hand and each has a measured cost:

  | occluder | source | cost |
  |---|---|---|
  | terrain | today's elevation grid, or `land.profile` (one call vs 20+ `getHeight`) | 0.9 us/point |
  | buildings | `world.searchObjects` + `VolumeType.SEGMENT`, true 3D, no size table | 8.7 us/sightline |
  | trees | OSM `landcover` polygons — world-model already holds 44,811 | already local |

  **The architectural question this raises, and it is not small:** buildings are only reachable
  from the *Windows* box through the mission-scripting bridge, while `line_of_sight_clear` runs
  in-process on the Mac inside body-layer's 5 Hz perception loop. A per-candidate LOS check would
  have to cross the LAN. That collides with X-B27's topology decision and with
  `plans/pb1-perception-logger/plan.md` decision 3 ("same box always"). **Resolve the topology
  before designing the call**, not after — the measured 8.7 us is a loopback figure and says
  nothing about a LAN round trip per candidate per poll.

  Cheapest first slice, if one is wanted before the topology moves: **trees only**, entirely
  Mac-side, since the OSM polygons are already in the store and need no bridge at all. That would
  close the forest half of the missed-AAA class of defect without touching the seam.

  **Do not start before `X-B26`'s SRTM-resolution question is settled** — both change
  `line_of_sight_clear`, and doing them in either order separately means touching it twice.

  **The "trees from OSM" row is settled rather than assumed, as of 2026-10-01** (merge `306ae05`).
  It was the fallback pending an answer; it is now the measured answer. **No DCS call gives
  tree-aware line of sight** — `isVisible`, `getIP`, `searchObjects` at any volume and
  `getSurfaceType` are all terrain/scenery only, tested against vehicles the pilot placed inside
  canopy. The engine has the capability but it is compiled and Petrovich's own verdict is an audio
  file. DCS's per-tree placement does exist on disk, and is deferred behind the `.surface5`
  payload-addressing wall (`X-B32`). Full reasoning:
  `aircraft-layer/research/2026-09-29-tree-los-probe-results.md`.

- [x] **X-B5 — Run Reviewer, Performance Reviewer and Security on this repo's Claude configuration
  itself.** Done 2026-09-27. All three roles ran in worktrees, advisory-only as this item required;
  reports at `reviews/claude-setup-{review,performance,security}.md`. All HIGH/MEDIUM findings fixed
  with the user in the loop in `d1c5724`.

  **What the audit actually found, beyond the seed list below** (most of which had self-corrected by
  the time it ran — the mirror contradiction, the "Current Focus" dead reference, `dod-check`'s
  hardcoded list and the `AGENTS.md` role count were all already fixed):
  - Two mechanisms injecting text into *every turn* had drifted from `CLAUDE.md`, each toward
    skipping a step it requires: the `UserPromptSubmit` reminder omitted Security entirely and
    asserted an exemption revoked on 2026-09-24, and `session-start.sh` still taught the
    todo.md-derived milestone protocol with no ROADMAP.md and no branch/worktree state check.
  - **`commit-quality-gate.sh` could not pass at all.** It invoked bare `ruff`/`mypy`/`pytest`, none
    of which are on `PATH` (each subproject has its own `.venv`), so every check exited 127 and the
    gate blocked any commit touching subproject code. Invisible for as long as commits touched only
    `.claude/`, `docs/` and `todo/`. It also ran mypy from the repo root, where config discovery is
    CWD-only — `body-layer` reports 6 phantom import errors from there and none from inside.
  - The deny list was defeated by ordinary flag rewrites (`rm -fr`, `git worktree remove -f`,
    `git -C <dir> reset --hard`), the last of these demonstrated destroying an uncommitted change.
    Replaced by argv-aware parsing in `destructive-command-gate.sh`.
  - The hardcoded-three-of-six defect recurred in three more places (`posttooluse-mypy.sh`,
    `push-roadmap-gate.sh`, root `CLAUDE.md`'s Subprojects section) — all now discovery-based.

  **Two lessons worth more than the fixes**, both about how the audit itself went wrong:
  - *A rule whose trigger is unobservable stays broken, and so does a script nobody executes.* The
    performance pass read `commit-quality-gate.sh`, called it "correctly scoped", and never ran it;
    one synthetic payload would have shown the 127s. For a hook, running it with a fake input is the
    first step, not the last.
  - *File counts do not predict cost for an incrementally-cached tool.* The same pass estimated
    whole-subproject mypy at 3–8s per edit from file counts and recommended narrowing the check.
    Measured with the real venv it is **110ms** warm — and a single file is also 110ms. The
    recommendation was dropped rather than applied, and the estimate would have bought a real loss of
    coverage for nothing.

  **Left open, deliberately** (all low-priority; see the reports for detail): `body-layer/CLAUDE.md`
  at ~24K tokens is the largest fixed-context item in the setup and wants a content pass by whoever
  owns it; the `UserPromptSubmit` reminder has no session-marker gate, so it re-injects ~170 tokens
  every turn; agent-dispatch overhead (~20–40K tokens × 5–6 per feature) is structural to
  worktree isolation and was sized for visibility, not for cutting.

  Original framing follows.

  The config is treated as prose nobody reviews, while it is
  in fact the thing that decides how every agent behaves — and a defect in it is executed rather
  than read.

  Scope: `CLAUDE.md` (root and every subproject's), `AGENTS.md`, `docs/AGENT_ROLES.md`,
  `docs/PROCESS.md`, `.claude/agents/*.md`, `.claude/skills/*/SKILL.md`, `.claude/settings.json`
  hooks and its deny list, `.claude/scripts/`. Each role reads it as its own kind of artifact:
  **Reviewer** for contradiction between files and instructions that cannot be followed as written;
  **Performance Reviewer** for what the configuration costs per session and per agent — context
  loaded on every turn, hook latency on every tool call, agents spawned where one would do;
  **Security** for the hooks and scripts as executable surface, the deny list's actual coverage, and
  what an agent is permitted to do without asking.

  **Seed material already found, 2026-09-25, not yet acted on** — the skill-file sweep (`a5fd5ef`)
  surfaced these in files it was told not to edit:
  - Root `CLAUDE.md` hardcodes three subprojects in four separate sections (Current priority,
    Subprojects, Milestone Completion, Verification). There are six — `git ls-files '*/pyproject.toml'`.
    `brain-layer` has shipped code and is named in none of them. The same class of defect made
    `/check`, `/compile`, `/test` and `/dod-check` capable of reporting PASS while never looking at
    half the repo.
  - **A live contradiction**: root `CLAUDE.md`'s "Knowledge graph" says the graph is built from the
    `graphify-corpus/` mirror; `.claude/skills/graph-refresh/SKILL.md` says that mirror was removed
    because it broke cache lookups and leaked `graphify_corpus_*` into the graph's vocabulary, and
    that it must not be reintroduced. One of the two is wrong and the skill is the newer.
  - Root `CLAUDE.md`'s "Subprojects" sends readers to `todo/todo.md` "Current Focus" for BL-x
    status, which the same file's "Current priority" section says no longer holds milestone
    narrative. There is no "Current Focus" heading in this file.
  - Root `CLAUDE.md`'s "Agents" asserts a role count and that all roles use one model, immediately
    followed by its own dated exception — the shape that goes stale silently.
  - `AGENTS.md`'s "Roles (one-liners)" lists seven and omits `investigator`, which root `CLAUDE.md`
    describes at length. Its "Recommended Role Sequences" still points at a possible exemption of
    security/performance-reviewer that `CLAUDE.md` replaced on 2026-09-24 with a cadence.
  - `AGENTS.md`'s rule 2 still says "trial this before relying on it" inside a section headed
    "Status: all three rules in force".

  Note the precedent this sits on: the skill sweep was worth running because three of its findings
  were *already wrong at the time of the audit*, not merely aging. The same is likely here, and the
  blast radius is larger — `CLAUDE.md` is loaded into every session, so a wrong line there is
  believed by every agent from its first turn. Do not let the roles edit the config themselves;
  `integrity-audit` is deliberately diagnostic-only and this should keep that posture — report,
  then apply with the user in the loop.

- [ ] **X-B6 — An outpost fragments into 18 contacts at range — diagnosed, not fixed.** Found in a real
  sortie 2026-09-25 from `--belief-truth-log`; full analysis in
  `plans/contact-fragmentation-at-range/debug.md`. The user heard the same callout four times
  (*"ground, 11 o'clock, 1 kilometre."*) and asked why they did not collapse into a group.

  **It is not clustering** — the contacts were founded across ten different polls, so per-poll
  clustering never saw them together. It is association over time, and it is a **recurrence of
  `plans/contact-duplication-ambiguity-runaway/`'s runaway with a new trigger**.

  The counter-intuitive part, and the reason it took a log to see: the association gate is not too
  *tight* at range, it is too **loose**. `naked_eye_sigma_m` scales with range, so at 4 km the
  3-sigma gate accepts a 2.9 km down-range discrepancy. In a dense outpost several existing
  contacts therefore pass, `ingest`'s deliberate anti-guessing rule reads "2+ candidates" as
  ambiguous and founds a *new* contact, and that new contact makes the next look ambiguous against
  one more candidate. Object-permanence continuity is the existing protection and still correct,
  but it needs stable cluster membership, which a sweeping gaze, a marginal gate and
  `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL = 3` all churn.

  Four directions are listed in the debug note, none chosen — the anti-guessing rule is
  load-bearing and this needs a decision rather than a patch. Note also that contacts drift between
  real objects over a sortie, so any fix validated against the belief-truth join must account for
  the join re-resolving, or it measures itself.


- [x] **X-B7 — A real-time ASCII view of what Petrovich is looking at, and with what. Built 2026-09-25 (`feature/eyesight-view`) — `--eyesight-view`, plus `--belief-truth-log` below.** User, 2026-09-25:
  *"it'd help if I could visually see where Petrovich is looking and with what. A realtime ascii
  graphic would do just fine."* Shape, as he described it:
  - **Ownship at bottom centre**, because the rear hemisphere is not visible anyway — so the
    drawing is a forward arc, not a full circle.
  - **A cone or line drawn where he is looking**, coloured by optic: **green = naked eye, blue =
    binocular**.
  - **A one- or two-letter id per contact**: `AA` air defence, `AR` armour, `TR` truck, `G` group,
    `U` unknown.

  **What already exists, so this is not built from nothing** — and checking this first is the
  point of writing it down here:
  - `perception.gaze.gaze_at(t_sim, plan)` is **pure**, so the current gaze is a read, not new
    state. The cones 2C sortie already added an overlay *line* naming the gaze o'clock
    (`logger._push_gaze_line`) for exactly this need — the user's own words then were *"very
    difficult to judge when I don't visually see where Petrovich is looking"*. This item is the
    spatial version of that same complaint.
  - `--detection-trace` (BL-9) already records, per poll and per candidate, which visibility gate
    decided its fate, at what true range and bearing, plus the optic and the contact it folded
    into. `body-layer/tools/summarize_detection_trace.py` reduces it after a flight. **The data
    this view needs is already being written** — what is missing is a live rendering of it.
  - `perception.optics` carries the optic in use, so green/blue needs no new state either.

  So the likely shape is a reader, not a new subsystem: a terminal view fed from the same per-poll
  state the trace writer already sees. Worth confirming that read before designing anything.

  **Settled by the user, 2026-09-25: this is a debug, testing and calibration tool, and it may show
  ground truth.** His words: *"it's a debug and testing tool. Can break no-omniscience boundary
  because the whole purpose is testing, debugging and calibration."* So it draws what is really
  there alongside what Petrovich believes — that contrast *is* the instrument. A view restricted to
  belief could not answer the question it exists to answer, which is why he could not see something
  he should have.

  **The invariant that still applies, and it is a different one: the view must be read-only and
  one-directional.** No-omniscience constrains what *Petrovich* knows, not what the developer sees
  — but nothing this view reads may flow back into belief. `detection_trace_writer.py` is the
  precedent and the model: it is deliberately allowed to hold ground truth and belief at once, and
  it never calls anything that mutates `ContactStore`, and no ground-truth field it touches is ever
  passed into `ingest`/`Percept`/`Contact`. Build this the same way, and say so in its module
  docstring, because the next reader will otherwise assume the boundary was simply forgotten.

  Worth noting the same tension was already resolved this way once: `--detection-trace` holds both
  and is trusted precisely because the direction of flow is enforced structurally rather than by
  remembering.

- [ ] **X-B8 — Per-module performance review, findings written to a document, and that document becomes a
  backlog item.** User, 2026-09-25. Each subproject reviewed in its own right —
  `world-model/`, `aircraft-layer/`, `body-layer/`, `audio-adapter/`, `brain-layer/`,
  `mission-interpreter/` — rather than only the per-feature passes that have run since
  2026-09-24. Those per-feature passes found real things (LOS sampled before the range gate; a
  wedged-brain poll costing 5015 ms every cycle), but they only ever look at what one branch
  touched.

- [ ] **X-B9 — Per-module security review, same shape: findings to a document, document becomes a backlog
  item.** User, 2026-09-25. Same reasoning and same module list. Note the standing scoping the
  user set when re-enabling the role: single-user, LAN-only, under active development — so this is
  a survey for real exposure, not a hardening audit. The per-feature pass has already found one
  genuine item this way (a service binding all interfaces for no benefit), which is the argument
  for doing it systematically.

- [ ] **X-B10 — End-to-end latency measurement: where the time actually goes, and what would buy the most.**
  User, 2026-09-25: *"what are the latencies what are the bottle necks, what would bring greatest
  improvements?"* The whole chain, not one hop — PTT to recognised transcript, transcript to
  dispatched command, perception poll to spoken callout, escalation to brain reply. **This has
  never been measured end to end**; what exists is scattered and single-hop (whisper's own bench,
  the brain-layer model measurements, `describe_position`'s p99, the 5 Hz poll budget).

  The deliverable the user asked for is specifically the *ranking* — not a table of numbers but
  which single change would buy the most. Worth stating because a measurement pass that produces
  only numbers answers a different question than the one asked.

- [ ] **X-B11 — The knowledge graph was rebuilt under the OLD graphify node-ID format — the next rebuild
  needs `graphify extract --force`.** Added 2026-09-24, and this will fail silently if missed.
  The `/graph-refresh` on 2026-09-24 (3287 nodes, 5829 edges) used the extraction spec's
  *immediate-parent* ID format (`auth_session_validatetoken`). The installed skill's
  `references/extraction-spec.md` changed during that same session to a **full-repo-relative-path**
  format (`src_auth_session_validatetoken`), explicitly to keep same-named files in different
  directories distinct. The two formats produce different IDs for the same symbol, so the next
  incremental extraction will create **orphan ghost-duplicate nodes** alongside the existing ones
  rather than updating them — the spec names this outcome itself and prescribes
  `graphify extract --force` to rebuild cleanly. Nothing warns about it; the graph just quietly
  grows two of everything it touches. Do the forced rebuild *before* trusting any query after the
  next doc change.

  Also noticed then: the installed graphify skill is 0.8.41 against package 0.9.64
  (`graphify install --platform claude` updates it). Probably the same root cause as the spec
  change — worth updating in the same pass.


- [~] **X-B12 — Re-enable the performance-reviewer and security roles, and run a catch-up audit of what
  shipped while they were exempt.** *(Was `[>]` deferred until Stage 4b of the group contact model;
  first half is done, second half is partial — state corrected 2026-09-27.)*

  **The roles were re-enabled on 2026-09-24** and root `CLAUDE.md`'s "Agents" section has said so
  since: *"performance-reviewer and security run once per whole feature, immediately before DoD"*,
  replacing the blanket skip. This item nevertheless still read as deferred three days later, and it
  was found by a knowledge-graph extraction pass noticing that a deferred backlog item and a
  completed one described the same thing — which is the first time on this project that the graph
  caught a staleness nobody was looking for. Worth recording as evidence for the graph's own value,
  next to the fact that the graph had gone unqueried for a day.

  **Catch-up audit, actual state:** aircraft-layer (2026-09-26, `research/2026-09-26-performance-
  review.md` + `-security-review.md`) and audio-adapter (2026-09-26, `docs/reviews/`) have both had
  whole-subproject passes. Per-feature passes exist for brain-layer, watch-reporting and
  position-belief-runaway under `plans/*/`. **Still unaudited as whole subprojects: world-model,
  body-layer, brain-layer, mission-interpreter** — body-layer is the notable gap, being the largest
  and the one holding the belief state. That remainder is what [[X-B8]] and [[X-B9]] (per-module
  performance and security reviews, findings to a document) actually cover, so this item should
  close into those two rather than tracking the same work a third time.

  Original deferral rationale (user, 2026-09-19) — not because the finding is weak, but because interrupting the current run
  to re-audit would cost more than the risk carries today.

  **Both exempted roles independently reported their own exemption has gone stale**
  (`/retro`, 2026-09-18). `CLAUDE.md` says: *"Skip performance-reviewer and security for now — this
  phase is an offline single-user local pipeline with no hot path and no untrusted-input surface
  yet."* That was written for the World Model Builder's offline phase. It no longer describes where
  the work happens.

  **Performance reviewer's case:** this week's changes landed in `aircraft-layer` and `body-layer`,
  which are live runtime paths, not the offline pipeline the exemption describes. Two specific
  candidates: `AudioPlaybackSender`'s worker thread and queue, which carries an explicit
  interrupt-*timing* correctness requirement, and `perception.clustering`'s O(n²) single-link pass
  running **every poll**. Its recommendation is to narrow the exemption's scope to `world-model/`
  explicitly, so runtime subprojects stop being swept under a phase description they have left.

  **Security's case, which contradicts a judgement already recorded elsewhere:** `POST /audio/play`
  was merged with the framing *"same severity class as what already exists, not a new category"*
  (`plans/tts-voice-output/plan.md` Decision 6, relayed to the user as settled). Security disagrees,
  and the disagreement is about the right axis: the existing unauthenticated endpoints push overlay
  text and trigger in-sim commands, with effects confined to the **DCS process**. Audio playback
  reaches the **host OS** — arbitrary content from any LAN device reaching the user's speakers — and
  audio-play primitives have a history of path/codec-confusion and resource-exhaustion issues that
  text overlays do not. Its reading is that this crosses the exemption's own stated line, *"no
  untrusted-input surface yet"*, because the LAN is now an input surface. The earlier framing
  reasoned about authentication being unchanged; severity is determined by blast radius, which
  changed.

  **When picked up:** narrow or lift the `CLAUDE.md` exemption, restore both roles to the sequences
  in `AGENTS.md`, and run a Mode-2 deep analysis on `POST /audio/play` plus a performance pass on
  the two candidates above. Note the exemption is a *phase* decision — the lesson worth carrying is
  that it needed a re-scope trigger and had none, which is the same failure shape the retro found
  in four roles' memory files.


- [ ] **X-B13 — `console.py`'s typed `scan-area` still drives the 9K113.** Found by review 2026-09-17,
  while checking the F10-path fix (`89b8b1d`). `body-layer/src/belief/console.py:548` calls
  `aircraft_client.trigger_petrovich_search("forward")` under the name "Scan" — the identical
  semantic mismatch just removed from `crew_console._handle_scan`, where *Scan* is naked-eye
  perception and *Observ* is the 9K113 (`docs/concept/state-transitions.jpg`'s glossary).

  Left out of `89b8b1d` deliberately: it is pre-existing, `--console`-only (a developer debug
  tool), and no crew or F10 path reaches it, so folding it in would have expanded a reviewed
  commit's scope for no in-flight benefit. But it is not merely mechanical either — `scan-area`
  is the *typed* command that takes explicit geometry, so "what should it trigger instead" has a
  real answer to pick: nothing at all (matching the F10 path), or a future `Observ` once that
  verb exists. Decide that when `console.py` is next touched, rather than copying the F10 fix
  blindly.

  Until then the repo contains two paths named "scan" that do different things, which is exactly
  the kind of contradictory precedent a future reader would follow in the wrong direction.


- [x] **X-B14 — Scan commands should drive naked-eye perception.** Raised 2026-09-16 from the first live
  F10 test of `f10-command-vocabulary`; narrowed 2026-09-17 once `cockpit-visibility` shipped.
  **Closed 2026-09-21 by cones slice 2B** (`plans/detection-cones-slice2/plan.md`): a pending
  `scan_area` task's relative sector now resolves to a `perception.gaze.Gaze` each poll
  (`logger.py`'s `_active_gaze`/`_apply_active_gaze`) and filters `NakedEyePerceptionSource`'s
  candidates via a new gate ahead of the cockpit mask, so "scan left" now changes which contacts
  Petrovich can detect, not just which he is attending to. The "full version" (dwell time,
  naked-eye-vs-binocular tier varying with time-looking) below is 2C/2D's job, not this one's.

  **A scan changes attention, not perception.** `perception/visibility.py`'s naked-eye gate uses a
  fixed cockpit occlusion mask (`perception.cockpit_mask`, `plans/cockpit-visibility/plan.md`) that
  no command steers, so "scan left" registers an `AttentionArea` and a `PendingIntent` but does not
  change which contacts are detected. It raises attention on things the fixed mask already found.
  The 9K113 trigger removed on 2026-09-16 (`fix/scan-naked-eye-not-9k113`) was the only observable
  effect a scan had, and it was the wrong organ — so scan is now honest but perceptually inert
  until this is built.

  The mask's own mis-sourcing is now fixed — `NAKED_EYE_FOV_HALF_WIDTH_DEG` (the 9K113's angular
  limit, not a human-through-glass figure) is gone, replaced by a body-relative
  depression-per-azimuth mask derived from real co-pilot cockpit screenshots
  (`plans/cockpit-visibility/plan.md` D7 — still uncalibrated, ±10-15° at best, same debt class as
  `visibility.py`'s own tier constants, but at least sourced from the right thing now).

  What the full version looks like, per the spec diagram: a steered *sub-window* within that mask
  that follows the commanded sector for the task's duration, plus the diagram's default-state sweep
  (`ahead → left → ahead → right`), dwell time per sector, and naked-eye vs binocular tier varying
  with how long Petrovich has been looking somewhere. That needs a dwell/attention scheduler that
  does not exist. Composes with, not duplicates, the static mask (`plans/cockpit-visibility/plan.md`
  D4): the mask is what the airframe permits him to see at all, always applies; scan steering is
  where he is currently looking within that, dynamic. Effective visibility is the intersection.

  Deliberately deferred by user direction 2026-09-16 ("write entry in backlog for full pattern
  simulation, but for now simply remove 9K113 trigger").

  **Compass/absolute scans still never reach `_active_gaze` — measured again 2026-09-23 while
  scoping `plans/voice-command-completeness/plan.md`.** `_active_gaze` only ever converts a
  `scan_area` task's `relative_sector` field into a `perception.gaze.Gaze` (cones slice 2B, above);
  a compass scan sets `area.sector` instead, so `scan north`/the quantised `scan_bearing_deg`
  fall through to `FREE_SCAN_PLAN` exactly as before that slice landed. A pilot who hears
  `"Scanning northwest."` and gets free-scan behaviour reads it as broken. Named explicitly, not
  silently reopened, by `voice-command-completeness`'s own Decision 5/Risks section, and deferred
  to that plan's Stage 5 alongside the item below (both land together: the clean fix is
  `_active_gaze` converting an absolute `area.sector` into relative o'clock legs per tick using
  current heading, the same generalisation the o'clock-scan item needs anyway).

  **Closed by Stage 5** (`plans/voice-command-completeness/plan.md`, `logger._active_gaze`):
  a `sector`-only task now also resolves, converted to `ScanPlan.commanded_legs` every poll via
  the new `perception.gaze.legs_within_wedge`, using that poll's own ownship heading — `scan north`
  now steers `NakedEyePerceptionSource`, not just an `AttentionArea`. **Unflown as of merge.**

- [x] **X-B15 — Ownship-relative o'clock scan tokens — deferred to Stage 5 of `plans/
  voice-command-completeness/plan.md`, user direction 2026-09-23.** The command vocabulary has two
  frames and only one has fine granularity: absolute (`north`/`315 degrees`, coarse and fine both)
  vs. ownship-relative (`left`/`right`/`ahead`/`full`, coarse only — `left` spans a 90° wedge, three
  o'clock hours). *"'scan 1 o'clock' directs scan at a narrow sector that is own ship relative.
  That is needed"* (user). Nine new tokens (`scan_clock_1..12`, matching the report family's own
  nine forward hours), **unbenched** — no recordings exist for them, same cost that kept
  `cancel_scan`/`cancel_watch` off voice until 2026-09-23; cheapest when the corpus is next
  re-recorded. The real cost is geometry, not vocabulary: a single o'clock hour is not expressible
  as a `RelativeSector` today (`perception.gaze._SECTOR_LEGS` only has `ahead`/`left`/`right`/
  `full`), so the clean generalisation is `ScanPlan` carrying legs directly (an o'clock command is a
  one-leg plan, exactly like `ahead` already is) rather than widening the `RelativeSector` literal
  and rippling through `_RELATIVE_SECTOR_WEDGE_DEG`/`belief.attention`'s re-export/the label
  tables — the same generalisation that would also fix the compass-scan-gaze gap immediately above,
  which is why the two items are sequenced to land in the same stage.

  **Closed by Stage 5**: `scan_clock_1..12` dispatch through `CrewConsole._handle_scan`'s new
  `relative_clock_hour` parameter, registering a one-leg `ScanPlan.commanded_legs`; the nine
  tokens are unbenched, as flagged above — next corpus recording's job. **Unflown as of merge.**


- [ ] **X-B16 — Stage 5 road junctions: pathological single-chunk stalls — CONFIRMED DATA-DEPENDENT.** Raised
  2026-09-16 from the `syria-full` build log validating `osm-landcover-optimization`. Stage 5 took
  2885 s, and a large share of that sat in a handful of chunks: chunk 13867→13868 took 331 s and
  chunk 14017→14018 took 337 s (one chunk each), with two further ~330-350 s near-stalls around
  them — roughly 28 of the 48 minutes in a few chunks. This is exactly the gap `b260ee7`
  (road-junction progress logging) named as remaining: *"nothing is logged during a single slow
  chunk."* Confirmed in the wild, plus a second symptom — the ETA swings badly during a stall
  (495 s → 1657 s remaining), so the estimate actively misleads. Two separable pieces of work:
  (a) log progress *within* a chunk, or at least emit a "chunk N still running, Xs elapsed"
  heartbeat so a stall is distinguishable from a hang; (b) find out why those specific chunks are
  so expensive (dense urban road clusters? a union-find degenerate case?) — the fix may be a
  chunk-splitting heuristic rather than better logging. Not scoped to a milestone; `world-model`.

  **Update 2026-09-16 — reproduced on a second machine, at the identical chunk indices.** A Mac
  `syria-full` build hit exactly the same four chunks (13867, 13868, 14017, 14018) that stalled on
  Windows, at ~170 s each versus Windows' ~330 s. Same indices, different OS and different CPU, so
  this is a property of the *data in those chunks*, not of the machine — which makes (b) tractable:
  those four chunk bounding boxes can be extracted and profiled directly rather than hunted for.
  They cost ~680 s of the Mac run's 1,038 s total, so fixing them is most of Stage 5's wall-clock.
  Stage 5 overall was much faster on the Mac (1,038 s vs 2,885 s), as were roadnet (444 s vs 670 s)
  and SRTM (4.4 s vs 11.3 s).

  Unrelated caveat when reading `world-model/syria-full-build.log`: it contains a 2.5-hour wall-clock
  gap mid-Stage-5 that is **not** a stall. The host slept. The progress lines' own `elapsed` counter
  advanced only 201 s across it, because `ingest_junctions`/`roadnet.routes` both use
  `time.monotonic()`, which on macOS does not tick during system sleep. Wall-clock timestamps and
  logged elapsed disagree by design there.

- [ ] **X-B17 — `syria-full` pipeline logs only 6 of 8 stages.** Raised 2026-09-16 from the same build log.
  Output goes `[6/8] SRTM elevation grid: done` straight to `Built ...` — `[7/8]` and `[8/8]` never
  appear. `probe: skipped (probe_output_path not given or not found)` accounts for at most one of
  them. Either the remaining stages are silent (no `starting`/`done` lines, unlike stages 1-6) or
  `_TOTAL_STAGES` overcounts. Cosmetic but misleading during a ~1 h build. `world-model`.

- [ ] **X-B18 — SRTM: 131 tiles staged, `tiles_used=79`; 7.4% of points void-or-uncovered.** Raised
  2026-09-16 from the same build log. The pipeline header reports `SRTM elevation grid (131
  tile(s))` but `SrtmIngestStats` reports `tiles_used=79` — 52 staged tiles contributed nothing.
  Separately `points_void_or_uncovered=47484` of `points_expected=639216` (7.4%). The M7 entry
  already records 92.6% coverage as an accepted result, so this is likely the known gap rather
  than a regression, but the 131-vs-79 discrepancy is unexplained and worth one look: if the 52
  unused tiles are outside the region bbox that is fine and the header should say so; if they
  overlap it, coverage is being lost. `world-model`.

- [ ] **X-B19 — Pin `CLASSIFIER_VERSION` bump discipline with a test.** Raised 2026-09-16. The comment
  above `CLASSIFIER_VERSION` (`world-model/src/build/ingest_osm.py`) lists the conditions that
  force a bump; `638239a` met two of them and landed without one, and was caught only by reading a
  build log weeks later. Nothing mechanically enforces the rule. Options: hash the relevant
  functions'/dataclass' source and assert the digest matches a pinned value alongside the version
  (fails loudly on any edit, forcing a conscious bump), or derive the cache key from such a digest
  instead of a hand-maintained integer. The second is the real fix but changes the invalidation
  key's shape. `world-model`.


- [ ] **X-B20 — Landmark references must be LOS- and knowledge-gated, not ground-truth.** Raised
  2026-09-13, while scoping world-model tactical-landmark enrichment (ridges/valleys,
  settlements, road intersections, other aerial landmarks — see
  `plans/world-model-tactical-landmarks/plan.md` once it lands). World-model can compute
  "this unit is 500m from a road intersection, south of a large building," but per this
  project's no-omniscience invariant, Petrovich/the brain must never speak a landmark
  reference the crew has no actual basis for knowing. Two independent gates, both needed:
  1. **Line-of-sight**: can we (or Petrovich) actually see the landmark itself right now, using
     the generalized A↔B LOS primitive (`plans/world-model-los-generalization/plan.md`,
     `query.line_of_sight.line_of_sight_clear`) applied ownship/Petrovich → landmark position,
     not just ownship → contact.
  2. **Knowledge**: do we have a standing memory of that landmark (a prior perception/
     observation of it — this is squarely BL-8's future territory), or does the Mission
     Understanding / briefing (Mission Interpreter's schema, `plans/mission-interpreter/
     plan.md`) name it explicitly? If neither, the landmark is not known and must not be
     referenced, even if world-model's query layer can compute its existence and position from
     ground truth.
  **Not scoped to a milestone yet** — spans world-model (landmark data + LOS query),
  mission-interpreter (briefing-named landmarks as a knowledge source), and body-layer
  (the actual gating logic before a landmark reference reaches speech output, likely a
  `belief/` concern parallel to `percept.py`'s existing DCS-truth-stripping boundary). Revisit
  once world-model's landmark enrichment and a first Mission Understanding schema both exist.

- [>] **X-B21 — "Wingman brain" — a much later, far-future direction.** Raised 2026-09-13, deliberately
  deferred, not scoped. Combines observation + flight control + world perception from a
  *non-player-position* aircraft — i.e. an AI-controlled wingman with its own Petrobrain-style
  cognition, not just Petrovich riding along in the player's own cockpit. A materially different
  architecture from everything built so far: today's aircraft-layer/body-layer split assumes
  perception is anchored to the player's own ownship telemetry throughout (`OwnshipState`,
  `perception/geometry.py`'s bearing/range math, `aircraft_client`'s `/telemetry/latest`). A
  wingman brain would need perception/state for an aircraft that isn't the player's — a new
  telemetry source, not a reuse of the existing one. Do not start scoping this until the current
  three-layer architecture (world model, mission interpreter, body/brain layer) is mature and
  proven for the single-player-aircraft case first.

- [x] **X-B22 — CLOSED 2026-09-27: not regressions, an unmerged branch.** Both tests were committed to
  `main` **already red**, by `e40e9da` — the sortie diagnosis, explicitly diagnosis-only: *"reproduced
  in a new failing test."* They are reproduction tests. The fix had been finished on
  `fix/sortie-2026-09-26` for a day — Reviewer, Security (APPROVED), Performance (APPROVED), **DoD
  PASSED** — and was never merged. Merged as `2ac8e61`; `body-layer` now 1303 passed / 0 failed.

  **Two things worth keeping from how this was found.** `git log -S` on the two test names answered it
  in one command — which is what this item's own last paragraph said to do first, and doing it before
  dispatching a debugger saved a diagnosis of a defect that did not exist. And the audit that filed
  this item got its framing wrong in a specific, instructive way: it said "treat these as possible
  real regressions with pilot-visible consequences". The consequences are pilot-visible, but a red
  test does not imply broken code — it can equally mean *finished work that never landed*. A test
  suite's colour is evidence about the tree, not about the codebase's history.

  The other half of the finding stands and was the real cost: because `commit-quality-gate.sh` had
  been exiting 127 on every check, nothing had run these at commit time, so a completed, fully-gated
  branch sat unmerged with nothing announcing it. The gate's repair is what surfaced it at all.

  Original text follows.

  **Two failing body-layer tests on `main`, exposed 2026-09-27 when the commit quality
  gate was repaired.** Found by X-B5's fixes, not by X-B5's review — the gate had been exiting 127 on
  every check, so nothing had actually run these at commit time:

  ```
  tests/test_contacts.py::test_range_crossing_does_not_fire_for_a_contact_behind_the_cockpit_mask
  tests/test_optic_policy.py::test_a_command_interrupted_look_is_not_permanently_burned
  ```

  `cd body-layer && ./.venv/bin/pytest tests -q` → 2 failed, 1292 passed, 4 xfailed in 11.03s.

  Not investigated — X-B5 was scoped to configuration, not code, so these were reported and left
  rather than fixed on a config commit. Both test names describe *belief-state behaviour the pilot
  would notice*: a crossing callout firing for a contact behind the cockpit mask is Petrovich
  reporting something he cannot see (the no-omniscience invariant), and a burned interrupted look is
  an optic that never recovers. So treat these as possible real regressions with pilot-visible
  consequences, not as stale tests, until the diagnosis says otherwise. Debugger, and check whether
  `plans/callout-outside-gaze/debug.md` already covers the first one — root `CLAUDE.md` records that
  a debugger once re-derived a mechanism that file had already diagnosed and partly fixed.

  **How long they have been failing is unknown and worth establishing first** (`git bisect` or
  `git log -S` on the assertions): the gate's 127 failure mode means the last commit that genuinely
  ran body-layer's tests is not the last commit that appeared to.

- [ ] **X-B23 — 41 `worktree-agent-*` branches whose harvest state is unknowable.** Filed
  2026-09-27 from the integrity audit's finding 6. Because the worktree handoff is a cherry-pick,
  an agent branch never registers as merged into `main` — so an unharvested branch and a harvested
  one look identical, and 67 had accumulated against 58 real branches, crowding the Session Start
  state check (`git branch -v --sort=-committerdate | head -20` was 13/20 scaffolding).

  **Half is fixed and needs no decision:** the 26 that *were* merged are deleted, `CLAUDE.md`'s
  Session Start command now filters the prefix, and `AGENTS.md` rule 1 deletes each branch at
  harvest time, so from now on a branch's existence means "not yet harvested" again.

  What remains is the 41 already-ambiguous ones, left in place rather than guessed at. Resolving
  them means, per branch, checking whether its commits' content reached `main` (`git log -p` against
  the corresponding `plans/*/` and `.claude/agent-memory/` files, since a cherry-pick changes the
  sha but not the content). Worth doing once, in one pass, mainly to find any **agent memory that
  was never harvested** — `AGENTS.md` calls that the most expensive loss in this system, because its
  whole purpose is to stop a later agent repeating a mistake, and the failure is silent by
  construction. Not urgent: the filter makes the daily cost zero.

- [x] **X-B24 — Status page's daily launchd refresh: REJECTED by the user, 2026-09-27.** It stays manual. The plist template remains in the repo unused; do not propose installing it again, and do not re-file this. Original text follows. Filed
  2026-09-27 from the integrity audit's finding 7. The skill and the script both asserted "a launchd
  agent runs it at 05:00 local, daily"; `launchctl` has no such job and `~/Library/LaunchAgents/`
  no such plist, so it has only ever run by hand. Both statements now say
  available-and-not-installed, which closes the *contradiction* — this item is the remaining
  **decision**, and it is the user's: installing a background job on their Mac is not something to
  do unasked.

  The plist (`.claude/scripts/com.petrobrain.status-page.plist`) carries its own `launchctl
  bootstrap` line and the script is already guarded to do nothing on a dirty tree, a non-`main`
  branch, no commits in 24h, or a missing `claude` binary. So installing it is one command; the
  question is only whether a derived page regenerating itself overnight is wanted at all, given it
  is explicitly never authoritative.

### Added 2026-09-28

- [>] **X-B25 — The destructive tokens share the ordinary confirm window; revisit when the channel
  changes.** `fix/confirm-band-affirmatives` raised `CONFIRM_WINDOW_S` 8.0 → 15.0 s and added a 20 s
  late-answer grace, and that window also gates `cancel_task`/`cancel_scan`/`cancel_watch` — the
  three tokens that *destroy* standing state and already carry a raised confidence floor
  (`ACT_FLOOR_CANCEL`) for exactly that reason. So a stale "cancel everything, confirm?" now stays
  committable for 15 s instead of 8, answerable by a wider set of words.

  **Accepted by the user 2026-09-28** — *"15 s acceptable for now"* — on Security's own reasoning:
  the too-narrow window was the sortie-demonstrated defect being fixed, and a destructive confirm
  nobody can ever answer is not safer, only silently broken. Probability low, impact medium, and
  the input is the pilot's own PTT-gated speech in a single-player session.

  **This item exists because of the "for now", and carries the lapse condition the project requires
  of any standing acceptance** (root `CLAUDE.md`, Agents: a blanket exemption with no stated end
  outlived its premise once already). Revisit when **either** of these becomes true:

  - **BL-10/SRS changes who can speak into this channel.** The whole risk assessment rests on one
    pilot, one microphone, one session. Anything that widens that — another crew member, a shared
    intercom, a recorded or replayed audio path — invalidates the premise rather than merely
    stressing it.
  - **A sortie shows the window is longer than it needs to be.** 15 s is a reasoned budget, not a
    measurement. If the pilot reports answering comfortably every time, the right move is to shorten
    it for the destructive tokens specifically rather than leave headroom nobody uses.

  The narrower fix, if it is ever wanted, is a `CONFIRM_WINDOW_S_CANCEL` mirroring the existing
  `ACT_FLOOR_CANCEL` split — the mechanism is already there and precedented, which is part of why
  accepting now costs little.

- [x] **X-B26 — Can DCS terrain elevation be read from its own files during flight, rather than
  probed?** User question, 2026-09-29: *"can we sample directly from DCS terrain grid files
  dynamically during flight, or do we need to live probe DCS."* This gates the whole live-terrain
  sampling design (`plans/live-terrain-sampling/design-input.md`) and the two routes are materially
  different builds — a file read has no frame-rate risk and no bridge-throughput ceiling, while live
  probing has both and its throughput is still unmeasured. The file route also matches this
  project's standing preference for DCS-native extraction over probing. **Investigate before
  committing to a probing design, not after.** Investigator pass; the DCS install is on the Windows
  box, and `world-model/data/raw/dcs/2026-09-02/DCS-files.txt` inventories it.

  **ANSWERED 2026-09-29 on the Windows box: both routes work; take the probe.** Two measurements,
  neither of which existed when this item was written:

  - **The bridge is cheap** — 568 units, mean 1.99 ms, p99 8 ms at 1 Hz, ~2.6 µs per item
    (`aircraft-layer/research/2026-09-29-bridge-call-cost-at-scale.md`). "Its throughput is still
    unmeasured" above is no longer true, and the frame-rate risk this item ascribes to probing is
    the one thing still open, not the throughput.
  - **The file route is real but unfinished** — `Syria.surface5` does encode elevation, confirmed
    129/129 against DCS ground truth against a 71/129 null control, with a working index walker and
    a correct geo-reference (`world-model/research/2026-09-29-surface5-elevation-confirmed.md`).
    But only a per-tile min/max envelope was decoded; per-node heights need the `Pbase` payload
    located inside 30 GB of undocumented container, still the 1–2 week bet M7 estimated.

  So the standing preference for DCS-native extraction is **not** decisive here: it would buy a
  fortnight's decode to obtain what `land.getHeight` already returns exactly, for ~2 ms, live.
  **Recommend closing as "probe", with `.surface5` parked as a known-good fallback** should the
  elevation-cost probe (deployed, awaiting a sortie) come back expensive. Leaving `[ ]` pending
  that probe's number and the user's call.

  ### CLOSED 2026-10-05 — neither route. **No live elevation polling at all.**

  **User decision**, after the elevation-cost probe flew and after an audit of who actually reads
  the elevation grid: *"I'd rather use coarse grid calculated from ridge/valley data and not poll
  elevation data in DCS, unless another reason comes up that requires it in live missions. Reject
  elevation probing from live missions with the caveat that something later might require it,
  build it if that happens."*

  **This closes the question the item asks by rejecting its premise.** Both routes were about
  getting *better* elevation into a live mission. The audit found almost nothing live needs it:

  - The grid's one real production consumer is `world-model/src/query/line_of_sight.py`, reached
    from `perception/visibility.py`'s naked-eye terrain gate. `X-B29` moves the **live** LOS answer
    to DCS, which leaves that primitive serving the offline and test path only — and a test oracle
    needs to be *deterministic*, not accurate.
  - `describe_position`'s `elevation.dcs_m` is exposed and has **zero production callers**: its
    only non-test caller is `perception/geometry.elevation_at`, which nothing in `src` calls.
  - Geomorphons reads SRTM `.hgt` directly and never touches the stored grid; `query/divides.py`
    samples no elevation by design; contact enrichment uses the features' own
    `elevation_range_m` tags; mission-interpreter has no `elevation` reference in `src` at all.
  - Measured on the 2026-10-04 `syria-full` rebuild: `grid_sample` is **46 MB of a 704 MB store
    (6.5%)**, 2,365,517 samples, and `elevation` is the only grid kind ever built. So this was
    never a disk argument.

  **The caveat is part of the decision, not a hedge**: if something later genuinely needs live
  elevation, build it then. Everything needed to do so is now measured and written down rather
  than guessed — `land.getHeight` works through the bridge and is bit-identical to the
  mission-editor probe at eight theatre-spread points; cost is ~215 points per call at a 2 ms
  budget, budgeting against the **cold** peak (9.2 µs/item) rather than the warm median; and a
  2601-point batch visibly stutters the frame. See
  `aircraft-layer/research/2026-10-05-elevation-cost-probe-results.md`.

  **`.surface5` stays parked, and this makes it less likely to ever be needed** — the fortnight's
  decode was always justified by live sampling, which is now rejected.

  Replacement work: `WM-B7` in `world-model/ROADMAP.md` (a coarse grid derived from ridge/valley
  data, as the deterministic test oracle). Low priority, gated on `X-B29` landing first, and
  explicitly not a live-accuracy project.

- [>] **X-B27 — Topology: body-layer and world-model stay together, on the Mac for now, Windows
  eventually. DECIDED 2026-09-29, deferred as work.** User: *"I will keep body and world layers on
  Mac for now, development is much easier that way. The eventual setup will run them on windows."*

  **So the service split is rejected, not merely unscheduled** — the in-process coupling stays, and
  the two subprojects move together or not at all. Three standing consequences, which are the
  reason this item stays open rather than being closed:

  - **Nothing may assume the Mac.** body-layer and world-model must stay cross-platform and free of
    macOS-only assumptions (paths, `say`, shell tools), because the target is Windows even though
    today's runtime is not. A Mac-only dependency introduced now is a migration cost incurred
    silently.
  - **Nothing may assume a network seam between body-layer and world-model either.** The import
    stays in-process, per root `CLAUDE.md`'s sole-exception rule. Do not design around a future
    HTTP boundary that has now been decided against.
  - **The LOS call-rate measurement below is no longer needed for this decision.** It was the
    gate on the *service* route only. Keep it in mind as ordinary performance curiosity if a dense
    scene ever feels slow, not as a blocker for anything.

  Original item follows, kept because its reasoning is what the decision rests on.

- [ ] **Measure the line-of-sight call rate per poll before considering a world-model
  service split.** The user raised making world-model its own service on the Windows box (where the
  DCS terrain files are), with an HTTP API to body-layer on the Mac — motivated, and stronger still
  if X-B26 says terrain files are readable. But body-layer ↔ world-model is the **sole sanctioned
  in-process cross-subproject import** (root `CLAUDE.md`), narrowed to "same box always" by
  `plans/pb1-perception-logger/plan.md` decision 3, and it sits on a hot path:
  `perception/visibility.py:769` calls `line_of_sight_clear` per candidate, per poll, at 5 Hz. A
  dense scene is plausibly hundreds of LOS checks per second — free over loopback, not free over
  the LAN. **The call rate decides the design** (batch per poll, move the gate to the Windows side,
  or keep it in-process), so measure it before moving code. The detection trace already records
  every `check_visibility` call, so this is a reduction over data the project already collects, not
  new instrumentation.

  **The alternative the user raised 2026-09-29, and it is probably the better one: keep the
  in-process coupling and eventually run *both* body-layer and world-model on the Windows box.**
  It preserves the sole sanctioned cross-subproject import instead of breaking it, and it moves the
  topology in the right direction rather than sideways. Today the *high-rate* seams cross the LAN —
  aircraft-layer → body-layer polls telemetry and world objects at 5 Hz over the wire, and
  world-model answers LOS in-process on the Mac. Moving body-layer to Windows makes **both** of
  those loopback (aircraft-layer is already there; world-model would sit next to the DCS terrain
  files it wants to read, per X-B26), leaving on the wire only the seams designed to be
  asynchronous: body → brain (`/escalate` + poll, whose own plan constraint is *"the brain cannot
  block anything"*) and body → audio-adapter (a line of text, occasionally). It also removes the
  manual `.sqlite` copy step `body-layer/CLAUDE.md` currently puts on the user.

  Costs, both real: the Mac is the development box and body-layer is where most iteration happens,
  so its tests and console harness would run away from where the work is done (mitigable — nothing
  in body-layer touches DCS directly, so it stays testable anywhere); and the Windows box would
  need body-layer's heavier dependency chain, `pyproj` included. Brain and TTS stay on the Mac
  either way.

  **Note for whoever picks this up: the measurement above is only needed for the *service* route.**
  The both-on-Windows route does not need it at all, because the LOS call never leaves the process.
  On that route this item becomes a deployment/packaging task, not a performance investigation.

- [>] **X-B28 — LOS must read the probe grid; SRTM stays coarse as the floor. DECIDED 2026-09-29,
  then SUPERSEDED the same day by X-B29.** Kept because the reasoning is still the record of how the
  decision moved, and because the elevation grid itself is not superseded -- only its role in line
  of sight.

  **What changed:** the user chose DCS-driven LOS (X-B29). Line of sight now comes from DCS itself,
  so it no longer depends on the fineness of our own terrain model at all, and the probe-grid
  wiring below stops being the critical path. His own framing of what the grid is still for:
  *"what we need it for is knowledge of the land formations. Where the ridges, valleys etc are. That
  is important information, but since LOS now is not dependent on finegrained terrain model, this
  moves to a lower priority. We do still need it, but maybe we can relax the grid spacings. To be
  redesigned."*

  So: the grid survives with a different job (land formations, `describe_position`, offline Mission
  Interpreter enrichment), a lower priority, and spacing that should be redesigned around *that*
  purpose rather than around line of sight. The original text follows.
  User, after the Windows-box session relayed its terrain findings: *"LOS calculations **must** use the
  probed refined grid, that is the whole point. Flight over unprobed terrain would automatically probe
  it. Therefore finer grid would always exist. Fine grid SRTM cost/value is low."*

  **This rejects the 100 m SRTM rebuild** the Windows session recommended. The reasoning is sound: a
  finer pre-built grid pays to compute something the probe supersedes the moment it matters. SRTM
  stays at 1000 m as the always-there floor.

  **The prerequisite, and it is the whole point of the item:** `query/line_of_sight.py` reads the
  **base grid only** — `sample_grid(conn, "elevation", x, z)` at line 142, with no schema argument, so
  it never touches the probe store. `perception/geometry.py:open_world_model` opens the region DB
  read-only with no ATTACH either. Verified independently on the Mac, and the same gap was found by
  the missed-AAA debugger. `query/describe.py` already does the layering correctly
  (`sample_probe_grid(..., schema="probe")` first, `sample_grid` fallback), so this is a small change
  — **but until it is made, no amount of probing improves line of sight at all.**

  Two gaps that survive the decision, neither fatal:

  - **The first-look window.** Probing happens on arrival, but LOS is asked its first questions
    before those samples land, so genuinely new ground falls back to 1000 m SRTM exactly when the
    aircraft is newest to it. `docs/concept/PETROBRAIN_RUNTIME.md`'s look-ahead ring exists for this;
    it means "a finer grid always exists" is true a few seconds after it is needed, not before.
  - **The Mission Interpreter has no probe data by definition** — it enriches waypoints, groups and
    trigger zones offline, across the whole map, before anything has been flown. That keeps SRTM
    alive whatever happens to the in-flight grid, and coarse is adequate there: it is waypoint
    context, not line of sight.

  Sequence, when work resumes: wire LOS probe-first (Mac side, per X-B27), then build probing. Not
  the reverse — the probe store filling up changes nothing until LOS reads it.

- [ ] **X-B29 — Compute line of sight in the aircraft layer, batched, next to DCS.**
  **MEASURED LIVE 2026-10-05 — the approach holds, and the binding constraint turned out to be
  batch size, not call frequency.** The user flew the elevation-cost probe and reported *"a small
  but annoying stutter every few seconds"*; the log agrees and says why. Full numbers:
  `aircraft-layer/research/2026-10-05-elevation-cost-probe-results.md`. What this entry must be
  built against, replacing the extrapolated figures quoted further down:

  - **`land.getHeight` works through the bridge, exactly** — eight theatre-spread points
    bit-identical to the 2026-09-06 mission-editor probe's recorded heights.
  - **No meaningful fixed overhead**: the null call measured 0.00 ms. Cost is per item.
  - **Budget against the *peak*, not the median, and against *cold*, not warm.** A 2601-point
    `getHeight` batch is 4.5 ms steady but **24 ms peak** on first touch of a region (9.2 µs/item
    cold against 2.3 µs warm). The worst case is correlated with flying somewhere new, which is
    exactly when it matters.
  - **`isVisible` costs ~7x `getHeight` per item** (10 µs vs 1.3 µs steady). They are not
    interchangeable in a budget.
  - **At a ≤2 ms per-call budget: ~215 `getHeight` points or ~130 `isVisible` rays.** Comfortably
    above what a 10 km bubble needs; the probe's 2601-point batch was ~12x the real requirement
    and was sized to find the ceiling.
  - **Cap the batch, not just the rate.** The probe already throttled to one call per 250 ms and
    the stutter happened anyway — spreading calls bounds the duty cycle, never the single-call
    cost.

  Still unmeasured: whether a 2 ms version is actually imperceptible. The arithmetic says it
  vanishes; nobody has flown it.

  **Two scope decisions, user, 2026-10-05:**

  - **World-model's own LOS primitive stays as the offline and test path** — *"yes, there's no
    other way."* body-layer's hard requirement is that everything runs with no live DCS and no
    collector, so `query/line_of_sight.py` is not replaced by this work, it is demoted to the
    path tests and offline tools take. **What it reads changes, though**: per the same day's
    decision to reject live elevation polling (`X-B26`), that primitive's elevation source becomes
    the coarse ridge/valley-derived grid of `WM-B7`, not the 2.3 M-sample SRTM grid. So `WM-B7`
    stops being an optional cleanup and becomes the stated plan for what the offline path stands
    on — still sequenced *after* this item lands, because until the live answer actually moves to
    DCS the existing grid is still answering a live question.
  - **Building occlusion is in scope for this slice**, not a follow-on — *"yes please."* See
    `X-B30`: `isVisible` demonstrably sees buildings (2 of 40 urban pairs terrain-clear but
    vision-blocked, 0 of 40 in desert) at ~10 µs a ray, and nothing occludes behind a building in
    either current path, so this is additive capability that cannot regress what works. Carry
    `X-B30`'s own caveat into the design: the *aimed* `through_buildings` checks came back 6/6
    clear while the positives came from the broader sweep, and whether that is geometry or a
    difference between the two call shapes is **not established** — settle it before relying on a
    particular call shape.

  Original entry follows. User idea,
  2026-09-29: *"could aircraft layer fire LOS calc for every known unit inside player bubble and
  within the 130 degree visibility cone? What would that cost? Maybe not every tick?"*

  **This inverts the seam and removes the reason the LAN was a problem.** Instead of body-layer
  asking per candidate (N round trips per poll), aircraft-layer computes LOS for every relevant
  unit in **one batched bridge call** and publishes the result the way it already publishes
  telemetry, world objects and indication text. Body-layer polls one response. Existing pattern,
  no new seam.

  Cost, from the Windows session's measured figures (0.5 ms fixed bridge overhead, 8.7 µs per
  `world.searchObjects` SEGMENT sightline, `aircraft-layer/research/2026-09-29-bridge-terrain-probe-results.md`
  finding 21):

  | units in bubble + cone | one batched sweep |
  |---|---|
  | 50 | 0.9 ms |
  | 200 | 2.2 ms |
  | 500 | 4.9 ms |

  At 1 Hz that is 0.2-0.5% duty, and the mission bridge already runs at 1 Hz, so it rides an
  existing cadence. It does not need every tick: at 83 m/s LOS state changes over seconds.

  **Density was already in the measurement** (user's own point: DCS missions do not carry hundreds
  of *units* in cities, though they carry thousands of *buildings*). Finding 21's rungs were flown
  over town/forest/mountains with 28% of 2 km rays clipping a building, and the two rungs agree to
  0.1 µs. The superlinear result that prompted the worry was a *sphere* search, a different volume.

  **The consequence that makes this more than an optimisation: it could remove the probe grid from
  the LOS path entirely.** LOS computed against DCS's own terrain and own buildings has no SRTM
  error to correct, needs no probe accumulation, and dissolves the missed-AAA defect class at its
  source rather than mitigating it with a 12 m tolerance. That is not omniscience -- line of sight
  is a physical fact about the world, not knowledge, and belief about *position* stays as fuzzy as
  it is now.

  Three constraints any design must keep:

  - **Tests must run with no DCS and no collector** (`plans/body-layer/plan.md` §2, a hard
    requirement). So world-model LOS stays as the offline and test path; this becomes the *live*
    path, not a replacement.
  - **The Mission Interpreter still needs the elevation grid** for offline enrichment, and
    ridges/valleys are derived from it.
  - Aircraft-layer so far reports facts rather than computing gates. HelperAI detection text is the
    precedent that this is not a new kind of thing, but the boundary shift should be argued, not
    assumed.

- [ ] **X-B30 — Building occlusion is NOT gated on the Windows move.** User direction, 2026-09-29,
  correcting an earlier read of mine: *"Do not gate buildings on the Windows move. While that may be
  the eventual setup, development is easier on my mac. The LAN delay penalty is acceptable during
  development."* So the buildings half of the occluder work proceeds Mac-side now, paying the LAN
  round trip, rather than waiting on X-B27's eventual topology. X-B29 above may make the point moot
  by batching the call anyway.

  **Positive evidence arrived 2026-10-05, unplanned, from the elevation-cost probe.**
  `occlusion_urban` reported **2 of 40 pairs where terrain alone was clear but `land.isVisible`
  said blocked**, against **0 of 40** in open desert, with `scenery_search` resolving real building
  objects (`BUNKERHILL`, `TAXI_OMNI_BLUE`) at the same place. So the scenery half of
  `isVisible` demonstrably fires on real geometry, at ~10 µs a ray.

  This **refines rather than contradicts** `aircraft-layer/research/2026-09-29-tree-los-probe-results.md`:
  that note concluded no DCS call sees *trees*, and its own wording was "terrain and scenery only"
  — buildings are scenery. The tree probe could not have shown this because it was looking for the
  half that does not exist.

  **One caveat, stated because it would be easy to over-read the result**: the directly targeted
  `through_buildings` and `through_buildings_wide` checks both returned 6/6 clear, 0 blocked, so
  the two positives came from the broader sweep rather than the aimed test. Whether that is
  geometry (the aimed pairs happened not to cross a building) or a real difference between the two
  call shapes is **not established**, and should not be assumed either way before building on it.

  See `aircraft-layer/research/2026-10-05-elevation-cost-probe-results.md`.

- [>] **X-B32 — DCS's per-tree placement is in `Syria.surface5`, behind the payload-addressing wall.
  DEFERRED 2026-10-01, same day it was opened.** Investigated on the Windows box in answer to the
  user's question *"what would it take to access the compiled tree aware LOS and call it between
  point A and B?"*. Full detail:
  `aircraft-layer/research/2026-09-29-tree-los-probe-results.md` Finding 10.

  **The question's own answer: you cannot call it.** No scripting binding exists; reaching the
  compiled test needs native injection into the DCS process — against the EULA, broken by every
  update, not a route. The rest is about rebuilding its input.

  **What was found.** Trees live in `Syria.surface5` as per-node `Trees` sections — **8,789 in the
  first 150 MB** — each with a `Pbase` array of ~325–346 twelve-byte positions and an `assetIndex`
  into a **readable 2,665-entry asset-name table at 140.3 MB**. Syria instances six species:
  `italiancypress`, `juniperus`, `mandal2`, `palm`, `pineitalian2`, `platan`. Extrapolated, that is
  **millions of individual tree positions** — better than the patch-centres outcome hoped for, and
  comfortably past the user's bar of "need to know if they block LOS".

  **Why it is deferred anyway.** The field table's `offset` is not a file offset: `Trees.Pbase`
  states 585 KB and the bytes there are another node's field declarations. Offsets grow with node
  index at no constant ratio — the recursive LOD quadtree. Candidate data bases, including the
  exact end of the descriptor region (0x85d2616), give degenerate clouds. **This is the same wall
  the elevation decode hit** (`world-model/research/2026-09-29-surface5-elevation-confirmed.md`
  Finding 5). Two attempts, two payloads, one blocker.

  **Correction worth keeping, because the wrong turn is re-walkable.**
  `surfaceDetails/Syria.sd5` parses perfectly — 276,924 records — and is **ground clutter, not
  trees**: its splat layers are grass, two desert shrubs and three rock types. The sibling `.ref`
  files are **SpeedTree meshes of a single tree**, not placements. Three files that look like tree
  data; none is.

  **Effort, revised.** The earlier "3,400× smaller, an afternoon" estimate was based on the wrong
  file and is withdrawn. The work is the **full 30 GB `.surface5` payload decode** — M7's 1–2 weeks
  with a real chance of stalling, now having stalled twice at the same point.

  **Reopen only if** someone takes on payload addressing deliberately — and then cost it as a
  **terrain-elevation** project that happens to yield trees, not the reverse. The reason is
  survival rather than sequencing: **trees have a working fallback and elevation does not.** OSM
  landcover ships today; the missed-AAA class has nothing behind it. A fortnight-long decode
  justified by the half that already has an alternative is the one that gets dropped at the
  midpoint, leaving the decode half-done — worse than either finishing it or never starting.

  **The transferable finding is the wall, not either negative:** two attempts from two unrelated
  payloads reached the identical blocker. That is what stops a third person spending an afternoon
  rediscovering it. OSM landcover remains the shipping answer for trees; nothing is blocked.
