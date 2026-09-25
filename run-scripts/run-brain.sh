source ./petrobrain.env
# No --host: server.py's own DEFAULT_HOST is 127.0.0.1, which is correct here.
# Unlike audio-adapter and the aircraft-layer collector, BOTH ends of this seam
# run on the Mac -- body-layer talks to brain-layer over loopback and nothing
# crosses the LAN. Binding all interfaces exposed POST /escalate to any device
# on the network for no benefit (security review, 2026-09-25). Pass --host
# explicitly if that ever stops being true.
pushd $PETROBRAIN_PATH/brain-layer/ && PYTHONPATH=src .venv/bin/python -m brain_layer \
    --stub-delay-s 0 \
    $@
popd
