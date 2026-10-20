source ./petrobrain.env
pushd $PETROBRAIN_PATH/audio-adapter/src && python.exe -m audio_adapter --host 0.0.0.0 "$@" --whisper-binary 'E:\whisper\cpu\whisper-cli.exe'  --whisper-model  'E:\whisper-models\ggml-small.en.bin' --target aircraft-layer --aircraft-layer-url http://$DCS_COLLECTOR_IP:7791 
popd
