## Security Deep Analysis: radio-check (BL-B82 + BL-B81)

Batch: `feature/radio-check`, diff base `main`@`d1126570`, tip `2f1c8d8c` (fast-forwarded into this
worktree; no fixup needed — tree was already clean and an ancestor of the tip). Covers plan +
implementation + review for both backlog items, since no separate Mode 1 plan review ran for this
small batch (per the dispatch instruction).

### Dependency Status

No dependency change. The new code imports only stdlib `re` and this subproject's own existing
`tuning` module (already a declared internal mechanism, not a new package). `extract-plan-deps` was
not run — `plan.md` proposes no new dependency and nothing in the diff (`crew_console.py`,
`speech.py`, `logger.py`, `vocabulary.py`, `command_matcher.py`) adds an import outside each
subproject's existing stdlib-only policy.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/belief/speech.py:408-420` (`render_greeting`) | Slot value → spoken text | `time_of_day` is looked up in a 4-key fixed dict via `.get(time_of_day, _GREETING_TEMPLATES["day"])`. No f-string/concatenation of caller-supplied text into the spoken line is possible — an unrecognised key degrades to a fixed fallback string, never to raw input. Confirmed by reading the function body directly, not the report's paraphrase. | None |
| `body-layer/src/belief/crew_console.py:2804-2812` (`_handle_greeting`) | Slot validation before render | `time_of_day` is checked against `_GREETING_TIMES_OF_DAY` (`frozenset({"morning","day","evening","night"})`) before `render_greeting` is ever called; an unrecognised/missing value returns a literal `"say again -- no greeting heard"` string and never reaches `render_greeting`. This is a second, independent gate on top of speech.py's own fallback — double-gated, not single-point-of-failure. | None |
| `body-layer/src/belief/crew_console.py:260-270` (`_match_radio_check_or_greeting`) | Crew-text (typed) slot extraction | `_GREETING_PATTERN = r"^good\s+(morning|day|evening|night)\s+petrovich\.?$"` — the captured group is itself restricted to the four alternatives by the regex alternation; `.group(1).lower()` cannot produce a fifth value. Anchored `^...$`, case-insensitive, no nested quantifiers — no ReDoS shape. | None |
| `audio-adapter/src/vocabulary.py:1126-1134` (`parse_time_of_day`) | Voice slot extraction | Returns only a `TIME_OF_DAY_WORDS` member (the same four strings) or `None` — a whole-word set-membership test against the normalised transcript, not a substring/capture of raw speech. The voice path cannot inject anything beyond the four fixed words either. | None |
| `body-layer/src/logger.py:320-330`, `:684-696` (`PerceptionLogger.run_once`, `ConsolePerceptionRunner.run_once`) | New conditional gating observation collection on `ownship.alt_agl_m > ON_GROUND_AGL_THRESHOLD_M` | Simple float comparison against a tunable bound (`lo=0.5, hi=50.0`, AST literals — confirmed in the diff, not re-derived). `ContactStore.tick`/`ingest([], ...)` still run unconditionally, so belief decay is unaffected — matches the plan's explicit intent ("existing belief is kept"). No overflow/off-by-one surface: this is a threshold gate, not an index or buffer computation. Fails toward the safe direction (missing/zero `alt_agl_m` reads as "on the ground", i.e. no scanning), consistent with the Reviewer's own finding. | None |
| `body-layer/src/belief/crew_console.py:1236-1246` (`on_ground: bool = field(default=True, ...)`) | Default value change (review fix) | Defaults to `True` (fail toward refusing a look command) rather than `False`. This is the conservative direction for an unknown/pre-telemetry state — narrows the review's own flagged window rather than widening any risk. | None |
| `body-layer/src/belief/crew_console.py:1636-1642` (`handle_command`'s on-ground branch) | New refusal branch | Runs after the existing world-model refusal check and after the silence-ends-on-any-command reset, matching the stated ordering in plan/implementation. No new command token bypasses existing refusal-mode handling — `radio_check`/`greeting` go through the same `handle_command` entry point as every other token, so BL-15's refusal mode and the on-ground gate both still apply to them where relevant. | None |
| `audio-adapter/src/command_matcher.py:771-791` (new `greeting` branch) | New dispatch branch ordering | Placed after the `engage` branch, before the generic phrase table, mirroring existing slotted-token branches (`follow`/`report`/`engage`). `"good"`'s fuzzy-anchor ratio against the pre-existing anchor set is at `VERB_FLOOR` exactly (measured by the implementer, cross-checked: `difflib.SequenceMatcher(None, "good", "look").ratio() == 0.5`) — this is the same accepted risk class as other short ordinary-English anchor words already in this file (`look`/`watch`/`report`/`scan`), not a new exploitable gap; the phrase-scoring pass is the real defence and is exercised by `test_good_job_degrades_rather_than_falsely_resolving_a_greeting`. No action — same risk posture as the rest of the vocabulary file. | None |

No file-system path construction, no new deserialization, no new network input surface (both new
tokens ride the existing F10/voice/crew-text transports and the existing `/speak`/`/transcripts`
seams, token-agnostic per the implementation report's own check of `server.py`), no new external
command execution, and no new credential-shaped literal.

**Single-player/LAN-only scope note (per root `CLAUDE.md`):** even if the double-gating above were
somehow bypassed, the only consequence would be a TTS line played to the one local pilot over a LAN
voice pipe already trusted for every other spoken line this system produces — not a cross-process or
cross-user exposure. Severity is calibrated accordingly; this is not a reason the gating analysis
above was skipped.

### Verdict

APPROVED

### Required Fixes (if any)

None.

### Findings Ledger (per role's closing-step rule)

No finding in this pass rose above "no action required" — every row in the table above resolved to
`None`. There is therefore nothing to file as a backlog item and nothing presented as a risk-matrix
option to the user: **not filed, intentionally** — no open finding exists to carry an ID. (This
differs from the plan-review mode's Dependency/Design-Finding sections, which don't apply here since
Mode 1 did not run separately for this batch; its ground is covered above under "Dependency Status"
and the design-level points already settled by the plan's own stated decisions, which this pass did
not find reason to re-open.)
