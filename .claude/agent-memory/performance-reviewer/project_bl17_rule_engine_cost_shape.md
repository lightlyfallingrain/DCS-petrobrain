---
name: bl17-rule-engine-cost-shape
description: BL-17 Stages 0-2 (Lua rule engine for spoken commands) measured hot-path costs -- all negligible against whisper's own transcription latency. SUPERSEDED IN PART by [[bl17-stage3-4-cost-shape]] -- the two caching fixes named below shipped in Stage 3a (D15) and are confirmed fixed, but the "a rule hit stays cheap, 10-40us" line is now STALE (D13 removed the early-return this depended on) and the collision check gained a real, un-mitigated 66-107x regression. Read the superseding file first.
metadata:
  type: project
---

**UPDATE 2026-11-17 (Stage 3-4 batch review): two of this file's own claims are now stale.** See
`[[bl17-stage3-4-cost-shape]]` for the corrected numbers and the one real regression found in this
batch. Specifically:
- The "transcript that *does* hit a rule stays cheap throughout (10-40 us even at 200 rules)"
  claim below (bullet 1) no longer holds -- D13 (Stage 3a) removed the early-return on a rule hit,
  so a hit now pays the same ~1-2ms the free-speech/legacy-hit cases already paid. Still negligible
  against whisper-cli, just not for the reason originally stated.
- The "`rule_patterns.compile_rules`'s rule x rule collision check (D9) is confirmed super-linear
  but bounded" claim (bullet 4, 42ms @ 100 rules, 118ms @ 200) is also stale -- D13's own
  perturbed-sample mechanism, added in the same stage this file predates, made it 66-107x worse
  (2.8-3.1s @ 100, 12.6s @ 200) via an avoidable per-pair recomputation, now flagged NOW/Required
  Fix in `plans/speech-rules/performance-stage3-4.md`.
- The two caching fixes this file names as "cheap fix when it's worth doing" (bullets 2 and 3 --
  `rule_anchor_words` at the `RuleRegistry.swap` point, and the whisper prompt keyed on
  `registry.version`) **did ship**, in Stage 3a (D15), and are confirmed fixed by direct test, not
  just by reading the docstring that claims it.

Original text below, unmodified except for this update block (a correction sweep, not a rewrite --
the original numbers were real measurements of the code as it stood at `1f5fa7ae`, before D13).

---

Measured 2026-11-17, `feature/speech-rules` @ `1f5fa7ae` (Stages 0-2), fresh venvs
(`/opt/homebrew/bin/python3.14`), real shipped code. Full report:
`plans/speech-rules/performance-stage0-2.md`.

## The one thing worth remembering: everything here is dwarfed by whisper-cli itself

