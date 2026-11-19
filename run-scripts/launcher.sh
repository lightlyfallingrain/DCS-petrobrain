# Text UI that starts, stops and watches the services (todo/backlog/X-B40.md).
# Stdlib only: launcher/.venv if it exists, otherwise any python3 >= 3.11.
cd "$(dirname "$0")/../launcher/src" || exit 1
PY=../.venv/bin/python
[ -x "$PY" ] || PY=python3
exec "$PY" -m launcher
