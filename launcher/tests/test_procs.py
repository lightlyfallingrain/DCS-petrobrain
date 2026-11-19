import time
from pathlib import Path

from launcher.procs import RunState, ServiceProcess
from launcher.services import Service


def test_service_reading_stdin_stays_on_until_stopped(tmp_path: Path) -> None:
    """body-layer's main thread is a stdin REPL: an EOF on start used to end it at once."""
    (tmp_path / "run-repl.sh").write_text("cat > /dev/null\necho got-eof\n")
    proc = ServiceProcess(Service("repl", "run-repl.sh"), tmp_path)
    proc.start([])
    time.sleep(0.5)
    running = proc.state
    proc.stop_and_wait()
    stopped = proc.state
    assert running is RunState.ON
    assert stopped is RunState.OFF
    assert "got-eof" not in proc.log