`audio-adapter`'s `/transcribe` runs once per push-to-talk release (human-paced), and always ends
in a `whisper-cli` subprocess call costing hundreds of ms to low seconds. Every cost measured in
this pass tops out in the **low single-digit milliseconds** even at 200 synthetic rules (2x the
plan's own stated eventual scale of ~80-100, U6). None of it is a credible latency risk at this
project's actual target scale -- but see below for what *does* scale and is worth a cheap fix
before rule count climbs.

## Measured numbers (worth citing directly rather than re-deriving)

- **`command_matcher.match_transcript`** grows ~3-6 us per *loaded* rule for every transcript that
  does **not** match a rule (legacy hit or free speech) -- `_rule_anchor_words` and `_match_rules`'
  `sorted()` call both recompute from scratch every call instead of caching against the rule set's
  own stable identity. At 100 rules: +300 us (free speech) to +620 us (legacy hit). At 200: +600 us
  to +1.24 ms. A transcript that *does* hit a rule stays cheap throughout (10-40 us even at 200
  rules) -- full-consumption exact-literal matching (`rule_patterns.match_pattern`) is genuinely
  fast; the cost is in trying every rule when none of them is the one that matches.
- **This is exactly the anti-pattern `command_matcher.py`'s own `VERB_ANCHOR_WORDS`/`_PHRASE_INDEX`
  already avoid** (computed once at import time, citing this project's own `world-model`
  Transformer-cost lesson in the comment) -- `_rule_anchor_words(active_rules)` breaks that same
  precedent for the one input that changes far less often (once per `PUT /rules`) than it is
  recomputed (every transcript). Cheap fix when it's worth doing: cache keyed on the `rules` tuple
  itself (`CompiledRule` is a frozen, hashable dataclass, so `functools.lru_cache` works directly)
  or at `RuleRegistry`'s one swap-in assignment point.
- **The whisper prompt provider (`_rule_prompt_provider` in `__main__.py`) rebuilds the *entire*
  prompt -- the full static ~80-token legacy vocabulary plus active rule words -- on every single
  `/transcribe` call**, not just on a rule push, because `WhisperCliEngine.transcribe` resolves its
  prompt callable fresh every call (D10's own design, so a mid-sortie rule push takes effect
  immediately). Measured 109 us (0 rule words) to 325 us (600 rule words, ~200 rules). Whisper's
  own transcription cost is architecturally insulated from this growth regardless -- the prompt is
  hard-capped at whisper's ~224-token context, so past that, extra words are silently dropped
  (a recognition-quality risk, already flagged in the plan as R3) rather than making whisper
  itself slower. Cheap fix if revisited: cache the legacy-vocabulary word list (genuinely
  constant) and only re-derive the rule-word tail keyed on `RuleRegistry.version`.
- **`rule_patterns.compile_rules`'s rule x rule collision check (D9) is confirmed super-linear but
  bounded**: 0.34 ms @ 1 rule, 42 ms @ 100, 118 ms @ 200 (doubling 100->200 costs 2.8x, not 4x --
  `generate_samples` caps each rule at <=2 samples, so no combinatorial blowup). Load-time only
  (startup + mission restart via U11's reload), never per-poll, never per-transcript. Acceptable
  at the plan's own stated scale; `[[BL-B95]]` (strangers' mission-stacked rules) is where this
  would need revisiting, already named by the plan as that milestone's concern.
- **One real Lua dispatch (handler call + `debug.sethook` instruction-budget arm/disarm, the real
  shipped mechanism) measured at 3.39 us/call** (vs. 0.61 us with no hook armed -- ~2.78 us is the
  hook's own overhead). This scales with how often a command is *spoken*, not with how many rules
  are *loaded*, so it never grows with rule count the way the matcher-side costs do. Negligible at
  any realistic frequency.
- **Mission-restart reload adds one more synchronous, timeout-bounded (5 s default) `PUT /rules`
  call on the poll thread**, additive to the already-documented aircraft-layer-GET blocking budget
  ([[project_body_layer_poll_loop_diagnosis]]: "5 GETs, 2.0 s timeout each = 10 s worst case" at
  mission restart). Same risk shape this project already accepts for that event, not a new
  pattern -- now ~15 s worst case combined, still only at a rare, already-tolerated event.

## Measurement technique notes (useful for the next adapter-side rule-count bench)

- `audio-adapter` has no third-party deps, so a bare venv + `PYTHONPATH=src` is enough to
  microbenchmark `command_matcher`/`rule_patterns`/`vocabulary` directly with real shipped code.
- A synthetic rule's literal word built as `f"zrule{i}"` collapses under
  `vocabulary.recognised_words`'s own `[a-z']+` regex (digits stripped), so every synthetic rule's
  literal collides into one word after extraction -- fine for *timing* `to_prompt`/
  `recognised_words` (the function still does the O(n) work regardless), but do not read the
  *word-count* column of such a bench as real vocabulary growth; it will stay flat where real
  distinct-word rules would not.
- `lupa` installs cleanly from PyPI for `cp314-macosx_arm64` (version `2.8`, per Stage 0's own
  research note) -- a minimal lupa-only venv (no full body-layer dependency chain) is enough to
  bench the Lua dispatch mechanism in isolation; no need to build the whole `body-layer/.venv`
  (world-model seam, `pyproj`, etc.) just to time `debug.sethook` overhead.
