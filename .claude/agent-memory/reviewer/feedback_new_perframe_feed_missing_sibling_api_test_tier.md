---
name: feedback_new_perframe_feed_missing_sibling_api_test_tier
description: when a new aircraft-layer per-frame feed (schema + cache + collector routing + GET /x/latest endpoint) ships, check for the sibling-feed test tier (test_<feed>_api.py) by grep, not by reading the Lua-side tests and assuming parity
metadata:
  type: feedback
---

BL-16 mode 2 batch A (Stage P-ICS/P0/P1, `plans/flight-control/plan.md`) added a new
per-frame feed, `AiPilotWheelState`/`AiPilotWheelCache`/`GET /ai_pilot_wheel/latest`,
structurally identical to `SightServoState`/`SightServoCache`/`GET /sight_servo/latest`
and `PayloadSample`/`PayloadCache`/`GET /payload/latest` before it. The implementer wrote
a thorough Lua-side test (`test_ai_pilot_wheel_lua.py`, pure functions run against a real
Lua interpreter) and a body-layer-side belief test (`test_ai_pilot_wheel.py`), and reported
"all tests pass" with real numbers (733/736 passed). Both reports were true and both missed
the same thing: **no aircraft-layer Python-side test exercises the new schema's own parse/
validation (`from_dict` error paths), the cache, the collector's new routing branch, or the
HTTP endpoint** — the exact tier every sibling feed has as its own `test_<feed>_api.py`
(`test_sight_servo_api.py`, `test_payload_api.py`, and `test_ptt.py`'s own
`TestPttSample`/`TestCollectorRouting`/`TestPttEndpoint` classes).

**How this was found:** not by reading the "Tests Added" section of the implementation
report (which only lists what was added, not what the convention would have added), but
by `grep -rln "AiPilotWheel" aircraft-layer/tests/` — one hit, the Lua-only file. Cross-
checked by `ls aircraft-layer/tests/ | grep -i "payload\|sight_servo\|ptt"` to confirm the
sibling pattern (`_api.py` + `_lua.py` pairs) actually exists for every comparable feed, so
the gap is a real asymmetry and not an invented convention.

**Why this matters:** `mypy --strict` passing and the body-layer-side test passing both
give false confidence here — the body-layer test serves a hand-built dict through a bare
`http.server` handler and never touches `AiPilotWheelState`/`CollectorServer`/
`AiPilotWheelCache` at all, so a defect in the schema's validation, the collector's routing
order (does it fire ahead of the telemetry fallthrough, same reason every other named kind
does?), or the endpoint's `None`-before-first-sample posture would pass every test in the
suite and only surface live.

**How to apply:** whenever a plan adds a new per-frame (or any `GET /x/latest`) feed to
`aircraft-layer`, grep for that feed's class name across `aircraft-layer/tests/` as a first
check, and separately confirm by directory listing that the sibling-feed test-file pattern
(`test_<feed>_api.py` alongside `test_<feed>_lua.py`) exists for at least one comparable
existing feed — if the new feed has the Lua half and the body-layer-consumer half but not
the aircraft-layer schema/cache/routing/endpoint half, that is a required fix, not an
optional nice-to-have, because it is the one tier most likely to hide a routing-order or
drop-vs-raise defect that neither mypy nor the body-layer tests can see.
