---
name: tts-voice-output-stage1-4
description: srs-adapter subproject scaffold + aircraft-layer audio channel + body-layer speech_client (BL-10 first slice, stages 1-4)
metadata:
  type: project
---

Implemented `plans/tts-voice-output/plan.md` stages 1-4 on `feature/tts-voice-output`
(commits `ac9cce5`, `90bfd48`, `6cb0ec6`, `3d09313`, `5cbd4e8`). Stages 5-6 (live Windows/DCS
verification) deferred to the user.

**winsound guarding — the pattern to reuse for any future Windows-only stdlib import.** A static
`if sys.platform == "win32": import winsound ... else: <RuntimeError-raising stand-in>` works with
`mypy --strict` on the Mac; a `try: import winsound / except ImportError:` does **not** — verified
live. `winsound`'s typeshed stub exists on every platform but reports every member as "no
attribute" outside `sys.platform == "win32"`, so referencing `winsound.PlaySound` inside a bare
`try` block still fails `--strict`. mypy specially recognizes `sys.platform` comparisons and skips
type-checking the statically-unreachable branch for the platform it's run on — the `if` form gets
that treatment, the `try`/`except` form does not.

**`python -m __main__` does not work** (`ValueError: __main__.__spec__ is None`) — a flat
`src/__main__.py` file cannot be the target of `python -m <name>` when `<name>` is literally
`__main__`. If a plan's file list says `src/__main__.py` for a subproject with no existing package
structure, put it in a small sub-package instead (`src/<subproject>/__main__.py` +
`__init__.py`) so `python -m <subproject>` resolves — keep other flat top-level modules
(`tts_engine.py`, `server.py`, etc.) as-is on `src`'s pythonpath.

**`say -v <unknown voice>` silently falls back to the default voice, does not error** — confirmed
live (`say -v "not a real voice" ...` exits 0, produces valid audio). Do not assume invalid-voice
detection is free; write a test that documents the actual (surprising) behavior instead.

**Every subproject needs its own `.gitignore`.** `srs-adapter/` had none initially — the root
`.gitignore` does not cover `.venv/`/`__pycache__/`. Copy the pattern from `aircraft-layer/
.gitignore`/`body-layer/.gitignore` when scaffolding a new subproject, before running any command
that could stage a venv.

Live end-to-end verified during this pass (not just unit tests): `srs-adapter --target local` via
`afplay` with nothing else running; `srs-adapter --target aircraft-layer` → real standalone
aircraft-layer collector → `POST /audio/play` → `AudioPlaybackSender`, including its designed
non-Windows `winsound` failure being logged/swallowed without crashing; body-layer's real
`SrsAdapterClient.push_speech` against a live `srs-adapter` instance.

See [[feedback_agent_memory_path]] — unrelated, but check it too if writing agent memory from
inside a subproject context.
