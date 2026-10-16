## Security Deep Analysis: attack-run-sortie-fixes (BL-B70)

### Scope

Branch `feature/attack-run-fixes` at `d826a54` (fast-forwarded from a stale worktree base
`5015a66`, no divergence — see Procedure below). Reviewer approved at `d826a54` (`review-2.md`,
re-review of fix commit `571e898`). This pass covers BL-B70 only; BL-B71 (the optic guidance
ladder) is not in this branch.

Changed files: `body-layer/src/belief/attack_run.py`, `body-layer/src/belief/speech.py`,
`body-layer/tests/test_attack_run.py`. One tuning-constant change
(`ATTACK_TARGET_LOS_MAX_AGE_S`, `perception/naked_eye_source.py` / `defaults.toml`), already
reviewed and approved in `plans/attack-run-sortie-fixes/review.md`'s Optional Refinements and
confirmed by `review-2.md` to be unchanged by the fix commit.

### Procedure

- `git rev-parse HEAD` at dispatch returned `5015a66f302f3380693eff2459adbf90a1169de7`
  (stale worktree base, per the standing worktree-staleness rule), `git status --porcelain` clean,
  and `5015a66` a strict ancestor of the named tip `d826a54fff061f2297196e17ef332445db27eaf2`.
  Fast-forwarded (`git merge --ff-only d826a54…`); no divergence, nothing lost.
- Queried `.claude/scripts/memory-search.py` for prior findings on `attack_run`/`speech`/cause
  taxonomy — none indexed yet (this is this module's first Security pass since the sortie-fix
  plan). Queried `gq.sh` for the attack-run guidance neighbourhood in the knowledge graph — no
  prior security finding on `attack_run.py`/`speech.py` turned up; the node list is the design
  docs/source files already read for this analysis.
- Read `.claude/agent-memory/security/` for applicable recurring-pattern lessons. Two looked
  relevant by name and were checked against this diff specifically (see Code Findings):
  `project_exemption_from_a_gate_check_both_transitions.md` (does a cause/state check only verify
  one direction of a transition) and `project_bl_b64_field_of_regard_unenforced.md` (does a plan's
  deferred enforcement actually land, and is newly-added bound data read anywhere or only tested
  `is not None`).
- Read the full feature diff (`git diff main...d826a54` over the three changed files, 1502 lines)
  before the grep hit list, per Mode 2 step 2. Grepped the two changed source files directly for
  `eval(`, `exec(`, `subprocess`, `os.system`, `pickle`, `yaml.load`, `__import__`, `open(`,
  `getattr(`, `setattr(` — zero hits. No new dependency, no new tuning constant beyond the one
  already reviewed.

### Dependency Status

No dependency change. No new import outside this project's own `belief`/`perception` packages
(`cockpit_mask`, `object_model`, `optics.UNAIDED_OPTIC`, `visibility.tier_ranges`,
`naked_eye_source.ATTACK_TARGET_LOS_MAX_AGE_S`), all pre-existing modules.

### What this feature actually is, for scoping

