"""
ARIA - Adaptive & Responsive Intelligence Agent
Entry point. Orchestrates: VAD-gated recording -> Whisper (STT) ->
wake-word check -> Ollama (LLM) -> Piper (TTS) -> Playback.

Individual pieces live in their own modules:
  config.py          - all constants
  audio_capture.py   - mic recording + VAD
  transcription.py   - Whisper STT
  wake_word.py       - fuzzy "ARIA" matching
  llm.py             - Ollama chat + conversation history
  tts.py             - Piper synthesis + playback
  hud_bridge.py      - HUD state broadcasting + shared prefs server
"""
import time

from audio_capture import record_with_vad
from transcription import transcribe_audio
from wake_word import find_wake_word_index
from llm import ask_llm
from tts import speak
from hud_bridge import (
    set_hud_state,
    reset_hud_idle,
    start_hud_server,
    is_muted,
    is_free_listening,
)


def run_turn():
    if is_muted():
        # Muted: don't touch the mic at all. Just idle-wait and re-check
        # next loop, so nothing is captured or processed while muted.
        set_hud_state(state="muted")
        time.sleep(0.3)
        return

    reset_hud_idle()
    t0 = time.time()
    got_speech = record_with_vad()

    if not got_speech:
        print("(Heard nothing, listening again.)")
        reset_hud_idle()
        return

    set_hud_state(state="thinking")
    t1 = time.time()
    user_text = transcribe_audio()
    print(f"Heard: \"{user_text}\"  ({time.time() - t1:.2f}s)")

    if not user_text.strip():
        print("(Transcription empty, listening again.)")
        reset_hud_idle()
        return

    # Always broadcast what was heard to the HUD - this is the main
    # "am I even being picked up correctly" feedback loop.
    set_hud_state(heard=user_text)

    if is_free_listening():
        # No wake word needed - treat the whole utterance as the command.
        command_text = user_text.strip()
        print("[free listening: no wake word required]")
    else:
        wake_idx = find_wake_word_index(user_text)
        if wake_idx is None:
            print("(No wake word detected, ignoring.)")
            reset_hud_idle()
            return

        words = user_text.strip().split()
        command_text = " ".join(words[wake_idx + 1:]).strip()

        if not command_text:
            print("(Heard only the wake word, nothing to act on. Listening again.)")
            reset_hud_idle()
            return

    print(f"Command: \"{command_text}\"")

    t2 = time.time()
    reply = ask_llm(command_text)
    print(f"ARIA: \"{reply}\"  ({time.time() - t2:.2f}s)")
    set_hud_state(reply=reply)  # text ready to show; state flips to "speaking" once audio actually starts

    t3 = time.time()
    speak(reply)
    print(f"(spoke in {time.time() - t3:.2f}s, total turn: {time.time() - t0:.2f}s)")
    reset_hud_idle()


if __name__ == "__main__":
    print("ARIA is ready. Say \"ARIA\" followed by your request. Ctrl+C to quit.")
    start_hud_server()
    try:
        while True:
            run_turn()
    except KeyboardInterrupt:
        print("\nGoodbye.")