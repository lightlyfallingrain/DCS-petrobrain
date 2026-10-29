## Security Plan Review: bl-b67-atgm-run

Reviewed: `plans/bl-b67-atgm-run/plan.md`, `explore-notes.md`,
`aircraft-layer/research/2026-10-29-bl-b67-loadout-and-atgm-object-recon.md`, at tip
`858625061c9ee6cdac95b3f69152b8c320e6b872`. Scope per root `CLAUDE.md`/`.claude/agents/security.md`:
computer/network security only (code execution, access to the computer, what a LAN port scanner
reaches, prompt injection, dependencies/secrets) — single-user, LAN-only threat model, one
proportionate pass. Player-experience correctness (no-omniscience boundary, callout wording,
guidance accuracy) is Reviewer's, noted below without a verdict.

### Dependencies Checked

No new dependency. The plan has no dependency statement at all (`grep` over the plan file for
dependency-shaped language returns nothing) — checked this isn't a silent omission by reading
"Affected Modules" directly: every new file is Python stdlib (`src/schema/payload.py`,
`src/schema/fire_button.py`, `src/perception/own_weapons.py`, `src/belief/atgm_run.py`) or Lua
additions to the already-committed `Export.lua`/`Export.probe-weapons.lua`. Both subprojects
already declare stdlib-only. Nothing to escalate.

### Design Findings

**No new write-path category.** `select_station` and `radiation_reset` both resolve, through
`effector_engine.write_effector`/`advance`, to the existing `client.write_cockpit_switch(device,
cmd, value)` → `POST /command/cockpit_switch` — the one deliberate generic-write exception
already reviewed and user-overridden on BL-B66
(`.claude/agent-memory/security/project_cockpit_write_vocabulary_invariant.md`,
`project_bl_b66_9k113_effectors_deep_analysis.md`). The plan adds no new generic write primitive
and no new POST endpoint to aircraft-layer. Every value this plan writes is one of a finite named
set from `effectors.toml` (`missile_station`: `off=0.0, s1=0.1…s8=0.8`; `radiation_reset`:
`pressed=1.0, released=0.0`) resolved by name through `EffectorDef.values`, not a float threaded
in from network input — same bounded-registry shape as every other effector. `select_station(step)`
computes which *name* to write (next loaded station, an int 1–8) but still indexes into the fixed
table; it cannot cause an arbitrary `performClickableAction(device, cmd, value)` call.

**Correction to a standing memory item.** `.claude/agent-memory/security/` (`AC-B11`'s own text,
`aircraft-layer/ROADMAP/AC-B11.md`) assumed BL-B67 would add a sixth unbounded-`Content-Length`
POST handler to `TelemetryAPIServer` ("eventually six, once BL-B67 lands"). This plan does not —
the two new aircraft-layer endpoints are both `GET /payload/latest` / `GET /fire_button/latest`
(read-only, no request body), and the write side reuses the existing `/command/cockpit_switch`
handler already counted in AC-B11's five. AC-B11 updated with this correction (see memory below);
no new finding filed, because there is nothing new to file — the handler count stays five until
some other feature actually adds a sixth.

