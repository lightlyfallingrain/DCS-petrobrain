from launcher.envfile import default_services, parse_env


def test_export_lines_quotes_and_comments() -> None:
    text = """
# a comment
export PETROBRAIN_PATH=/mnt/d/Code/DCS-petrobrain
export SOX_PATH='C:\\Program Files\\sox\\sox.exe'
MAC_IP=192.168.1.10   # trailing comment
export EMPTY=
not an assignment
"""
    env = parse_env(text)
    assert env == {
        "PETROBRAIN_PATH": "/mnt/d/Code/DCS-petrobrain",
        "SOX_PATH": "C:\\Program Files\\sox\\sox.exe",
        "MAC_IP": "192.168.1.10",
        "EMPTY": "",
    }


def test_default_services_plural_wins_and_trims() -> None:
    assert default_services({"DEFAULT_SERVICES": "brain, piper,,body-layer"}) == [
        "brain",
        "piper",
        "body-layer",
    ]
    assert default_services({"DEFAULT_SERVICE": "brain"}) == ["brain"]
    assert default_services({}) == []
