---
name: project_bl17_whisper_numerals_citation_overreach
description: BL-17 Stage 3a review-fix re-review -- rule_words()'s docstring cites research/2026-09-19-whisper-contract-and-grammar-probe.md to support "whisper already writes recognised numbers as numerals regardless of prompt wording," but that file only measured a single digit word ("three") in a clock-position context, not composed two/three-digit number words -- an extrapolation the citation does not support, and BL-17.md's own roadmap entry two sections earlier calls the composed-number case unmeasured.
metadata:
  type: project
---

Re-reviewing `1cb9b0de` (BL-17 Stage 3a review fix, round 2) against this project's own standing
rule to check a citation actually says what a docstring claims it says (root `CLAUDE.md`'s
analogous invariant for DCS internals, applied here to an external-tool claim). The docstring on
`rule_patterns.rule_words()` and the mirroring test class
(`TestRuleWordsNeverCarriesComposedNumberWords`) assert, citing
`audio-adapter/research/2026-09-19-whisper-contract-and-grammar-probe.md`: *"whisper already
writes recognised numbers as numerals regardless of a prompt's wording."*

Read the cited file directly: its one relevant measurement is "report three o'clock" decoding to
`"3 o'clock"` on both benched models -- a **single digit** word, in a clock-position context, on
synthetic `say` audio. The file's own "What this does not tell us" section limits its caveat to
accent, not to composed numbers, and the Implementer's own docstring generalizes a one-data-point,
single-digit measurement to an unqualified claim about "recognised numbers." Crucially,
`body-layer/ROADMAP/BL-17.md`'s own roadmap entry for the exact same decision, written the same
day, two sections above this docstring, says the opposite about certainty: *"Unknown what STT
does, does it become 30 or thirty... Settle with real whisper output when the re-plan picks this
up."* The docstring now states as settled fact something the project's own roadmap calls
unmeasured.

**Why this did not block approval**: the engineering decision is safe regardless of which way
whisper actually transcribes a composed number -- `_consume_digit_run` already parses a numeral
token and D14's word-grammar already parses a spelled word, so the fix holds under either outcome.
The citation overreach is a documentation-accuracy defect, not a design or behaviour problem;
flagged as a required fix anyway (mechanical, one docstring reword) because a future reader will
trust the citation as having settled something Stage 3c's real corpus bench is what actually
settles.

**How to apply**: when a docstring or test-class justification cites a `research/` file to support
a claim, read the cited file's actual finding before trusting the paraphrase -- check not just
whether the direction of the claim is right, but whether the *scope* (single case vs. a general
class) matches what was measured. A generalization from n=1 to "always"/"regardless of" is exactly
the shape this project's own `BL-17.md` roadmap caught itself making uncertain two sections earlier
in the same file -- cross-check the roadmap's own stated certainty against the docstring's, not
just the research file.

Full report: `plans/speech-rules/review-stage3a.md`, "Re-review — 2026-11-17", Required Fix 1.
