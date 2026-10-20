# Note: piper must be installed with *windows* python
# In windows power shell (or command prompt, I guess)
# cd <suitable-location>
# python.exe -m venv piper-venv
# cd piper-venv/Scripts
# ./pip.exe install "piper-tts[http]"
# mkdir <suitable-location>/piper-voices
# ./python.exe -m piper.download_voices en_GB-northern_english_male-medium --download-dir <suitable-location>/piper-voices
#
# Add to DCS-Petrobrain/run-scripts/petrobrain.env:
# export PIPER_VENV_PYTHON=<suitable-location>/piper-venv/Scripts/python.exe
# export PIPER_VOICES_DIR=<suitable-location>/piper-voices
source ./petrobrain.env
$PIPER_VENV_PYTHON -m piper.http_server \
    --host 127.0.0.1 --port 7800 \
    --model en_GB-northern_english_male-medium \
    --data-dir $PIPER_VOICES_DIR
