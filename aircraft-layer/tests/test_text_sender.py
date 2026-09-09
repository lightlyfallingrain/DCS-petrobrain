from __future__ import annotations

import json
import socket

from collector.text_sender import MAX_LINE_LENGTH, TextOverlaySender


def test_send_line_delivers_well_formed_datagram() -> None:
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(("127.0.0.1", 0))
    receiver.settimeout(2.0)
    port = receiver.getsockname()[1]

    try:
        with TextOverlaySender(host="127.0.0.1", port=port) as sender:
            sender.send_line("CONTACT_DETECTED: BMP-2, high certainty")

        data, _addr = receiver.recvfrom(4096)
        decoded = json.loads(data.decode("utf-8"))
        assert decoded == {"text": "CONTACT_DETECTED: BMP-2, high certainty"}
    finally:
        receiver.close()


def test_send_line_truncates_to_max_line_length() -> None:
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(("127.0.0.1", 0))
    receiver.settimeout(2.0)
    port = receiver.getsockname()[1]

    try:
        with TextOverlaySender(host="127.0.0.1", port=port) as sender:
            sender.send_line("x" * (MAX_LINE_LENGTH + 50))

        data, _addr = receiver.recvfrom(4096)
        decoded = json.loads(data.decode("utf-8"))
        assert decoded == {"text": "x" * MAX_LINE_LENGTH}
    finally:
        receiver.close()


def test_send_line_to_closed_port_does_not_raise() -> None:
    # No receiver bound on this port -- on a real OS this can provoke an
    # ICMP port-unreachable / ECONNRESET-class OSError on a subsequent send,
    # which `send_line` must swallow rather than propagate (a missing
    # listener -- DCS not running, or running without the overlay Hook
    # script -- is an expected state, not an error).
    unused = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    unused.bind(("127.0.0.1", 0))
    port = unused.getsockname()[1]
    unused.close()

    sender = TextOverlaySender(host="127.0.0.1", port=port)
    try:
        sender.send_line("no listener here")
    finally:
        sender.close()


def test_send_line_opens_socket_lazily_if_not_opened() -> None:
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(("127.0.0.1", 0))
    receiver.settimeout(2.0)
    port = receiver.getsockname()[1]

    sender = TextOverlaySender(host="127.0.0.1", port=port)
    try:
        sender.send_line("no explicit open() call")
        data, _addr = receiver.recvfrom(4096)
        assert json.loads(data.decode("utf-8")) == {"text": "no explicit open() call"}
    finally:
        sender.close()
        receiver.close()
