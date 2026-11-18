source ./petrobrain.env
pushd $PETROBRAIN_PATH/body-layer
.venv/bin/python tools/check_rules.py
popd

