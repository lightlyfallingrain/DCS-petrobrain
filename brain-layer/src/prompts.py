"""The two prompt shapes D5 allows (`plans/brain-layer/plan.md`), as
module constants -- **verbatim, not reconstructed per call**, since the
plan's own D6 finding is that a small model's accuracy is sensitive to
exactly how tightly the formatting instruction is worded ("both models
picked wrong when the formatting instruction was removed"). Both are
`str.format`-style templates rather than an f-string builder, so the
literal wording stays visible and diffable in one place.

**Classify** -- the utterance's deterministic grammar found no matching
verb at all (`decider.structural_unable_reason`'s `NO_SUCH_COMMAND`
case). The model gets one narrow question: does the pilot's own wording
plausibly name one of the known commands anyway (a synonym, an awkward
phrasing the grammar missed), or not. `CLASSIFY_PROMPT` is D5's "one
narrow decision per call" applied to D11's "plausibly a command the
deterministic grammar missed" scope item (`plans/brain-layer/plan.md`
scope bullet 2) -- this is the genuine-judgement half of `NO_SUCH_COMMAND`
that `structural_unable_reason` deliberately leaves to a real decider
(see that function's own docstring: "genuine judgement... left to the
caller").

**Discriminate** -- Measurement 4's exact fix, quoted verbatim from the
plan: the code has already established the reference is ambiguous; the
model's only job is to find pilot's-own-words evidence that singles out
one candidate, and D10's validator (body-side) checks that evidence is
both present and actually discriminating. Used both for the initial `ASK`
case (2+ candidates) and, per D9, for the Stage 3 answer leg (the same
prompt run again against the pilot's follow-up utterance) -- Stage 3
itself is out of scope here, but the prompt is written to already support
that reuse rather than being ASK-specific in its wording."""

from __future__ import annotations

#: D11's closed set of simple (no-slot-parameter) command tokens the
#: classify call may confirm -- a curated subset of `belief.crew_console.
#: DISPATCHED_COMMAND_TOKENS`, duplicated here rather than imported
#: (module independence: this process never imports body-layer code, the
#: seam is HTTP/JSON only). **Deliberately narrower than the full
#: vocabulary** -- every token below takes no slot the model would have
#: to also extract (a bearing in degrees, a clock hour), which BR-1's
#: single-line closed-vocabulary constraint (D5) is not built to elicit
#: reliably. The body-side D10 validator is the real authority on
#: whether a returned token is legal at all (`belief.brain_reply`); this
#: list only shapes what the model is offered to choose from, so a
#: mismatch here costs accuracy, never safety.
CLASSIFY_COMMAND_VOCABULARY: tuple[str, ...] = (
    "watch_nearest",
    "watch_nearest_air_defence",
    "report_all",
    "cancel_task",
    "cancel_scan",
    "cancel_watch",
    "stop_talking",
)

#: Measurement 4's fix (plan `## Measurement 4`), down to the imperative
#: mood and the `PICK <id> BECAUSE <words>` / `ASK` reply forms -- this
#: wording is what turned a 3B model's silent wrong guess into a caught,
#: honest `ASK` on every model tried (D6). Two lines were added after the
#: measurement, found by running a real model against a live server
#: 2026-09-25 (not by the tests, which passed because they fed the parser
#: evidence the real model does not produce): an opening "reply with
#: EXACTLY ONE line" sentence, guarding the same runaway-deliberation
#: failure D6 measured ("think step by step" -> 575 tokens, picked
#: wrong); and a narrowed BECAUSE instruction -- the model otherwise
#: mirrors this prompt's own `Pilot said: "..."` rendering and either
#: wraps its evidence in quote characters (stripped by `decider._unquote`,
#: the more common failure and the one that can never be worked around by
#: prompt wording alone) or quotes the entire sentence (which can never be
#: grounded in one candidate's own `why` text -- this is the one the
#: prompt wording below actually prevents).
#: `{candidates}` is a newline-joined `"<id>: <why>"` list; `{transcript}`
#: is the pilot's own words, never anything derived or paraphrased.
DISCRIMINATE_PROMPT = """Reply with EXACTLY ONE line, nothing else, no explanation.

The code has ALREADY established that the pilot's reference is ambiguous. Your ONLY job is to decide whether the pilot's own words contain something that singles out one candidate. Quote ONLY the single distinguishing word or short phrase - a place, a landmark, a position. NEVER quote the whole sentence: the words you quote must appear in that candidate's description and not the other's.

Pilot said: "{transcript}"

Candidates:
{candidates}

Reply on one line, exactly one of:
PICK <id> BECAUSE <words>
ASK

Use ASK unless the pilot's words clearly name something true of one candidate and not the other. Reply with nothing else."""

#: The classify call's own narrow question -- D5's "each one question"
#: sibling to `DISCRIMINATE_PROMPT`, for the `NO_SUCH_COMMAND` case
#: (module docstring). `{commands}` is a newline-joined list of
#: `CLASSIFY_COMMAND_VOCABULARY`; `{transcript}` is the pilot's own words.
CLASSIFY_PROMPT = """Reply with EXACTLY ONE line, nothing else, no explanation.

The pilot said something that did not match any known command exactly. Decide whether it plausibly means one of the commands below anyway, or does not match any of them at all.

Pilot said: "{transcript}"

Known commands:
{commands}

Reply on one line, exactly one of:
CONFIRM <command>
UNABLE

Use UNABLE unless the pilot's words clearly mean one of the listed commands. Reply with nothing else."""


def render_discriminate_prompt(
    transcript: str, candidates: list[tuple[str, str]]
) -> str:
    """`candidates` is `[(id, why), ...]`, in the order the payload
    itself offered them -- no reordering, since D10's validator checks a
    `PICK <id>` against exactly that list."""
    candidate_lines = "\n".join(f"{cid}: {why}" for cid, why in candidates)
    return DISCRIMINATE_PROMPT.format(transcript=transcript, candidates=candidate_lines)


def render_classify_prompt(transcript: str) -> str:
    command_lines = "\n".join(CLASSIFY_COMMAND_VOCABULARY)
    return CLASSIFY_PROMPT.format(transcript=transcript, commands=command_lines)


__all__ = [
    "CLASSIFY_COMMAND_VOCABULARY",
    "CLASSIFY_PROMPT",
    "DISCRIMINATE_PROMPT",
    "render_classify_prompt",
    "render_discriminate_prompt",
]
