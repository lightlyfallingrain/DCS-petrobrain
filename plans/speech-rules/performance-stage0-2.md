### Performance Review

**Scope:** BL-17 Stages 0–2 (`feature/speech-rules`, tip `1f5fa7ae`, fast-forwarded cleanly from
this worktree's prior `6fb23698` — strict ancestor, clean tree). The Lua rule engine
(`body-layer/src/rules/{sandbox,loader,engine,actions}.py`), its wiring into `crew_console.py`/
`body.py`, and the adapter-side grammar/matcher/collision-check seam
(`audio-adapter/src/rule_patterns.py`, `command_matcher.py`'s rule branch, `server.py`'s
`PUT /rules`, the dynamic whisper prompt). One rule shipped (`config/rules/flight.lua`,
`turn_heading_relative`).

**Target, from the task and `CLAUDE.md`:** no hard real-time budget yet (Runtime work hasn't
started), but the user's own reason for fixed wording — *"to get the deterministic (=fast) path,
I use fixed wording"* — means the latency from push-to-talk release to Petrovich acting on a
matched command must not grow noticeably as more rules are ported (plan's own stated eventual
scale: all ~80–100 existing commands become rules, U6).

**Method:** built fresh venvs for both subprojects (`/opt/homebrew/bin/python3.14`, none existed
in this worktree) and measured every hot path named in the task directly, rather than reasoning
about Big-O alone — `functools`-free microbenchmarks against the real shipped code, at 0/1/10/50/
100/200 synthetic rules (100 is the plan's own stated eventual scale; 200 is 2× that, to see the
trend continue). Numbers below are medians of 7×2000-call runs (or 7×5000 for the Lua dispatch
check), `/opt/homebrew/bin/python3.14`, this machine.

### Findings

#### `match_transcript`'s per-transcript cost scales linearly with active rule count, for every transcript that does *not* match a rule

- **Location:** `audio-adapter/src/command_matcher.py::match_transcript`, specifically
  `_match_rules` (iterates every active rule, `sorted()` + a fresh `match_pattern` attempt per
  rule) and `_rule_anchor_words` (rebuilds the rule-literal anchor set from scratch every call).
- **Measured** (synthetic rules, each a distinct first literal — the worst case for anchor-set
  growth):

  | active rules | free-speech (no match), µs | rule hit, µs | legacy phrase-table hit, µs |
  |---|---|---|---|
  | 0 | 827.7 | — (n/a) | 1383.8 |
  | 1 | 832.8 | 10.8 | 1394.0 |
  | 10 | 859.4 | 12.1 | 1448.8 |
  | 50 | 986.7 | 18.0 | 1700.2 |
  | **100** (plan's own eventual scale) | **1138.5** | 25.2 | **2007.2** |
  | 200 (2× that) | 1447.1 | 40.0 | 2626.3 |

  So: a transcript that *does* match a rule stays cheap (10–40 µs even at 200 rules — full-
  consumption exact-literal matching is genuinely fast). A transcript that falls through to the
  legacy matcher or to free speech pays an extra ~3–6 µs per *loaded* rule regardless of whether
  it ever matches one, because `_match_rules` tries every active rule's pattern before giving up,
  and `_rule_anchor_words` rebuilds its set from the whole rule list every call (confirmed in
  isolation: 0.13 µs at 0 rules → 9.45 µs at 100 → 17.79 µs at 200 — small on its own, so the bulk
  of the ~300–600 µs growth above is the `_match_rules` loop itself, including its
  `sorted(rules, key=lambda r: r.id)` call on a tuple that `compile_rules` already hands over
  sorted).
- **Risk:** today (one rule shipped) this is invisible. Once Stage 4+ ports the ~80–100 commands
  U6 calls for, *every* legacy-matched command and *every* piece of free speech pays this
  overhead on top of the matcher's own existing cost (measured elsewhere at 100–800 µs per call,
  `[[project_slot_branch_beats_phrase_table]]`). At 100 rules that is roughly +0.3–0.6 ms; at 200
  it is +0.6–1.6 ms. **Not credible as a budget violation**: `/transcribe` runs once per
  push-to-talk release (human-paced, not per-poll), and the very next step after `match_transcript`
  returns is a `whisper-cli` subprocess invocation that itself costs hundreds of milliseconds to
  low seconds — a sub-2-ms addition on top of that is not something a pilot could notice. It *is*
  a genuine, measured, linear-in-rule-count cost that will keep growing as the project ports the
  rest of the vocabulary, and it is exactly the anti-pattern this same file's own
  `VERB_ANCHOR_WORDS`/`_PHRASE_INDEX` already avoid (computed once at import time, with a comment
  citing this project's own `world-model` Transformer-cost lesson) — `_rule_anchor_words` breaks
  that precedent for the one new input (the active rule set) that changes far less often (once per
  `PUT /rules`) than it is recomputed (every transcript).
- **Action:** MONITOR. Not required now — no credible path to a noticeable latency regression at
  the stated scale, and the one shipped rule's own dispatch is unaffected.
- **Suggestion (cheap, matches existing convention):** cache `_rule_anchor_words(rules)` and the
  rules tuple's sorted-by-id order at the point `rules` is swapped in (`RuleRegistry`'s one
  assignment point, D8's own "swapped in with one assignment" design already gives a stable,
  versioned object to key a cache off), not recomputed per transcript. `CompiledRule` is already a
  frozen dataclass of hashable fields, so `functools.lru_cache` keyed on the `rules` tuple itself
  would also work without restructuring `RuleRegistry`. Worth doing opportunistically when Stage
  4+ is implemented, not worth a standalone change now for one rule.

#### The whisper prompt is rebuilt from scratch on every `/transcribe` call, not cached against the rule version that actually changes it

- **Location:** `audio-adapter/src/audio_adapter/__main__.py`'s `_rule_prompt_provider` →
  `vocabulary.recognised_words`/`to_prompt`, resolved fresh inside `WhisperCliEngine.transcribe`
  on every call (`stt_engine.py:214`), per D10's own design ("a rule pushed mid-sortie changes the
  prompt whisper actually sees on the very next recognition without this engine being
  reconstructed"). Before this plan, the prompt was a fixed string built once at process startup.
- **Measured** (`to_prompt()` alone, the actual function called per `/transcribe`):

  | rule words supplied | time, µs | resulting prompt length |
  |---|---|---|
  | 0 | 109.1 | 142 words |
  | 300 (≈100 rules × 3 words) | 215.0 | 143 words |
  | 600 (≈200 rules × 3 words) | 324.9 | 143 words |

  (The flat word count across tiers is this synthetic bench's own artifact — the synthetic
  literals collapse under `recognised_words`' `[a-z']+` regex, which strips digits; the *timing*
  still correctly reflects the full per-call recomputation cost regardless.) The function always
  re-walks the full static legacy vocabulary (~80 tokens' phrasings, ~142 words) plus whatever
  rule words are active, every single call.
- **Risk:** same shape as the previous finding — a per-utterance recomputation of something that
  is overwhelmingly static (the legacy vocabulary never changes at runtime; only the rule-word
  tail does, and only on a `PUT /rules`). Measured cost (109–325 µs) is three-plus orders of
  magnitude below the whisper-cli subprocess call that immediately follows it, so **not a credible
  latency risk** at any rule count this project is heading toward. Whisper's own transcription
  time is also architecturally insulated from rule-word growth: the prompt is hard-capped at
  whisper's own ~224-token context window (D10/R3), so past that cap extra rule words are silently
  dropped rather than making whisper itself slower — the real cost of overflow is a recognition-
  quality regression (R3, already flagged), not a latency one.
- **Action:** MONITOR, for the same reason as the previous finding.
- **Suggestion:** if this is ever revisited, cache the legacy-vocabulary word list once (it is
  genuinely constant) and only re-derive the rule-word tail keyed on `RuleRegistry.version`, which
  already exists and already changes exactly when the answer should. Not required for Stage 1b/2's
  one rule.

#### `compile_rules`'s collision check is confirmed super-linear, but bounded and load-time-only

- **Location:** `audio-adapter/src/rule_patterns.py::compile_rules`, the rule×rule pass (D9 step
  1): an `O(n²)` pass over every accepted-rule pair, each pair running up to 2×2 `match_pattern`
  attempts (`_rules_collide`).
- **Measured** (real `compile_rules`, synthetic non-colliding rules, including the real
  `_legacy_probe`-shaped injection):

  | rules | wall time |
  |---|---|
  | 1 | 0.34 ms |
  | 10 | 2.67 ms |
  | 50 | 16.84 ms |
  | **100** | **41.83 ms** |
  | 200 | 118.05 ms |

  Confirmed super-linear (doubling 100→200 rules costs 2.8×, not 2×) but far short of a runaway —
  bounded because `generate_samples` caps each rule at ≤2 samples (D9's own "collapsed to these two
  extremes" scoping) rather than a combinatorial explosion.
- **Risk:** this runs only at body-layer startup and at a genuine DCS mission (re)start (U11's
  reload), never per-poll and never per-transcript. 42 ms at the plan's own stated eventual scale
  (100 rules), 118 ms at 2× that — imperceptible against a mission-restart event that already
  involves DCS-side state reset, and explicitly called "acceptable at load time" by the plan
  itself. Not a credible risk at this stage's scale. `[[BL-B95]]`'s later "mission rules added to
  the common set" could push `n` meaningfully higher (strangers' scripts, per-mission additions
  stacked on the ~100 base rules) — already named by the plan as that milestone's own concern, not
  this one's.
- **Action:** MONITOR, deferred to `[[BL-B95]]` as the plan already does. No action now.

#### Mission-(re)start reload adds one more synchronous, timeout-bounded network call to an already-documented poll-thread blocking class

- **Location:** `body.py`'s `_check_for_new_mission` → `_load_rules` (bounded, measured above) →
  `_push_rules` (`PUT /rules` via `AudioAdapterClient.put_rules`, `timeout_s=5.0` default,
  `belief/audio_client.py`). Also reachable on an ordinary poll on a `rules_version` mismatch
  (D2's re-push), not only at mission restart.
- **Risk:** this is the *same risk shape* this project's own memory already documents and accepts
  for the existing aircraft-layer GETs on the poll thread (`[[project_body_layer_poll_loop_diagnosis]]`:
  "5 aircraft-layer GETs ... 2.0 s timeout each = 10 s worst case"). BL-17 adds one more
  synchronous, blocking call with its own 5 s worst case to that same budget, bringing the
  mission-restart worst case to ~15 s if the adapter happens to be unreachable at exactly that
  moment. This is additive to a pre-existing, already-known pattern, not a new problem class, and
  it fires only on a rare event (mission restart, or an adapter restart/version mismatch) — never
  every poll.
- **Action:** MONITOR. Worth remembering if the aircraft-layer timeout budget is ever revisited as
  its own item, but not a reason to hold up this diff — the existing pattern already absorbs
  exactly this kind of addition without a mission-restart SLA anywhere in the project.

#### Lua dispatch itself (handler call + instruction-budget hook) — measured, negligible

- **Location:** `body-layer/src/rules/engine.py::run_rule` → `sandbox.py::run_with_budget`
  (`debug.sethook` armed/disarmed around every dispatch).
- **Measured** (isolated lupa runtime, the real shipped mechanism — `debug.sethook(..., "", 1000)`
  wrapped in the one-line Lua shim the Stage 0 research note found necessary, running the real
  `flight.lua`-shaped handler):

  | | median µs/call |
  |---|---|
  | handler call, with the budget hook armed+disarmed | 3.39 |
  | same handler, no hook armed | 0.61 |
  | hook arm/disarm overhead | ~2.78 |

- **Risk:** none at any realistic rule count — this cost is per-*dispatch* (one Lua call per
  spoken command actually acted on), not per-rule-loaded, so it does not scale with how many rules
  exist, only with how often a command is spoken. 3.4 µs is immeasurably small next to the rest of
  the pipeline.
- **Action:** none. Confirms the Reviewer's own "no new unbounded loop or per-poll allocation
  found" with a real number rather than architecture-only reasoning.

#### Nothing was added to the steady-state poll loop beyond O(1) checks

- **Location:** `body.py`'s poll body gained: `_poll_transcripts` returning one extra
  already-present HTTP response header (`rules_version`, no new request), and one string
  comparison (`rules_version != rule_runtime.adapter_accepted_version`) that only does real work
  (the `_push_rules` call analysed above) on a mismatch. `drain_action_file_error` is one more
  boolean-flag check, same O(1) shape as the pre-existing `drain_config_error`.
- **Risk:** none. This matches the task brief's own expectation ("anything added to body-layer's
  poll loop should be nothing — flag it if there is") — there is effectively nothing beyond a
  header read already riding the existing poll and a cheap comparison.
- **Action:** none.

### Verdict

**PASS**

No required changes. Every hot path named in the task brief was measured directly against the
real shipped code, not estimated: the one real, credible, *scaling* cost (rule count growing
`match_transcript`'s per-transcript overhead linearly, and the whisper-prompt rebuild cost with
it) is real and worth fixing cheaply — but it is three-plus orders of magnitude below the
whisper-cli subprocess call that dominates this pipeline's actual latency, and the project's own
stated eventual scale (U6's ~80–100 rules) keeps it under ~2 ms even in the worst case measured
(200 rules, 2× that scale). Nothing here credibly threatens "the latency from push-to-talk release
to Petrovich acting on a matched command must not grow noticeably" at the scale this plan actually
targets. Flagged as MONITOR items for whoever implements Stage 4+, where rule count actually grows
from today's one toward the planned ~80–100 and the two caching opportunities (rule-anchor-word
set, whisper-prompt legacy-word base) become worth taking rather than premature.
