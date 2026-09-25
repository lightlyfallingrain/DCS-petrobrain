"""Cross-process BR-1 Stage 2 check -- a dev acceptance aid, not a test.
Mirrors `live_cross_process_check.py`'s own shape (Stage 1's async round
trip) but drives a real `brain-layer` server running `OllamaDecider`
against a real Ollama daemon, exercising both prompt shapes end to end:
the discriminate call (ambiguous vs. discriminating "that tank") and the
classify call (a paraphrased known command vs. genuine nonsense), plus
(scenario 5, below) several overlapping utterances fired without waiting.

Assertion-free by design, same posture as `live_cross_process_check.py`/
`body-layer/tools/speak_samples.py` -- it prints numbers and replies for a
human to judge. This is the instrument for the one verification gap this
stage's implementation could not close in-sandbox: no test here runs a
real Ollama daemon, so nothing here can prove a real model's own quoting/
deliberation habits against the live prompts short of running this.

**Scenario 5 exists because scenarios 1-4 cannot show the failure mode
that actually matters in production** (`plans/brain-layer/performance-
review.md`'s Stage 2 MONITOR finding, carried forward as a recommended
refinement by `plans/brain-layer/review.md`'s Stage 2 fold review):
Ollama serialises generation on one daemon, so a single deliberating
reply (the D6 measurement: `qwen3:4b` reasoning for 32.7s against its own
prompt instructions) does not just make *that* reply slow -- it chain-
drops every utterance that arrives while it is still computing, because
each of those still only gets `OllamaClient`'s own per-call timeout
before the client gives up, while Ollama itself keeps grinding through
its queue regardless. Scenarios 1-4 fire one utterance at a time and wait
for each reply before sending the next, so a regressed model would only
ever show up there as one slow reply -- never as the run of silently
dropped utterances a real chain-drop produces. Scenario 5 fires several
utterances back to back with no wait, then reports, per utterance,
whether it was answered and -- for the ones that were not -- the best
available read on *why*: **superseded** (a later-fired utterance was
answered, which is D3's newest-wins working as designed, not a failure)
vs. **no evidence of an answer to any later utterance either** (consistent
with a chain-drop, or simply every one of them still being decided when
this script gave up waiting -- the wire gives no server-side reason code
for an utterance that never got a reply, so this script cannot fully
distinguish "dropped by a timeout" from "still in flight," and says so
rather than guessing).

Run it with the server up:

    cd brain-layer && PYTHONPATH=src .venv/bin/python -m brain_layer \\
        --host 127.0.0.1 --decider ollama \\
        --brain-model qwen3:4b-instruct-2507-q4_K_M &
    .venv/bin/python brain-layer/tools/live_stage2_decider_check.py
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

URL = "http://127.0.0.1:7796"


def _post(path: str, body: dict[str, Any]) -> None:
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()


def _get(path: str) -> Any:
    with urllib.request.urlopen(f"{URL}{path}", timeout=5) as response:
        return json.loads(response.read())


def _escalate_and_wait(
    payload: dict[str, Any], timeout_s: float = 15.0
) -> tuple[float, float | None, dict[str, Any] | None]:
    t0 = time.monotonic()
    _post("/escalate", payload)
    handoff = time.monotonic() - t0
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        replies = _get("/replies/poll")
        if replies:
            return handoff, time.monotonic() - t0, replies[0]
        time.sleep(0.05)
    return handoff, None, None


_DISCRIMINATE_BASE: dict[str, Any] = {
    "utterance_id": "U_DISCRIMINATE",
    "transcript": "keep an eye on that tank",
    "t_sim": 100.0,
    "partial_parse": {
        "matched_intent": "set_attention",
        "referenced_contact_candidates": [
            {"id": "CONTACT_7", "why": "T-72, 2.1 km, near Gemerek village"},
            {"id": "CONTACT_12", "why": "T-72, 3.4 km, on the road"},
        ],
    },
}


#: Fired this closely together, a genuinely deliberating model (D6's
#: measured 32.7s worst case) has not finished the first one before the
#: last one is submitted -- the condition scenario 5 exists to create.
#: Against a fast/healthy model every one of these will simply be
#: answered in turn; the point is to *also* be informative when the model
#: is not healthy, not to force a drop on a good day.
_OVERLAP_FIRE_INTERVAL_S = 0.3

#: How long to keep draining `/replies/poll` after the last utterance is
#: fired before giving up on the ones still missing. Generous relative to
#: `OllamaClient.DEFAULT_TIMEOUT_S` (5.0s, `ollama_client.py`) so a
#: healthy model has time to answer every one of them in turn even though
#: they were all submitted almost at once.
_OVERLAP_DRAIN_TIMEOUT_S = 30.0

#: Five different utterances, fired back to back -- distinct transcripts
#: (not five copies of one) so each reply is independently checkable
#: against what it should have said, not just against whether it arrived.
_OVERLAP_UTTERANCES: list[tuple[str, dict[str, Any]]] = [
    (
        "U_OVERLAP_1",
        dict(_DISCRIMINATE_BASE, utterance_id="U_OVERLAP_1"),
    ),
    (
        "U_OVERLAP_2",
        dict(
            _DISCRIMINATE_BASE,
            utterance_id="U_OVERLAP_2",
            transcript="keep an eye on that tank near the village",
        ),
    ),
    (
        "U_OVERLAP_3",
        {
            "utterance_id": "U_OVERLAP_3",
            "transcript": "go take a look up north",
            "t_sim": 100.0,
            "partial_parse": {
                "matched_intent": None,
                "referenced_contact_candidates": [],
            },
        },
    ),
    (
        "U_OVERLAP_4",
        {
            "utterance_id": "U_OVERLAP_4",
            "transcript": "the grass over there is looking rather brown today",
            "t_sim": 100.0,
            "partial_parse": {
                "matched_intent": None,
                "referenced_contact_candidates": [],
            },
        },
    ),
]


def overlapping_utterances_scenario() -> None:
    """Scenario 5, module docstring: fire `_OVERLAP_UTTERANCES` without
    waiting for a reply between them, then drain and report what came
    back against what was fired, in fire order."""
    print(
        f"5. overlapping utterances: firing {len(_OVERLAP_UTTERANCES)} without waiting "
        f"({_OVERLAP_FIRE_INTERVAL_S * 1000:.0f}ms apart)"
    )
    t_start = time.monotonic()
    fire_order: list[str] = []
    fired_at_ms: dict[str, float] = {}
    for utterance_id, payload in _OVERLAP_UTTERANCES:
        fired_at_ms[utterance_id] = (time.monotonic() - t_start) * 1000
        _post("/escalate", payload)
        fire_order.append(utterance_id)
        time.sleep(_OVERLAP_FIRE_INTERVAL_S)

    received: dict[str, dict[str, Any]] = {}
    received_order: list[str] = []
    deadline = time.monotonic() + _OVERLAP_DRAIN_TIMEOUT_S
    while time.monotonic() < deadline and len(received) < len(fire_order):
        for reply in _get("/replies/poll"):
            utterance_id = reply.get("utterance_id")
            if isinstance(utterance_id, str) and utterance_id not in received:
                received[utterance_id] = reply
                received_order.append(utterance_id)
        if len(received) < len(fire_order):
            time.sleep(0.05)

    # A missing utterance is read as "superseded" if any utterance fired
    # *after* it did get answered -- D3 newest-wins means an answered
    # later job proves an earlier one was at least eligible to be
    # discarded, whether or not that is actually why this one is
    # missing. Otherwise there is genuinely no wire-visible evidence
    # either way (still in flight when this script gave up, or dropped
    # by a timeout) and this script says exactly that rather than
    # guessing which.
    for index, utterance_id in enumerate(fire_order):
        fired_ms = fired_at_ms[utterance_id]
        reply = received.get(utterance_id)
        if reply is not None:
            print(
                f"   [{index + 1}] {utterance_id} (fired t+{fired_ms:.0f}ms): "
                f"ANSWERED -- kind={reply.get('kind')} reply={reply}"
            )
            continue
        later_answered = any(
            received.get(later_id) is not None for later_id in fire_order[index + 1 :]
        )
        if later_answered:
            verdict = "no reply -- superseded (a later-fired utterance was answered, D3 newest-wins)"
        else:
            verdict = (
                "no reply -- no later utterance answered either: consistent with a "
                "chain-drop (Ollama still serialising a slow generation) or simply "
                f"still in flight when this script's {_OVERLAP_DRAIN_TIMEOUT_S:.0f}s "
                "drain window ended -- cannot distinguish the two from the wire alone"
            )
        print(f"   [{index + 1}] {utterance_id} (fired t+{fired_ms:.0f}ms): {verdict}")

    answered_count = len(received)
    print(
        f"   summary: {answered_count}/{len(fire_order)} answered, "
        f"{len(fire_order) - answered_count} never delivered"
    )


def main() -> None:
    ambiguous = dict(_DISCRIMINATE_BASE, utterance_id="U1")
    handoff, elapsed, reply = _escalate_and_wait(ambiguous)
    print(
        f"1. discriminate, genuinely ambiguous: handoff={handoff * 1000:.1f}ms elapsed={elapsed}"
    )
    print(f"   reply = {reply}")

    discriminating = dict(_DISCRIMINATE_BASE)
    discriminating["utterance_id"] = "U2"
    discriminating["transcript"] = "keep an eye on that tank near the village"
    handoff, elapsed, reply = _escalate_and_wait(discriminating)
    print(
        f"2. discriminate, has a discriminating word: handoff={handoff * 1000:.1f}ms elapsed={elapsed}"
    )
    print(f"   reply = {reply}")

    classify_paraphrase = {
        "utterance_id": "U3",
        "transcript": "go take a look up north",
        "t_sim": 100.0,
        "partial_parse": {"matched_intent": None, "referenced_contact_candidates": []},
    }
    handoff, elapsed, reply = _escalate_and_wait(classify_paraphrase)
    print(
        f"3. classify, paraphrased known command: handoff={handoff * 1000:.1f}ms elapsed={elapsed}"
    )
    print(f"   reply = {reply}")

    classify_nonsense = {
        "utterance_id": "U4",
        "transcript": "the grass over there is looking rather brown today",
        "t_sim": 100.0,
        "partial_parse": {"matched_intent": None, "referenced_contact_candidates": []},
    }
    handoff, elapsed, reply = _escalate_and_wait(classify_nonsense)
    print(
        f"4. classify, genuine nonsense: handoff={handoff * 1000:.1f}ms elapsed={elapsed}"
    )
    print(f"   reply = {reply}")

    overlapping_utterances_scenario()


if __name__ == "__main__":
    main()
