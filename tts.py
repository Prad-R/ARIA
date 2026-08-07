"""
ARIA - text-to-speech via Piper.
Cleans LLM output of formatting characters that sound broken when read
aloud (safety net in case the LLM ignores the system prompt's rules),
then synthesizes and plays the audio.
"""
import re
import subprocess
import time

import soundfile as sf
import sounddevice as sd

import config
from hud_bridge import set_hud_state, should_stop_speaking, clear_stop_speaking


def clean_for_speech(text: str) -> str:
    """
    Safety net in case the LLM ignores the system prompt's formatting rules.
    Strips markdown/formatting characters that sound broken when read aloud
    by TTS, and normalizes some punctuation to speech-friendly equivalents.
    """
    # Replace dashes/hyphens used as pause punctuation with a comma-like pause
    text = re.sub(r"\s*[-–—]{1,3}\s*", ", ", text)
    # Collapse ellipses to a single period
    text = re.sub(r"\.{2,}", ".", text)
    # Strip markdown emphasis/formatting characters
    text = re.sub(r"[*_`#]+", "", text)
    # Strip bullet/list markers at line starts
    text = re.sub(r"^\s*[\-\*•]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    # Collapse any resulting double spaces/newlines
    text = re.sub(r"\n+", ". ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def speak(text: str):
    text = clean_for_speech(text)
    # Piper synthesis happens here first - the HUD should still show
    # "thinking" during this, not "speaking", since no sound is out yet.
    subprocess.run(
        [config.PIPER_BINARY, "--model", config.PIPER_VOICE_MODEL, "--output_file", config.TTS_FILE],
        input=text.encode("utf-8"),
        check=True,
    )
    data, sr = sf.read(config.TTS_FILE)

    # Clear any stale interrupt signal from before this turn started, so an
    # old click doesn't immediately cut off a fresh reply.
    clear_stop_speaking()

    # Only now, right as audio actually starts playing, switch the HUD to speaking.
    set_hud_state(state="speaking")
    sd.play(data, sr)

    # Poll instead of a blocking sd.wait(), so a "stop speaking" request
    # (from the tray icon) can interrupt playback immediately rather than
    # having to wait for the whole reply to finish.
    stream = sd.get_stream()
    while stream is not None and stream.active:
        if should_stop_speaking():
            print("[speech interrupted]")
            sd.stop()
            clear_stop_speaking()
            break
        time.sleep(0.1)