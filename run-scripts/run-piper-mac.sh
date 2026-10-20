source ./petrobrain.env
$PIPER_VENV_PYTHON -m piper.http_server \
    --host 127.0.0.1 --port 7800 \
    --model en_GB-northern_english_male-medium \
    --data-dir $PIPER_VOICES_DIR