**New Export.lua feeds are read-only pushes, both stated pcall-guarded**, following the
already-established per-frame-closure pattern (`project_export_lua_per_frame_closures_are_established_pattern`)
and the PTT edge-detection shape (`push_ptt_state`) for the fire-button feed. Both sit in-process in
`Export.lua`, defined (per the plan's own note) below the locals they close over — the one
mechanical check this codebase has for the exact bug class that previously made `push_ptt_state`
silently publish nothing (`GETGLOBAL` bytecode scan, `aircraft-layer/CLAUDE.md`). Plan explicitly
schedules this check for Stage 4 ("Lua `GETGLOBAL` bytecode check… on the edited `Export.lua`").
Not a finding — the plan already carries the mitigation that matters here.

**Export.lua→collector channel stays loopback-only**, consistent with the existing telemetry/
world-objects channels (confirmed pattern, not re-derived: `collector/server.py` binds `127.0.0.1`
per `project_bl_b90_stage4_readback_by_need.md`). The new payload/fire-button feed does not change
who can be Export.lua's peer.

**Two new unauthenticated read-only GET endpoints extend an already-accepted exposure shape, not a
new one.** `aircraft-layer`'s API binds `0.0.0.0` (LAN-reachable by design, stated in
`aircraft-layer/CLAUDE.md`'s "What this is"); a LAN actor reaching `/payload/latest` or
`/fire_button/latest` learns ammo-station counts and a momentary button's last-press time — no
credential, no write capability, nothing beyond what `/world_objects/latest` or
`/petrovich_indication/latest` already expose about this aircraft. Consistent with this project's
stated single-user/LAN-only threat model; not escalated.

**Own-weapon object ids never cross the perception/belief boundary** (`perception/own_weapons.py`
holds ids, emits only `OwnWeaponEvents`; grep fence planned on `belief/` imports). This is a
no-omniscience/architecture invariant, not a computer-security boundary — noted under "Passed to
Reviewer" below, no verdict given here.

**No LLM involved and no prompt-injection surface.** `atgm_run.decide` is a pure deterministic
function over typed state; `belief/speech.py`'s new render functions build fixed-template strings
(`"<Family>, <N> seconds"`, `N` a rounded number) from a 3-valued `missile_family` enum and
arithmetic — not from arbitrary DCS object-name text interpolated unbounded. No brain-layer/LLM
call appears anywhere in this plan's affected-modules list.

**Probe script (Stage 0) extends an existing, already-reviewed pattern.** `Export.probe-weapons.lua`
(already committed, prior finding `C_8`) is disposable recon code per this project's standing
posture (`.claude/agent-memory`: DCS probe `io`/`lfs` access authorized for recon probes only,
never pipeline code). Grepped the existing file for `loadstring|dostring|os\.|require(` — the only
hit is `io.open` against the script's own fixed `LOG_PATH`, the same shape every other probe in
this directory uses. The proposed extensions (dump `pairs(obj)` keys, add `LoGetPayloadInfo()`)
add no new primitive.

### Verdict

APPROVED

### Required Fixes

None.

### Passed to Reviewer (no verdict given)

- Own-weapon object ids staying out of `belief/` (no-omniscience invariant) is enforced by a grep
  fence the plan proposes in Stage 5 — correctness of that fence, and of `aim_unit_direction`'s
  single-unit aim replacing the cluster centroid, is Reviewer's to verify against the diff.
- The deferred OBSERV-refused-by-cannon response and the "missile" singular not being in
  `WEAPON_WORDS` are both explicitly flagged in the plan's own Risks section as player-experience
  gaps, not security gaps.

---

## Re-review — 2026-10-29, revised plan at `e523f2b3aba17ad66128decc343808238ebee8d6`

**Branch state note.** My worktree's HEAD (`ca69f8ec`) had diverged from the target tip (ancestor
check: `git merge-base --is-ancestor HEAD e523f2b3...` → false — a prior `git merge --ff-only`
attempt correctly refused with "Diverging branches can't be fast-forwarded"). Per protocol I did
not merge, checkout, or rebase anything in this worktree. I verified the revision against an
isolated snapshot instead: `git archive e523f2b3... | tar -x` into a scratch directory, and read
`plan.md`/`explore-notes.md`/`security-plan-review.md` from there. The firing-events Hook
(`aircraft-layer/dcs-export/petrobrain-firing-events-hook.lua`), `src/schema/firing.py` and
`src/collector/firing_receiver.py` — all pre-existing, unmodified-by-this-plan reference material —
were read from this worktree's own tree (`ca69f8ec`), which is the correct source for them since
the plan builds the own-weapon branch *on top of* that unmodified code, not a copy diverged from it.
**This file, this section aside, was reconstructed from the snapshot rather than appended to a
checked-out copy, because `plans/bl-b67-atgm-run/security-plan-review.md` does not exist in this
worktree's diverged history at all** — flagged for the harvester: this cannot fast-forward onto
`feature/bl-b67-atgm-run`, and the re-review section below is the actual new content; the section
above it is a verbatim copy of the already-committed original, included only so the file reads
correctly in this worktree and nothing is lost if this commit is the one taken.

Covers the revision's changes against the six points named in the dispatch, each checked against
`plan.md`'s "Launch and impact detection" section and "Affected Modules" list (lines ~198–277,
~317–384 at `e523f2b3`).

### 1. New DCS-sourced weapon type-name string crossing the wire

