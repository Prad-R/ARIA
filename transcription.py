"""
ARIA - speech-to-text via faster-whisper.
Model loads once at import time (not per-turn) to keep latency low.
"""
from faster_whisper import WhisperModel

import config

print("Loading Whisper model...")
_whisper_model = WhisperModel(config.WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")


def transcribe_audio() -> str:
    segments, _ = _whisper_model.transcribe(
        config.RECORDING_FILE,
        beam_size=5,
        initial_prompt="ARIA",  # nudges Whisper to expect this word
    )
    text = "".join(seg.text for seg in segments).strip()
    return text
