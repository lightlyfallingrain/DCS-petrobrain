# Petrobrain

A crew brain for the DCS World Mi-24P's front-seat operator, Petrovich.

The goal is to make Petrovich feel like a real copilot rather than a set of disconnected game
systems. He spots and identifies contacts, tells the pilot what matters, helps them evade threats
and line up attack runs, and works the cockpit switches that are his job. His knowledge is limited
to what he could actually see: **code owns the truth, models own interpretation and language.**

**Status:** early, active development. Single-player only. Expect things to move.

## How it is put together

| subproject | what it does |
|---|---|
| `world-model/` | Offline geographic knowledge of a DCS theatre: roads, settlements, terrain |
| `mission-interpreter/` | Offline understanding of one mission, without the mission author's secrets |
| `aircraft-layer/` | DCS `Export.lua` + LAN collector: telemetry out, cockpit commands in |
| `body-layer/` | Petrovich's perception, beliefs, memory and crew console |
| `brain-layer/` | The language model loop that decides what Petrovich says and does |
| `audio-adapter/` | Speech: text-to-speech out, recognised voice commands in |

DCS runs on Windows; the rest can run on another machine on the same LAN. Each subproject has its
own `pyproject.toml` and virtual environment.

## More

- `ROADMAP.md` — what is done and what is next
- `docs/concept/` — design concepts
- `CLAUDE.md`, `AGENTS.md`, `.claude/` — the Claude Code setup the project is built with

## License

[CC BY-NC-SA 4.0](LICENSE.md): free for non-commercial use, with attribution and share-alike.
Commercial use — including of the Claude Code setup — needs a separate agreement; see
`LICENSE.md`.
