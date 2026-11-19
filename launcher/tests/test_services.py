from pathlib import Path

from launcher.helpparse import HelpOption
from launcher.services import (
    OptionState,
    build_args,
    env_key,
    option_state,
    script_flags,
    services_for,
)

RUN_SCRIPTS = Path(__file__).resolve().parents[2] / "run-scripts"


def test_env_key() -> None:
    assert env_key("body-layer", "--eyesight-view-radius-m") == (
        "OPT_BODY_LAYER_EYESIGHT_VIEW_RADIUS_M"
    )
    assert env_key("brain", "--decider") == "OPT_BRAIN_DECIDER"


def test_script_flags_ignores_comments() -> None:
    text = "# pass --host 0.0.0.0 explicitly\npython -m x --decider ollama \\\n  --host 0.0.0.0 $@\n"
    assert script_flags(text) == {"--decider", "--host"}


def test_option_state_and_build_args() -> None:
    debug = HelpOption("--debug", False, "")
    model = HelpOption("--brain-model", True, "")
    url = HelpOption("--ollama-url", True, "")
    host = HelpOption("--host", True, "")
    env = {"OPT_BRAIN_BRAIN_MODEL": "qwen3:8b"}
    in_script = {"--host"}
    assert option_state("brain", debug, in_script, env) is OptionState.TOGGLEABLE
    assert option_state("brain", model, in_script, env) is OptionState.TOGGLEABLE
    assert option_state("brain", url, in_script, env) is OptionState.NO_VALUE
    assert option_state("brain", host, in_script, env) is OptionState.IN_SCRIPT
    assert build_args("brain", [debug, model], env) == [
        "--debug",
        "--brain-model",
        "qwen3:8b",
    ]


def test_every_listed_script_exists_and_forwards_args() -> None:
    """The launcher reaches a service only through the script's own `$@`."""
    for platform in ("mac", "wsl"):
        for svc in services_for(platform):
            text = (RUN_SCRIPTS / svc.script).read_text()
            assert "$@" in text, svc.script
