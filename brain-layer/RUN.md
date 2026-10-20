# Running the Brain Layer

Petrovich's slow, deliberative loop. When body-layer's deterministic grammar
cannot act on what the player said, it hands the utterance here. A small
local model picks one reply from a closed set — `PICK <id>`, `ASK`,
`CONFIRM <token>` or `UNABLE <reason>` — and body-layer turns that into
Petrovich's words. The model never writes what he says.

**Where this runs:** anywhere on the LAN. Normally the Mac, next to
body-layer and the Ollama daemon. It does not need DCS.

```
 body-layer ── POST /escalate ──▶ brain-layer :7796 ── /api/generate ──▶ Ollama :11434
            ◀─ GET /replies/poll ─┘   (202 at once; the reply arrives later)
```

**Nothing ever waits on it.** `POST /escalate` answers `202` before a decision
exists, and body-layer collects the reply on a later poll. A slow or hung model
costs a late answer, never a stalled crew.

For the design see `CLAUDE.md` and `plans/brain-layer/plan.md`; for milestone
status see `ROADMAP/brain-layer-roadmap.md`.

---

## 1. One-time setup

No third-party Python dependencies — stdlib only.

**macOS (zsh)**

```zsh
cd brain-layer
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

**Windows (Command Prompt)**

```bat
cd brain-layer
python -m venv .venv
.venv\Scripts\python -m pip install -e .
```

For the real model (`--decider ollama`) you also need **Ollama** running, with
the model pulled:

```zsh
ollama pull qwen3:4b-instruct-2507-q4_K_M
```

The stub decider needs neither.

## 2. Run the server

The usual way, from `run-scripts/`:

```zsh
./run-brain.sh
```

which is:

```zsh
cd brain-layer
PYTHONPATH=src .venv/bin/python -m brain_layer --stub-delay-s 0 --decider ollama
```

Extra arguments to the script are passed through, e.g.
`./run-brain.sh --debug`.

`PYTHONPATH=src` is **required** — `src` is not an installed package.

**The binary's own `--decider` default is `stub`; the run script passes
`ollama`.** Running `python -m brain_layer` by hand without the flag gives you
the stub, which answers with no model at all.

**It listens on loopback by default**, which is right while body-layer runs on
the same machine. If body-layer moves to another box, add `--host 0.0.0.0` —
`/escalate` has no authentication, so do not do it otherwise.

At startup the server warms the model once, so the first in-flight question
does not pay the load time.

### Options

| flag | default | meaning |
|---|---|---|
| `--host` | `127.0.0.1` | listener host |
| `--port` | `7796` | listener port |
| `--decider` | `stub` | `stub` (no model, for testing the round trip) or `ollama` (the real model) |
| `--stub-delay-s` | `0` | how long the stub pretends to think; `stub` only |
| `--brain-model` | `qwen3:4b-instruct-2507-q4_K_M` | Ollama model tag |
| `--ollama-url` | `http://127.0.0.1:11434` | Ollama daemon |
| `--decide-timeout-s` | `12.0` | upper bound on one decision |
| `--debug` | off | log every request |

### Connecting body-layer to it

Body-layer's crew needs `--brain-client http --brain-url http://127.0.0.1:7796`
— `run-scripts/run-crew-text.sh` already passes both. See `body-layer/RUN.md`.

## 3. Check it is working

```zsh
curl http://127.0.0.1:7796/health
curl http://127.0.0.1:7796/replies/poll
```

`/replies/poll` returns `[]` when nothing has been decided since the last
poll. **A poll from curl takes the reply away from body-layer**, so do not run
it during a sortie.

To see the round trip, i.e. that the handoff does not block, the reply arrives
later, and body-layer's poll cadence is untouched:

```zsh
cd brain-layer && PYTHONPATH=src .venv/bin/python -m brain_layer \
    --host 127.0.0.1 --port 7797 --stub-delay-s 8 &
cd body-layer && PYTHONPATH=src:../world-model/src .venv/bin/python \
    ../brain-layer/tools/live_cross_process_check.py
```

`tools/live_stage2_decider_check.py` does the same against the real model.
Both print numbers for you to judge; they are not tests.

## 4. Development checks

From `brain-layer/`, with the venv's tools — `ruff`/`mypy`/`pytest` are
generally not on `PATH`:

```zsh
.venv/bin/ruff format src tests
.venv/bin/ruff check src tests
.venv/bin/mypy src
.venv/bin/pytest tests -q
```

**`mypy` must run from inside `brain-layer/`** — its config discovery is
CWD-only. The suite needs no Ollama and no DCS.

---

## Troubleshooting

**Every reply is an instant `ASK` or `UNABLE`, and never a `PICK` or
`CONFIRM`** — you are on the stub, which has no judgement. Pass
`--decider ollama`.

**Replies arrive late or not at all** — Ollama is not running, the model is not
pulled, or it is still loading. Ollama's own request timeout is 5 s and the
server's backstop is `--decide-timeout-s`. Run with `--debug` to see which one
fired.

**body-layer cannot connect** — the server is on loopback and body-layer is on
another machine (see `--host` above), or the port does not match
`--brain-url`.
