# Speech word fixes from the Stage 3c corpus bench (`[[BL-B129]]`)

**Written by the main loop from the user's own direction, 2026-11-18** — not an Architect pass: the
behaviour is fully specified by the user's four answers below, and the change is local to the
matcher, the prompt and one rule file. Goal-aligner skipped for the same reason (the user stated
the expected behaviour directly). Explore happened in conversation: the bench was run, shown, and
these answers came back.

Evidence: `audio-adapter/research/2026-11-18-state-hint-bench.md` (today's full prompt, 164 clips:
141 ok, 22 "say again", 1 wrong command). Bench tool: `audio-adapter/tools/phrase_bench.py`.
Corpus: `audio-adapter/data/corpus/bl17-stage3c/` (git-ignored, on the Mac).

## The user's direction (verbatim, 2026-11-18)

> - "alt" -> use "altitude" that's what I'll say
> - numbers as words -> either get whisper to STT the to numbers ditecly or then we use individual
>   digits like "three zero" to say 30.
> - when numeric input is expected (heading <number>, speed <number>, etc) fuzzy match the part
>   after the verb to numbers since that is expected there.
> - "alright" is not a word we use -> map to "right"

## Decisions

**D1 — "alt" goes; "altitude" is the word.** `body-layer/config/rules/flight.lua`:
`set_altitude`'s `<verb:alt|altitude>` and `hold_altitude`'s `hold <verb:altitude|alt>` lose
`alt`. Any readback or handler code reading `s.verb` for these two rules is adjusted. The rule file
is the user's config — change only these two patterns and what depends on them. The prompt follows
automatically (`rule_words`). Bench evidence: "hold alt" heard as "hold out" 2/4.

**D2 — numbers: try numerals from whisper first, digits-by-digit is the fallback.** Measured gap:
"turn left thirty" 0/4 (whisper drops "thirty"); "turn left three zero" 3/4. Composed number words
are deliberately absent from the prompt (`rule_patterns.rule_words` docstring, user 2026-11-17).

1. Try a prompt change that makes whisper write composed numbers as numerals — e.g. numeral
   examples in the prompt's framing sentence (`vocabulary._PROMPT_FRAMING`/`to_prompt`), not a
   list of number words. Measure with `phrase_bench.py` (A_full row) before and after.
2. **Ship it only if** "turn left thirty"-type phrases improve and the bench shows **no new wrong
   command** and no drop on any other phrase. Respect the 224-token prompt cap
   (`server.py`'s warning; `test_vocabulary.py`'s cap test).
3. Otherwise, no prompt change: the spoken form for numbers is individual digits ("three zero"),
   which already works. Record that in the research note and the plan, and say so in the report —
   the user then knows to say digits.

