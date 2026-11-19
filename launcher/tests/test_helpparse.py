from launcher.helpparse import HelpOption, parse_help

# Shapes taken from brain-layer's and body-layer's real argparse output.
HELP = """usage: python -m brain_layer [-h] [--host HOST]
                             [--decider {stub,ollama,tool_loop}] [--debug]

Run the `brain-layer` process.

options:
  -h, --help            show this help message and exit
  --host HOST           listener host
  --decider {stub,ollama,tool_loop}
                        which Decider to run behind POST /escalate (default:
                        stub).
  --debug               verbose logging
  -v, --verbose         more output
  --forest-occlusion, --no-forest-occlusion
                        model forest occlusion
"""


def test_parse_help_options() -> None:
    assert parse_help(HELP) == [
        HelpOption("--host", True, "listener host"),
        HelpOption(
            "--decider", True, "which Decider to run behind POST /escalate (default:"
        ),
        HelpOption("--debug", False, "verbose logging"),
        HelpOption("--verbose", False, "more output"),
        HelpOption("--forest-occlusion", False, "model forest occlusion"),
        HelpOption("--no-forest-occlusion", False, "model forest occlusion"),
    ]


def test_usage_and_description_lines_are_not_options() -> None:
    assert parse_help("usage: x [-h]\n\nsome text --like this\n") == []
