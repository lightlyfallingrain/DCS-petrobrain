## Security Deep Analysis: rule-collision-misheard

### Dependency Status
No dependency change. Pure logic change in `audio-adapter/src/rule_patterns.py` (one new
keyword-only `bool` parameter threaded through `_is_genuine_collision`/`_collides_with_legacy`) plus
tests. No new imports, no new third-party package, no new network/file/process call.

### Scope and threat framing
`PUT /rules` (`audio-adapter/src/server.py`) is the LAN-facing endpoint this fix touches indirectly:
it's what calls `compile_rules` -> `_collides_with_legacy` -> `_is_genuine_collision`. Per this
project's threat model (single-user, LAN-only; realistic attackers are a malicious dependency or an
infected LAN host scanning/probing ports), the question that matters here is whether loosening the
rule x legacy collision check lets a spoken utterance resolve to an unintended command with false
confidence — a "confident wrong command" — or widens what an unauthenticated LAN caller of
`PUT /rules` can get accepted into live effect.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `audio-adapter/src/rule_patterns.py:1062` (`return confident_loss_disables`) | Collision-check gating changed from always-disable to conditional-disable for the rule x legacy pass | Not exploitable as a "confident wrong command": `command_matcher.match_transcript`'s rule/legacy merge (`src/command_matcher.py:1166-1182`) already picks the higher-`match_ratio` branch at runtime whenever both a rule and legacy resolve, independent of whether the rule exists in the registry at all. So for the exact mis-hearing this flag governs, keeping the rule accepted changes nothing about which command actually fires — the Reviewer's independent verification of that merge logic (`review.md` lines 17-23) is correct and I re-read the same call chain and agree. The change only restores correct recognition on the rule's *clean* wording, which is the intended fix. | None |
| `audio-adapter/src/rule_patterns.py` (whole diff) | New parameter is a plain `bool`, no new input validation surface | `confident_loss_disables` is caller-supplied internally (`_rules_collide` keeps the default `True`; `_collides_with_legacy` hardcodes `False`) — never derived from request data, so there is no path for a `PUT /rules` payload to flip this flag itself. The attacker-controlled inputs into this function (`other_ratio`, `sample`, ids) are unchanged from before the fix; the diff only changes what the function *does* with an existing comparison, not what data reaches it. | None |
| `audio-adapter/src/server.py` `PUT /rules` (pre-existing, unchanged by this diff) | Unauthenticated LAN endpoint, no body-size bound reviewed here | Pre-existing, not touched by this diff, and already documented and accepted in `audio-adapter/CLAUDE.md` ("the default is deliberately left on loopback... `/speak`/`/transcribe`/`/stop` carry no authentication"). This fix does not change reachability, authentication, or validation of `PUT /rules` — it changes only which *otherwise-valid* rules get accepted once a payload is already parsed. Not a finding against this feature; noted only to record that it was considered and ruled out as in-scope here. | None — pre-existing, accepted elsewhere |
| `audio-adapter/tests/test_rule_patterns.py`, `test_rules_api.py` | Test-only changes | No production code path, no security content. | None |

**On "widening what gets accepted":** the loosened check does let more rules pass `PUT /rules`'s
collision gate than before (any rule whose only legacy collision is a confident loss on a perturbed
sample, not an exact tie). This is true regardless of whether the pusher is the legitimate body-layer
process or a hostile LAN host exploiting the endpoint's lack of authentication. However, the worst
outcome of an accepted-but-malicious rule is bounded by what `compile_rules`/`match_transcript` can
do with it: a pattern-to-id mapping that, if it matches a transcript, returns that id/ratio to whoever
polls `GET /transcripts/poll` (body-layer). It is not code execution, not a file-system write, and
not a path that can forge a *higher*-confidence resolution than the real legacy/rule comparison
already allows (the merge logic is unchanged by this diff and was not touched). So this loosening
does not create a new "confident wrong command" primitive — it only accepts rules that are, by this
project's own definition (U10), not genuine collisions. The pre-existing lack of `PUT /rules`
authentication is the actual vector for a hostile push, and that is unchanged and already accepted
project-wide, not introduced or expanded by this fix.

### Verdict
APPROVED

### Required Fixes (if any)
None.

### Not filed, intentionally
- The `PUT /rules`/`/speak`/`/transcribe`/`/stop` lack-of-authentication posture is pre-existing,
  already documented and accepted in `audio-adapter/CLAUDE.md` ("Running the server" section), and
  unaffected by this diff. No new backlog item filed for it here — it is a standing, named design
  decision, not a finding against `fix/rule-collision-misheard`.
- The Reviewer's two "Optional Refinements" (plan.md D9 staleness note; a missing `DEBUG`/`INFO`
  log line on the now-silent confident-loss-but-kept path) are observability/documentation items,
  not security findings — left to the Reviewer's own report, already on file at
  `plans/rule-collision-misheard/review.md`, not duplicated here.

### Passed to Reviewer
None — no player-facing correctness observation beyond what the Reviewer's own report already
covers.
