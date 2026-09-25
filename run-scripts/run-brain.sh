source ./petrobrain.env
pushd $PETROBRAIN_PATH/brain-layer/ && PYTHONPATH=src .venv/bin/python -m brain_layer \
    --host 0.0.0.0 \
    --stub-delay-s 0 \
    $@
popd
