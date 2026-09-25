"""Cross-process BR-1 Stage 1 check -- a dev acceptance aid, not a test.

Drives a real `body-layer` `BrainLayerClient` against a real `brain-layer`
server running in a separate process with an 8 s stub delay. It exists because
the plan's Stage 1 acceptance names three things no single-process test can
show: that handoff does not block, that the reply arrives later, and that the
poll loop's cadence is untouched while the brain is thinking. The unit tests
prove each half against a fake; only two real processes prove the whole.

Assertion-free by design, same posture as `body-layer/tools/speak_samples.py`
-- it prints numbers for a human to judge, and its PASS/FAIL lines are a
convenience, not a gate. It is deliberately not in `tests/`: it needs a server
listening on a port, which a test suite must never depend on.

Run it with the server up:

    cd brain-layer && PYTHONPATH=src .venv/bin/python -m brain_layer \
        --host 127.0.0.1 --port 7797 --stub-delay-s 8 &
    cd body-layer && PYTHONPATH=src:../world-model/src .venv/bin/python \
        ../brain-layer/tools/live_cross_process_check.py

Measured 2026-09-25 on this machine: handoff 0.1 ms against an 8000 ms stub,
tick interval mean 203.8 ms against a 200 ms target (worst 214.6 ms), reply at
8.15 s carrying `kind='unable' reason='NO_SUCH_COMMAND'`.
"""

import time

from belief.brain_client import BrainLayerClient
from belief.escalation import EscalationPayload
from belief.utterance import PartialParse

URL = "http://127.0.0.1:7797"
client = BrainLayerClient(base_url=URL)

payload = EscalationPayload(
    utterance_id="u_live_1",
    transcript="see if that ridge is clear",
    transcript_confidence=0.91,
    t_sim=100.0,
    partial_parse=PartialParse(
        matched_intent=None,
        confidence=0.0,
        disposition="escalated",
        reason_escalated="unmatched",
    ),
    situational_header={"contact_counts": 0, "estimated_units": 0},
)

# --- 1. handoff must not block -------------------------------------------
t0 = time.monotonic()
client.handle(payload)
handoff = time.monotonic() - t0
print(f"1. handoff blocked for      {handoff * 1000:7.1f} ms   (stub delay is 8000 ms)")

# --- 2. simulate the 5 Hz poll loop while the brain thinks ----------------
# Every iteration does what the real loop does: drain replies, then wait.
POLL_S = 0.2
ticks, replies, gaps = 0, [], []
deadline = time.monotonic() + 12.0
last = time.monotonic()
while time.monotonic() < deadline:
    got = client.poll_replies()
    now = time.monotonic()
    gaps.append(now - last)
    last = now
    ticks += 1
    if got:
        replies.append((now - t0, got))
        break
    time.sleep(POLL_S)

worst = max(gaps)
mean = sum(gaps) / len(gaps)
print(f"2. polled {ticks} times while thinking; tick interval mean "
      f"{mean * 1000:.1f} ms, worst {worst * 1000:.1f} ms  (target 200 ms)")

# --- 3. the reply must actually arrive, after the delay -------------------
if replies:
    elapsed, got = replies[0]
    r = got[0]
    print(f"3. reply arrived after      {elapsed:7.2f} s   kind={r.kind!r} "
          f"reason={r.reason!r} utterance_id={r.utterance_id!r}")
else:
    print("3. NO REPLY within 12 s — FAIL")

print()
ok_handoff = handoff < 0.5
ok_cadence = worst < POLL_S * 2
ok_reply = bool(replies) and 7.0 < replies[0][0] < 11.0
print(f"handoff non-blocking : {'PASS' if ok_handoff else 'FAIL'}")
print(f"cadence undisturbed  : {'PASS' if ok_cadence else 'FAIL'}")
print(f"reply after ~8 s     : {'PASS' if ok_reply else 'FAIL'}")