**D3 — a numeric slot fuzzy-matches what follows the verb to digits.** Where a pattern expects a
number (`angle`, `quantity`, `speed_target`'s numeric form, `heading`), words in that slot position
that are not digits or number words are matched to digit words by sound/spelling, because a number
is what is expected there. Measured cases: "heading **to** seven zero" (×3) → 270, "altitude 3
**to** 0 radar" → 320, "turn left three **free**/**show**", "**for**ty five". A small explicit
homophone table (to/too → two, for/fore → four, free/tree → three, won → one, ate → eight, niner →
nine, oh → zero …) plus, if needed, the existing char-ratio fuzz against the digit words with a
cutoff. Constraints:

- **Only inside a numeric slot, after the verb/literal has matched.** Never anywhere else — "to"
  and "for" are ordinary words.
- The slot's existing bounds still apply (heading three digits 000–359, etc.); a fuzzed value that
  falls outside bounds is a miss, never clamped.
- The readback already speaks the value, so a wrong fuzz is audible; the fuzz must still not turn
  a "say again" into a wrong command on the corpus (bench WRONG count must not rise).

**D4 — "alright" means "right".** Normalise "alright"/"all right" to "right" before matching
(`vocabulary.normalize_for_match` or the matcher's own normalisation step — wherever the existing
word-mapping lives; reuse it rather than adding a second). Bench: `right_3` "alright" matched
`point` — the only wrong command under today's prompt. After the fix it must reach the HVRT bare
"right". Check that "all right" in a non-command sentence does not now fire a command where it
previously fell through — if the HVRT bare-word path would fire on any sentence containing
"right", report it rather than widen it.

**D5 — a bare direction followed by a number never becomes `point`.** Added mid-implementation,
user-approved 2026-11-18 ("as recommended"). Evidence:
`audio-adapter/research/2026-11-18-whisper-model-sweep-flight-corpus.md` (on `main`) -- when
whisper drops "turn" from "turn right forty five", the remainder "right forty five"/"right 45"
resolves to the legacy `point` command (base.en x2, medium.en x1; small.en's one wrong command,
"alright" -> `point`, is the same path -- D4 above fixes that specific instance, this generalises
the guard). `command_matcher.py`'s `point`/`"what"` branches call `_parse_point_slots`, which scans
the whole transcript for each of four slots independently rather than requiring full consumption;
a `relative` slot ("right") resolving on its own, with a trailing bare number never checked by
anything, is the mechanism. Required: "right 45", "right forty five", "left 30" (direction word +
number, no "turn") must not match `point`; a miss ("say again") is correct -- never invent "turn"
to complete it into `turn_heading_relative`. Fix must not regress real `point` phrasings that
legitimately pair a number with its own unit marker ("two o'clock", "three kilometres").

**D6 — fix the `turn_heading` double-"heading" defect found while implementing D3.** Added
mid-implementation, main-loop decision 2026-11-18. The real shipped `flight.lua` pattern,
`"<verb:turn|fly> heading <heading_deg:heading>"`, required the literal word "heading" **twice** to
match at all -- once from the pattern's own grammar, once more from inside `rule_patterns.
_consume_heading`'s own `consume`, which also checked for the literal word "heading" before reading
the three digits. "turn heading three one five" (what a pilot actually says, and every test's own
assumed wording) never matched the real rule; only "turn heading heading three one five" did.

**Fix:** make the `heading` slot type pure digits -- exactly 3 digits, 0-360 (360→0), the same
digit-homophone table D3 ships -- and move the anchor word into the pattern, as an ordinary
literal, where it belongs. `flight.lua`'s own pattern string needs no change (it already writes the
literal correctly); only the slot type's own `consume` and its sample, every direct use of the bare
`<deg:heading>` slot in tests, and the `rule_words` docstring (which incorrectly claimed no pattern
used a literal "heading") needed correcting. Reasoning: a literal in the pattern is what
`rule_words` walks to feed the whisper prompt bias (D10); an anchor hidden inside a slot's own
`consume` never reached the prompt either way (user direction, 2026-11-18, recorded in `BL-17`:
*"read the actual speech patterns used from the lua rule files and use them to get whisper recognize
those"*).

## Out of scope

- "speed max" heard as "speed maximum"/"speed x", "forward" as "from what", "level flight" as
  "pilot flight" — not in the user's list; leave.
- The corpus's "heading three one five" and "level off" clips predate the user's 13:53 wording
  change ("turn/fly heading", "stop turn"); not re-recorded, not re-mapped.
- Stage 3c's hint narrowing (deferred).

## Acceptance

- Unit tests for D1 (the two patterns), D3 (each homophone in each numeric slot type, bounds,
  never outside a slot), D4 ("alright" → right; a free-speech sentence with "all right" unchanged),
  D5 ("right 45"/"right forty five"/"left 30" never match `point`; a legitimate relative+distance
  phrase, e.g. "look right 5 kilometres", still does), D6 ("turn heading three one five"/"fly
  heading 0 9 0"/"turn heading to seven zero" → `turn_heading` with the right value; "turn heading
  heading 315" no longer matches; "heading 315" alone does not become `turn_heading`).
- `phrase_bench.py` re-run on the corpus with the branch's matcher, rules and prompt: A_full row
  correct count up, WRONG count not up; the before/after table appended to
  `audio-adapter/research/2026-11-18-state-hint-bench.md`. (D6 note: the corpus's own
  `heading_*`-style clips say "heading …" without "turn"/"fly", so they stay on the legacy
  `scan_bearing_deg`/`report_bearing_deg` path per the corpus's own documented caveat and are
  unaffected by D6.)
- `tools/check_rules.py` (body-layer) passes on the edited `flight.lua`.
- Flight: `#needs-flight` — say "altitude three hundred", "hold altitude", "turn left three zero",
  "turn heading two seven zero" (D6: the verb is required now — bare "heading two seven zero" is
  not a command), "right".
