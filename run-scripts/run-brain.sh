source ./petrobrain.env
# No --host: server.py's own DEFAULT_HOST is 127.0.0.1, and loopback is the
# right *default* -- binding all interfaces exposed POST /escalate to every
# device on the network, which bought nothing in the setup this script is
# written for, where body-layer and brain-layer share a machine (security
# review, 2026-09-25).
#
# **That is a fact about the current deployment, not about the service.** Only
# aircraft-layer is pinned to a machine, because it needs the DCS installation;
# every other service here can run wherever, and the seams are HTTP precisely
# so they can (user, 2026-09-25). If brain-layer ends up on a different box
# from body-layer, pass `--host 0.0.0.0` explicitly -- which is why this script
# omits the flag rather than the binary hardcoding loopback.
# Relative, not $PETROBRAIN_PATH -- that variable holds the WSL/Windows path
# (/mnt/d/...) and does not resolve on the Mac, where this service runs.
pushd ../brain-layer/ && PYTHONPATH=src .venv/bin/python -m brain_layer \
    --stub-delay-s 0 \
    $@
popd