`weapon:getTypeName()` is DCS-authored free text (a weapon-type identifier, not a string the Hook
constructs) and now crosses the Hook→collector wire as the `<type>` field of
`OWN_SHOT:<t>:<seq>:<type>:<category>:<guidance>:<exists01>`. The plan states, Hook-side: "`<type>`
is truncated to 48 characters and has `:;|` replaced." Checked against the existing wire discipline
(`schema/firing.py`'s `initiator` field, which is also DCS-sourced free text, is bounded only by
"can contain a colon, same defensive posture" — no length cap at all today) — **the plan's 48-char
truncation is new ground for this wire, not a repetition of an existing pattern**, and it is the
right one for a field whose only consumers are a 3-valued-enum lookup (`family_of`) and a log line,
never speech (confirmed: "the plan is to be revised for it" / "never reaches speech raw" per the
dispatch wording, and `atgm_run.py`'s `missile_family` state param is explicitly `"shturm" /
"ataka" / None`, not the raw string).

**Finding: the parser-side bound is not stated as a parser invariant, only as a Hook-side
mitigation.** The plan names the `:;|` replacement and 48-char cap only in the Hook's own branch
description (line 211-212); "Affected Modules" → `src/schema/firing.py` says only "`OwnWeaponRawEvent`;
`FiringEventBatch.own_events`; parser accepts 3 or 4 segments" — it does not say the parser *itself*
re-validates the type-field length/charset rather than trusting the Hook's cap. This matters because
of the plan's own stated risk: "**Deployed-Hook version skew**: an old Hook sends three segments…
degrades to the backstop… not a crash" — the inverse case, a stale Hook that predates the 48-char
cap fix sending an unbounded or unsanitized type string in a *four*-segment payload, is not named.
`FiringEventBatch.from_wire`'s existing pattern (`ALLOWED_KINDS`, numeric-or-"nil" fields, explicit
`FiringParseError` on anything unexpected) is exactly the right place to also bound `<type>`
independently — same posture `_parse_entry` already takes toward `initiator` (defend the parser,
don't trust the sender). **Not severity-raising on its own** (a sender-side truncation this project
controls, UDP loopback only, consumed only by an enum lookup and a log line — no path to speech, no
path to a file write, no path to a shell), but it is a real gap against this project's own stated
practice of parser-side defense, and belongs as a concrete plan amendment, not a verbal risk note.

**Recommendation (addressed at Implementer, not blocking):** `schema/firing.py`'s `_parse_entry` (or
an `_parse_own_entry` sibling) should itself cap `<type>`'s length (e.g. reject/truncate past some
bound well above 48, so a stale-Hook payload can't carry an arbitrarily long string into a Python
dict key or a log line) and reject any embedded `:`/`;`/`|` rather than assuming the Hook already
stripped them — the same "parser defends itself, does not trust the wire" posture `_parse_entry`
already uses for `initiator`.

### 2. Wire format 3→4 segments, with 3-segment back-compat

Confirmed present and correctly scoped: plan states "`FiringEventBatch.from_wire` must accept the
old three-segment payload too, as an empty own segment, because the deployed Hook copy can lag the
repo," named again under "Deployed-Hook version skew" in Risks. This is the same pattern
`schema/firing.py`'s current `from_wire` already enforces strictly (`parts = payload.split("|", 2);
if len(parts) != 3: raise`) — extending it to accept 3 *or* 4 and raising on anything else (not
silently absorbing a 2- or 5-segment payload) is the correct shape and is explicit in the plan
("parser accepts 3 or 4 segments," Affected Modules). No finding.

### 3. Bounded state: scripting-state weapon objects cap 8, collector ledger cap 32, 60 s retention, mission-restart clear

All four bounds are explicit in the plan text (lines 207-209, 220-222) and each has a stated reason:
cap 8 ("the oldest is dropped; the run never has more than one in flight" — so 8 is headroom, not a
tight fit), cap 32 and 60 s retention on the collector ledger (unstated reason but consistent with
`EmitterTracker`'s own shape), cleared on model-time regression "the same mission-boundary rule
`EmitterTracker` uses" — this is a real, already-reviewed mechanism (`_RESTART_TOLERANCE_S`,
confirmed present in `firing_receiver.py` at `ca69f8ec`), not an invented one. This closes the
exact unbounded-growth shape a LAN scanner replaying/flooding `S_EVENT_SHOT`-shaped traffic would
otherwise exploit (an attacker on this LAN cannot inject Hook-side Lua events at all — DCS is the
only producer of `S_EVENT_SHOT` — but the collector-side cap matters against a compromised or buggy
Hook, or simply against this project's own bug surface). No finding; matches this project's
existing bounded-ledger precedent.

### 4. `GET /firing/latest` gaining own-weapon times on the LAN

Checked against the threat model (single-user LAN, port-scanner-reaches-everything posture already
applied to `/payload/latest` in the prior review). `own_weapons` on `/firing/latest` is read-only,
no new endpoint, no new bind address, and discloses: a Hook-local sequence number, a weapon type
name (already bounded per point 1 above, pending the parser-side amendment), category/guidance
enum values, and shot/gone timestamps for *this player's own* missile launches. This is strictly
less sensitive than what `/firing/latest` already discloses about *other* units' firing
(`initiator` names, `targets_ownship`, positions for `S_EVENT_SHOT`) and no more sensitive than
`/payload/latest`'s ammo-station counts, both already accepted in the prior review under this
project's stated LAN-only threat model. No new finding; same posture extends cleanly.

### 5. Changed Hook code inside string literals sent to the scripting state — the `GETGLOBAL` check must run on the extracted literals

Confirmed the plan states this explicitly and correctly, twice: Stage 5 bullet one, "Run the
`GETGLOBAL` check on the **extracted** `EVENT_REGISTER_CODE`/`EVENT_POLL_CODE` literals (`luac -p`
does not look inside strings)." This is exactly `aircraft-layer/CLAUDE.md`'s own documented
procedure (confirmed by reading that file and by the knowledge-graph query above, which surfaced
the same "GETGLOBAL bytecode scan" node and the no-hoisting caveat) — "extract the literal to its
own file and check it separately," the lesson from the `push_ptt_state` incident. The plan's own-
weapon branch is new code added inside exactly those two literals (`EVENT_REGISTER_CODE`'s handler
body, `EVENT_POLL_CODE`'s drain), which is precisely the half `luac -p` on the outer `.lua` file
cannot see. The plan names the mitigation at the right stage (Stage 5, before this code ships) and
for the right reason. No finding.

### 6. Extra 1 Hz GET

Named explicitly in Risks: "One extra `GET /firing/latest` per poll (the tracker, beside
`naked_eye_source`'s own). It is a small JSON, 1 Hz... A local, reversible choice." This is a
performance/coupling tradeoff, not a security one — correctly out of this role's scope (it adds no
new listening socket, no new attack surface, nothing a port scanner wouldn't already reach via the
existing `/firing/latest`). No finding; noted only to confirm it was read and is not being silently
skipped.

### Summary against the prior review

The prior review (`858625061c`) approved a design built on a fire-button feed, `GET
/fire_button/latest`, and `ATGM_LAUNCH_COINCIDENCE_S`/`ATGM_OBJECT_NAMES`-by-name identification —
all of that is now dropped. None of the prior review's approved findings (loopback-only Export.lua
channel, bounded cockpit-write vocabulary via `effectors.toml`, no new generic write primitive, no
LLM/prompt-injection surface, probe-script posture) change under the revision: the revision removes
a read-only GET and an unbounded-by-name identification scheme, and replaces them with a smaller
read-only wire addition riding the *existing* firing-events bridge. The attack surface is narrower
in the revision, not wider — one fewer endpoint, one fewer per-frame cockpit-arg push, the same
bounded-write posture, the same loopback-only transport.

### Verdict

**APPROVED**, with one non-blocking plan amendment required before Stage 5 is implemented (see
"Required Plan Changes" below) — proportionate to a single-user, LAN-only project where the gap is
a missing explicit parser-side bound on a field that already has a sender-side mitigation, UDP
loopback-only, and is never read as anything but an enum lookup or a log line.

### Required Plan Changes

1. **Add one sentence to "Affected Modules" / `src/schema/firing.py`** (or to Stage 5's own bullet
   list) stating that `_parse_entry`'s own-weapon sibling independently bounds `<type>`'s length and
   rejects embedded `:`/`;`/`|`, rather than relying solely on the Hook-side truncation/replacement —
   matching `_parse_entry`'s existing defense-in-depth posture toward `initiator`. This is a one-line
   plan edit and a small addition to Stage 5's test list ("type fields are bounded" already appears
   there — extend it to state the bound is enforced in the parser, not merely assumed from the
   sender).

### Passed to Reviewer (no verdict given)

- Everything the prior review passed to Reviewer still applies unchanged (own-weapon object ids
  staying out of `belief/` via the grep fence; `aim_unit_direction`'s single-unit aim).
- The revision's own correctness questions — whether `S_EVENT_SHOT` reliably carries `event.weapon`
  for the 9M114/9M120 (Q6, "the load-bearing unknown" per the plan's own Risks), whether a jettison
  is correctly assumed not to fire `S_EVENT_SHOT`, and the InFlight silence/pass-through-channel
  table — are all player-experience/correctness findings, not security findings, and are Reviewer's
  to verify against the eventual diff.
