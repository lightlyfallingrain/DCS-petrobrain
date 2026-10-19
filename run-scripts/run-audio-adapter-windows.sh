source ./petrobrain.env
pushd $PETROBRAIN_PATH/audio-adapter/src && python.exe -m audio_adapter --host 0.0.0.0 "$@"
popd
