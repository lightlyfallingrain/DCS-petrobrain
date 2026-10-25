## Security Deep Analysis: 9k113-scan-procedure (BL-B89 batch — BL-B98 fix + Stage 2)

Base check: this worktree's own prior HEAD (`8b21e866`, scaffolding from an earlier agent run in
this worktree) was **not** an ancestor of the named tip `627ab398b074b308f90ba4ec023edb765ecdd25e`
— reported as a mismatch per rule 4. Detached to the named tip directly (`git checkout --detach`);
tree confirmed clean both before and after.

Covers two pieces whose own security pass was deferred to this batch by user direction:
- the BL-B98 fix (`23898e70^..01a6fadd`, folded into this feature branch at `4dccaa6c`)
- Stage 2 (`8f5d2ade..627ab398`, including the review fix at `627ab398` for Required Fix 1)

Stage 1 had its own security pass (`plans/9k113-scan-procedure/security.md`, APPROVED) and is not
re-litigated here except where Stage 2/the BL-B98 fix touch the same code.

### Dependency Status

No dependency change. Every changed file is Python within `audio-adapter/src/{vocabulary.py,
command_matcher.py}` and `body-layer/src/{belief/optic_policy.py, belief/crew_console.py,
belief/speech.py, belief/voice_commands.py, body.py, perception/gaze.py}`, plus tests and the
generated `config/defaults.toml`. Grepped both diffs (`23898e70^..01a6fadd` and `8f5d2ade..627ab398`)
for `eval(`, `exec(`, `subprocess`, `os.system`, `socket`, `pickle`, `__import__`, `requests.`,
`urllib`, `open(`, `yaml.load`, `marshal`, `shell=True` — zero hits in either. No new `import` line
introduces a package; `extract-plan-deps`-equivalent grep over `plan-stage2.md` (already run for the
plan review, security-plan-stage2.md) found nothing new, confirmed unchanged against the actual diff.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| — | No in-scope pattern in either diff (no exec/eval/shell-out, no new fs/socket surface, no deserialization, no secrets, no DCS-install-path or `.miz` reference) | Confirmed by grep over the full diff, not just the plan's description | None |
| `body-layer/src/belief/crew_console.py` (confirm-affirm block, `handle_transcript`) | New `observ_request`-scoped "yes" branch | Read against the actual code (not just the plan review's claim): the branch body is exactly `self.handle_command("observ_on", ...)` (a hardcoded literal token, never derived from the transcript) followed *conditionally* — only if `self.sight_ready` after that call — by `self.pending_point_request = PendingPointRequest(slots=pending.observ_request, ...)`, where `observ_request` is the dict captured when `look <where>` was first parsed, not re-parsed from the affirming utterance. No other effector or dispatch path is reachable from this branch. Confirms security-plan-stage2.md's design-time claim against the shipped code. | None |
| `body-layer/src/body.py:_sight_point_sweep` | New geometry helper feeding the sequence engine | Reuses `search_pattern` + `within_field_of_regard` (the same field-of-regard enforcement `_sight_in_regard_sweep` already applies) and returns only `(azimuth, elevation)` float tuples — pure geometry, no new write path into the effector/sequence engine, no new command surface. | None |
| `body-layer/src/body.py:_apply_point_request_transition` (review fix, `627ab398`) | `OpticState` field reset scoped by whether a bounded look clock is actually in play | Pure in-process dataclass `replace()` over already-bounded belief state (contact ids, sim-time floats, enum phases) — no externally reachable input, no new attack surface. This is the Reviewer-caught correctness bug (unrelated mid-look abandonment) fixed between `d0b58959`/`627ab398`; correctness-only, no security implication. | None (already Reviewer's/DoD's territory) |
| `audio-adapter/src/{vocabulary.py,command_matcher.py}` | New `point`/`what` slot parsing | All new slot-producing functions (`parse_clock`, `parse_range_km`, `parse_sector_word`, `parse_relative_word`, `_parse_point_slots`) are closed-vocabulary table lookups or a pre-bounded `1<=value<=20` integer range check — re-confirmed against the shipped code, matching security-plan-stage2.md's design-time analysis exactly. No numeric parsing path that could carry a huge/negative/NaN value reaches any downstream consumer. | None |
| — | LLM prompt injection | No new path from spoken-transcript free text into a brain-layer prompt. `match_transcript`/slot resolution stays entirely deterministic/closed-vocabulary; `drain_brain`/`poll_replies()` references in the diff are pre-existing and unrelated to this command surface. | None |

### Tunable Bounds

Three new tunables in `belief/optic_policy.py`, all AST-literal `lo`/`hi`, all rendered correctly
in `body-layer/config/defaults.toml` (checked the rendered file, not just the source `#:` comment):

| key | default | lo | hi |
|---|---|---|---|
| `POINT_SWEEP_COUNT` | 2 | 1 | 5 |
| `POINT_READY_TIMEOUT_S` | 5.0 | 2.0 | 30.0 |
| `POINT_DISTANCE_BAND_HALF_KM` | 1.0 | 0.25 | 3.0 |

All three are local-config-only (`config/tuning.toml`, edited by the single user on their own
machine — not externally reachable by network input, mission data, or any untrusted source).
Worst case of a pathological value, per security-plan-stage2.md's own assessment and confirmed
against the shipped bounds: a long-running or slow-to-clear bounded look, not a crash, not a
listener change, not privilege escalation — a correctness/availability-of-the-cockpit concern
under this project's single-user/LAN threat model, not a security finding. No cross-key coupling
risk analogous to Stage 1's `SIGHT_SEARCH_*` bands exists here — the three keys are independent
(sweep count, a timeout, a distance half-width) with no shared band geometry between them.

### Surface Check

- **LAN port-scanner surface** — unchanged. No new listener, endpoint, or socket in either diff.
  `audio-adapter`'s existing `POST /transcribe` boundary (already reviewed) is unaffected in kind;
  this batch only changes what `match_transcript` can return.
- **Access to the computer** — unchanged. No new file I/O, no path built from received/spoken data.
  `config/defaults.toml` regeneration is the existing `tools/generate_defaults.py --write` mechanism.
- **No ED source and nothing under `$DCS_INSTALL_PATH`** — grepped both diffs for `install`,
  `DCS_INSTALL`, `Saved Games`, `.miz`, `open(`, `Path(` — zero hits.
- **Arbitrary code execution / deserialization** — none in either diff (grep above).
- **Secrets/credentials** — none introduced or referenced.

### Passed to Reviewer

Not security findings, carry no verdict here (already disposed by Reviewer/Debugger in
`review-stage2.md`/`debug-bl-b98.md`, noted only for completeness):
- Whether the resumed-at-last-position belief (BL-B98 fix) reads correctly to the pilot in flight —
  a correctness/perception question, explicitly left for flight in `debug-bl-b98.md`.
- The relative-vs-bounded clock/compass asymmetry and the "ready" (`sight_ready` vs. `home_phase is
  SIGHTING`) resolution — already resolved and tested per `implementation-stage2.md`.
- `POINT_SWEEP_COUNT`/`POINT_DISTANCE_BAND_HALF_KM` default-value/bound sensibleness — a
  gameplay-pacing judgement, not a security bound.

### Verdict

APPROVED
