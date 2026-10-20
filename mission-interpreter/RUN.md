# Running the Mission Interpreter

Reads one mission **before you fly it**. It parses the `.miz`, strips
everything only the mission author should know (hidden and late-activation
groups, triggers), places the route and the zones against the world model, and
has a local model infer purpose, task and likely threats. Then it asks you a
few questions about your intent, and writes a compact mission file that
body-layer loads at startup.

**Where this runs:** anywhere with the `.miz`, a reachable world-model API, and
Ollama. Normally the Mac. It is offline and pre-mission: run it once per
mission, not during the sortie.

```
 mission.miz ─▶ parse ─▶ filter author-only ─▶ enrich ──▶ synthesize ──▶ your answers ─▶ compact JSON
                                                │            │                              │
                                     world-model API     Ollama qwen3:14b       body-layer --mission-understanding
                                         :7792              :11434
```

For the design see `CLAUDE.md` and `docs/concept/MISSION_INTERPRETER.md`; for
milestone status see `ROADMAP/mission-interpreter-roadmap.md`.

---

## 1. One-time setup

No third-party Python dependencies. The `.miz` Lua parser is vendored, in
`src/_vendor/`.

```zsh
python3 -m venv mission-interpreter/.venv
mission-interpreter/.venv/bin/pip install "ruff==0.16.5" "mypy==2.3.1" "pytest==9.1.1"
```

There is no lockfile and nothing to `pip install -e`. The venv only carries
the dev tools.

You also need:

- **A built world model for the mission's theatre** — see `world-model/RUN.md`.
- **Ollama with `qwen3:14b` pulled**:

  ```zsh
  ollama pull qwen3:14b
  ```

  **Pull it first, deliberately.** The interpreter checks that the model is
  present before calling it and stops with an error if it is not. Without that
  check, Ollama would quietly start a multi-GB download mid-run.

## 2. Start the world-model API

The interpreter reaches the world model over HTTP, not by importing it. In a
second terminal:

```zsh
cd world-model
PYTHONPATH=src .venv/bin/python -m api \
  --db data/world-model/syria-full.sqlite \
  --theatre Syria
```

It listens on `127.0.0.1:7792`. **`--theatre` must name the theatre the store
was built for**; the store cannot tell you.

## 3. Interpret a mission

```zsh
cd mission-interpreter
PYTHONPATH=src .venv/bin/python -m player_intent.main \
  "path/to/Mission.miz" \
  --theatre Syria \
  --emit-compact out/mission-compact.json
```

What happens:

1. It parses, filters and enriches. This is deterministic, with no model.
2. It asks `qwen3:14b` for purpose, task and known threats. If an answer comes
   back unusable, that one field is left empty rather than failing the run.
3. It **asks you questions** on the terminal, but only where the mission is
   ambiguous: yes/no, a choice, or free text.
4. It prints the full `MissionUnderstanding` as JSON on stdout.
5. With `--emit-compact`, it also writes the compact runtime file.

**`--emit-compact` is the output that matters for flying.** The stdout dump is
for reading. Hand the compact file to body-layer:

```zsh
… -m logger … --world-model-dir ../world-model/data/world-model/ \
  --mission-understanding ../mission-interpreter/out/mission-compact.json
```

Body-layer then takes the theatre from the file, picking
`<theatre>-full.sqlite` out of `--world-model-dir`, and tracks the mission
phase against your position. See `body-layer/RUN.md` and
`body-layer/src/logger.py --help`.

### Options

| argument | default | meaning |
|---|---|---|
| `miz_path` | — | the `.miz` file |
| `--theatre` | required | must match the running world-model API's `--theatre` |
| `--world-model-url` | `http://127.0.0.1:7792` | world-model API |
| `--ollama-model` | `qwen3:14b` | Ollama model |
| `--emit-compact` | none | also write the compact runtime JSON here |

## 4. What never reaches the crew

The filtering runs before anything else sees the mission:

- **Hidden and late-activation groups are dropped entirely.** The crew-facing
  tree has no field through which they could leak back in.
- **Triggers are never surfaced.**
- Threat hints derived from hidden groups are reduced to a coarse kind and a
  place name. The model never sees their names, sizes, timings or exact
  coordinates.

If Petrovich ever seems to know about an ambush before he could have seen it,
that is a defect in this layer. Report it as one.

## 5. Development checks

From `mission-interpreter/`, with the venv's tools:

```zsh
.venv/bin/ruff format src tests
.venv/bin/ruff check src tests
.venv/bin/mypy src
.venv/bin/pytest tests -q
```

**`mypy` must run from inside `mission-interpreter/`** — its config discovery
is CWD-only.

The suite needs no Ollama and no world model. `test_synth_live_ollama.py` is
the one live test and skips itself when Ollama or `qwen3:14b` is absent. Tests
against the real campaign sample (`research/samples/Mission 02-Bagram.miz`,
gitignored) skip when it is not in your checkout.

---

## Troubleshooting

**`OllamaUnavailableError`** — the Ollama daemon is not running.

**`OllamaModelNotPulledError`** — `ollama pull qwen3:14b` (or whichever model
you passed).

**`WorldModelClientError`** — the world-model API is not running, is on another
port, or was started with a different `--theatre`.

**Purpose / task / threats come out empty** — the model's answer was
unparseable for those fields and the run degraded rather than failed. Rerun, or
try a different `--ollama-model`.

**`ModuleNotFoundError: No module named 'miz'`** (or `player_intent`) —
`PYTHONPATH=src` is missing.
