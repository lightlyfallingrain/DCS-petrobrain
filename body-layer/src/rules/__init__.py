"""Spoken commands as Lua rules (`plans/speech-rules/plan.md`, BL-17).

`sandbox.py` is the only module here (or anywhere in this codebase) that
imports `lupa`. `loader.py` reads `config/rules/*.lua`; `engine.py` turns
what it finds into a `RuleSet` and runs one rule's handler per dispatch;
`actions.py` is the allowlisted Python registry a handler may call into.
See each module's own docstring."""