Pure-function speech/guidance logic: `_no_look_cause` (a cause taxonomy computed from
`cockpit_mask.is_visible`, `Contact.live_los_clear`, `visibility.tier_ranges` — the same
primitives `check_visibility` already gates on, in the same order), `_should_emit` (a text-equality
veto, strictly simpler than the angular-threshold clause it replaces), and `speech.py` additions
(`alignment_clock_hour`, `alignment_phrase`, two new render functions, a new age-phrase helper).
No I/O, no network, no file system, no subprocess, no new external input source — `Contact` and
`OwnshipState` are the same internal, already-trusted belief-store objects every other `belief/`
module reads. Nothing here is reachable from untrusted (non-DCS-sim) input, and nothing here is
new input-trust surface at all: it is a re-derivation of an existing taxonomy from existing data,
not a new ingestion path.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `attack_run.py` `_no_look_cause` | Gate order (mask → range → LOS → fallback) mirrors `check_visibility`'s real gate order, verified against source (`visibility.py:990-1023`) by both Reviewer passes and re-traced here | Correct; this is the no-omniscience-relevant part of the diff and it tightens disclosure (a target beyond naked-eye presence range now correctly reads `"too_far"`, never a misattributed `"obstructed"`) rather than loosening it | None |
| `attack_run.py` `decide` — `MASKED` branch | Checked against `project_exemption_from_a_gate_check_both_transitions` (does a state-keyed branch admit a payload direction its own justification does not cover): `cause == "masked"` returns `state, None` **symmetrically** — it is not keyed on entering vs. leaving the mask, both directions get the identical silent treatment, and the plan's own text says why (a break that masks the target must not itself start or end a "losing sight" episode). `last_spoken_unresolved`/`last_spoken_text`/`last_spoken_clock_hour` are all left untouched on a `MASKED` tick, on both edges — verified by reading the single `if cause == "masked": return state, None` short-circuit, which is unconditional and precedes every other branch, so there is no asymmetric code path to find | No finding — the memory lesson's failure mode (a kind-keyed exemption that only checks the motivating direction) does not reproduce here because the branch is a single return with no direction-dependent sub-case | None |
| `attack_run.py` `decide` — §10 losing/regaining sight | `losing_sight`/`regaining_sight` are each the opposite edge of the same boolean (`now_unresolved` vs. `state.last_spoken_unresolved`); both edges have their own render path and their own test (`test_decide_lined_up_tier_transition_speaks_once_each_way`, the new cause-taxonomy tests). Checked for the B64 "enforcement deferred, never checked at the next stage" shape — not applicable; the taxonomy and its consumer land in the same commit, not split across stages | None | None |
| `attack_run.py` `_no_look_cause` — mask test uses `body_relative_direction(..., bank_deg=ownship.bank_deg)`, not `decide`'s own bank-removed `alignment_direction` | Deliberate and documented (mirrors `belief.contacts._callout_may_speak`'s existing mask check, same call shape). Using the bank-removed azimuth here would under-mask during a banked turn — i.e. the *wrong* choice would be the more permissive, omniscience-leaking one, and the diff takes the stricter one | None | None |
| `speech.py` `render_attack_run_lost_sight`/`_attack_run_regained_sight` | New f-string composition from `phrase` (internal vocabulary word), `what` (`_unit_type_display`, an existing pre-reviewed helper), `where` (`"ahead"` or `None`, both internal literals), `age` (bucketed string from `_attack_run_last_seen_phrase`). No externally-controlled string reaches a render, log, or any executed context — these are TTS text, never evaluated, never used as a format string for anything downstream besides display/speech | None — no injection surface; this is pure string assembly for a voice line | None |
| `_attack_run_last_seen_phrase` | `minutes = round(ago_s / 60.0)`; `ago_s` is `now_sim - contact.last_seen_sim`, both floats from the belief store's own sim clock, not attacker-influenced; bucketed into four fixed phrases, no unbounded growth, no injected number beyond `_spoken_number(minutes)` which is an existing bounded word-formatter | None | None |
| `AttackRunState` field changes | All new/removed fields go through `replace()`, never a fresh `AttackRunState(...)` construction except the deliberate full reset on `contact.id` mismatch (unchanged from before this diff, and that reset is the one place a fresh construction is *correct*, not the F4 trap) — confirmed by the diff itself (`replace(state, ...)` at every emit/memory-update site) and by Reviewer's own grep (`review-2.md`) finding no new fresh-construction site | None (the `BL-B64`-class bug this plan's own F4 flagged pre-emptively is the thing the implementation avoided, not a finding against it) | None |
| Removed `ATTACK_RUN_CHANGE_THRESHOLD_DEG` | Deletion of a tuning constant and its two baseline fields (`last_spoken_azimuth_deg`/`last_spoken_elevation_deg`); `defaults.toml` correctly drops the entry (verified by diff) | None — a deletion, not an added surface | None |
| `", obstructed"` unreachable in live play | Already filed as `BL-B76` on `main` (Reviewer's finding, narrowed 2026-10-16, pre-existing — `Contact.live_los_clear` can only be `True`/`None` in live play, never `False`, outside tests/replay) | Known, not new; not re-reported as a finding of this pass, per the dispatch brief | None (tracked on `main` as `BL-B76`) |

### No-omniscience invariant

This feature is, if anything, a strengthening of it: the cause taxonomy's whole point is to stop
tier-2 guidance from attaching an incorrect `", obstructed"` qualifier to a target that is merely
beyond naked-eye presence range (`"too_far"`) or behind the cockpit mask (`"masked"`, now silent
rather than spoken at all). The one accepted gap — `UNKNOWN` speaking bare tier-2 guidance with no
qualifier, indistinguishable from a live look — is the plan's own named Risk (`plan.md`, Risks &
Unknowns), already surfaced to the user and already a `[?]`-style open question in the plan's
Decisions section ("Does an unqualified UNKNOWN tier-2 callout need any marker at all? Recommend
no"), not a new finding from this pass.

### Verdict

APPROVED

### Required Fixes (if any)

None.

### Low-risk findings presented to the user

None meet the bar for the risk-communication format — every candidate above resolved to "no
finding" on inspection, and the one accepted gap (`UNKNOWN`'s missing qualifier) was already
raised, reasoned about, and resolved by the user in the plan itself (`plan.md`, Decisions
Requiring User Input, #6), not newly surfaced here.
