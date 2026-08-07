"""
ARIA - Adaptive & Responsive Intelligence Agent
Full pipeline: VAD-gated recording -> Whisper (STT) -> wake-word check ->
Ollama (LLM) -> Piper (TTS) -> Playback.

Wake word ("ARIA") is checked via fuzzy-matching the Whisper transcript,
since openWakeWord has no pretrained "ARIA" model and training a custom
one is a bigger separate project.
"""
import difflib
import json
import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

PIPER_BINARY = os.path.join(os.path.dirname(sys.executable), "piper")
import re
import subprocess
import time

import numpy as np
import sounddevice as sd
import soundfile as sf
import webrtcvad
import ollama
from faster_whisper import WhisperModel

# ---- Audio / VAD config (tuned values from calibration) ----
SAMPLE_RATE = 16000  # target rate for Whisper output file naming/reference
FRAME_DURATION_MS = 30

# Hardcoded to the laptop's built-in mic (sof-hda-dsp, hw:1,7).
# This bypasses PulseAudio's "default source" entirely, so it keeps working
# correctly even when the Echo Dot is connected over Bluetooth and would
# otherwise hijack the default input device.
MIC_DEVICE_INDEX = 8

# Raw ALSA hardware devices (like our hardcoded mic) often only support their
# native rate (commonly 48000Hz), unlike PulseAudio's virtual devices which
# auto-resample. So we query and record at whatever rate the device actually
# supports, and let webrtcvad (which supports 48000Hz) and Whisper (which
# resamples internally) handle that rate directly.
_device_info = sd.query_devices(MIC_DEVICE_INDEX)
MIC_SAMPLE_RATE = int(_device_info["default_samplerate"])
FRAME_SIZE = int(MIC_SAMPLE_RATE * FRAME_DURATION_MS / 1000)

_WEBRTCVAD_SUPPORTED_RATES = (8000, 16000, 32000, 48000)
if MIC_SAMPLE_RATE not in _WEBRTCVAD_SUPPORTED_RATES:
    raise RuntimeError(
        f"Mic device {MIC_DEVICE_INDEX} reports {MIC_SAMPLE_RATE}Hz, which "
        f"webrtcvad doesn't support (needs one of {_WEBRTCVAD_SUPPORTED_RATES}). "
        f"Check `python find_mic_device.py` output and adjust handling if needed."
    )

VAD_AGGRESSIVENESS = 3
SILENCE_FRAMES_THRESHOLD = int(2000 / FRAME_DURATION_MS)   # ~2 seconds of silence
TRIGGER_FRAMES_THRESHOLD = 3                                 # ~90ms of continuous speech
ENERGY_THRESHOLD = 400                                        # RMS floor to count as real speech
WARMUP_FRAMES = 10
MAX_RECORD_SECONDS = 15

RECORDING_FILE = "turn_input.wav"
TTS_FILE = "turn_output.wav"

WHISPER_MODEL_SIZE = "base"
OLLAMA_MODEL = "llama3.2:3b"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PIPER_VOICE_MODEL = os.path.join(SCRIPT_DIR, "piper_voices", "en_US-lessac-medium.onnx")

# ---- Wake word config ----
# Common ways Whisper might mishear "ARIA" - add more here if you notice new ones
WAKE_WORD_VARIANTS = ["aria", "area", "are ya", "ares", "arya", "asia", "ari", "ariah", "arriya"]
WAKE_WORD_MATCH_THRESHOLD = 0.7  # 0-1, similarity ratio required to count as a match

# ---- HUD state broadcasting ----
# A tiny local HTTP server that serves ARIA's current state as JSON, so a
# separate HUD window (hud.py) can poll it and show live status/transcript
# without being coupled to the voice pipeline itself.
HUD_SERVER_PORT = 8765

_hud_state = {
    "state": "idle",        # idle | listening | thinking | speaking
    "heard": "",
    "reply": "",
    "timestamp": time.time(),
}
_hud_state_lock = threading.Lock()


def set_hud_state(**kwargs):
    with _hud_state_lock:
        _hud_state.update(kwargs)
        _hud_state["timestamp"] = time.time()


def reset_hud_idle():
    """Goes back to idle and clears any leftover transcript/reply text."""
    set_hud_state(state="idle", heard="", reply="")


class _HudStateHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/state":
            self.send_response(404)
            self.end_headers()
            return
        with _hud_state_lock:
            body = json.dumps(_hud_state).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")  # HUD window fetches cross-origin
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # silence default request logging, it's noisy


def start_hud_server():
    server = HTTPServer(("127.0.0.1", HUD_SERVER_PORT), _HudStateHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[HUD state server running on http://127.0.0.1:{HUD_SERVER_PORT}/state]")


SYSTEM_PROMPT = (
    "You are ARIA (short for Adaptive & Responsive Intelligence Agent), a voice assistant. "
    "You do not have a chat window or a screen. Every word you output gets converted "
    "directly to speech and spoken out loud through a speaker, and every word the user "
    "says gets transcribed from audio into your input. This is a real-time spoken "
    "conversation, not a text chat.\n\n"
    "Because of this:\n"
    "- Never use hyphens, dashes, ellipses, asterisks, bullet points, numbered lists, "
    "markdown, or any visual formatting. A text-to-speech engine will read every "
    "character literally, including punctuation, so unusual punctuation sounds broken "
    "or confusing out loud.\n"
    "- Write only in plain, complete sentences using periods, commas, and question marks.\n"
    "- Keep responses short and conversational, ideally one to three sentences, the way "
    "a person would actually speak in conversation, not the way someone would write "
    "a document.\n"
    "- Do not describe visual things you can't actually show, since the user cannot see "
    "anything, only hear you.\n"
    "- Do not use quotation marks around your own words or describe what you are "
    "doing as you say it. Just say the answer directly and naturally, the way a "
    "person would, without narrating or quoting yourself.\n"
    "- If you would normally give a list, say the items in a flowing sentence instead, "
    "for example 'you could do X, Y, or Z' rather than separate bullet points."
)

# ---- Load models once at startup (not per-turn - keeps latency low) ----
print("Loading Whisper model...")
whisper_model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")

conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]

# Cap how many user/assistant turn-pairs we keep, so context sent to the LLM
# (and thus latency) doesn't grow unbounded over a long-running service.
# The system prompt (index 0) is always kept regardless.
MAX_HISTORY_TURNS = 15  # ~15 back-and-forth exchanges, fits comfortably in 8192 ctx


def strip_punctuation(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text).lower().strip()


def find_wake_word_index(text: str):
    """
    Returns the index (in the raw word list) of the first word/word-pair that
    fuzzy-matches the wake word, or None if no match is found.
    Checks both single words and adjacent two-word pairs (e.g. "are ya").
    """
    raw_words = text.strip().split()
    cleaned_words = [strip_punctuation(w) for w in raw_words]

    for i in range(min(len(cleaned_words), 3)):  # only check near the start
        # single word check
        for variant in WAKE_WORD_VARIANTS:
            similarity = difflib.SequenceMatcher(None, cleaned_words[i], variant).ratio()
            if similarity >= WAKE_WORD_MATCH_THRESHOLD:
                return i
        # two-word check (e.g. "are ya")
        if i + 1 < len(cleaned_words):
            pair = f"{cleaned_words[i]} {cleaned_words[i + 1]}"
            for variant in WAKE_WORD_VARIANTS:
                similarity = difflib.SequenceMatcher(None, pair, variant).ratio()
                if similarity >= WAKE_WORD_MATCH_THRESHOLD:
                    return i + 1  # command starts after both words
    return None


def rms_energy(audio_chunk):
    samples = audio_chunk.astype(np.float32)
    return np.sqrt(np.mean(samples ** 2))


def record_with_vad() -> bool:
    """Records until silence is detected. Returns True if speech was captured."""
    import collections

    vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
    frames = []
    silence_count = 0
    triggered = False
    max_frames = int(MAX_RECORD_SECONDS * 1000 / FRAME_DURATION_MS)

    print("\n[Listening...]")

    stream = sd.InputStream(samplerate=MIC_SAMPLE_RATE, channels=1, dtype="int16",
                             blocksize=FRAME_SIZE, device=MIC_DEVICE_INDEX)
    stream.start()

    # Instead of blindly discarding the first WARMUP_FRAMES (which used to eat
    # the start of words like "hey ARIA" if you spoke immediately), we keep a
    # rolling buffer of that audio. We just don't use those frames to decide
    # whether speech has started (dodges the stream-startup click artifact),
    # but the actual audio is preserved and gets included once real speech
    # is confirmed shortly after.
    prebuffer = collections.deque(maxlen=WARMUP_FRAMES)
    frame_count = 0

    speech_run = 0
    pending_frames = []

    for _ in range(max_frames):
        audio_chunk, _ = stream.read(FRAME_SIZE)
        frame_count += 1

        if frame_count <= WARMUP_FRAMES:
            # Still in the warmup window - store audio but don't evaluate
            # VAD/energy on it yet, since this window can contain a click
            # artifact from the stream just starting.
            prebuffer.append(audio_chunk.copy())
            continue

        frame_bytes = audio_chunk.tobytes()
        vad_says_speech = vad.is_speech(frame_bytes, MIC_SAMPLE_RATE)
        energy = rms_energy(audio_chunk)
        is_speech = vad_says_speech and energy > ENERGY_THRESHOLD

        if not triggered:
            if is_speech:
                speech_run += 1
                pending_frames.append(audio_chunk.copy())
                if speech_run >= TRIGGER_FRAMES_THRESHOLD:
                    print("[speech detected, recording...]")
                    set_hud_state(state="listening")
                    triggered = True
                    # Prepend the pre-buffered audio too, in case the word
                    # actually started during the warmup window.
                    frames.extend(prebuffer)
                    frames.extend(pending_frames)
                    pending_frames = []
            else:
                speech_run = 0
                pending_frames = []
        else:
            frames.append(audio_chunk.copy())
            if is_speech:
                silence_count = 0
            else:
                silence_count += 1
                if silence_count > SILENCE_FRAMES_THRESHOLD:
                    print("[silence detected, stopping]")
                    break

    stream.stop()
    stream.close()

    if not frames:
        return False

    audio_data = np.concatenate(frames, axis=0)
    sf.write(RECORDING_FILE, audio_data, MIC_SAMPLE_RATE)
    return True


def transcribe_audio() -> str:
    segments, _ = whisper_model.transcribe(
        RECORDING_FILE,
        beam_size=5,
        initial_prompt="ARIA",  # nudges Whisper to expect this word
    )
    text = "".join(seg.text for seg in segments).strip()
    return text


def trim_history():
    """Keeps the system prompt plus only the most recent N turn-pairs."""
    global conversation_history
    system_msg = conversation_history[0]
    turns = conversation_history[1:]  # everything except system prompt
    max_messages = MAX_HISTORY_TURNS * 2  # each turn = 1 user + 1 assistant message
    if len(turns) > max_messages:
        turns = turns[-max_messages:]
    conversation_history = [system_msg] + turns


def ask_llm(user_text: str) -> str:
    conversation_history.append({"role": "user", "content": user_text})
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=conversation_history,
        options={"num_ctx": 8192},  # Ollama defaults to 2048 regardless of model's real max
    )
    reply = response["message"]["content"]
    conversation_history.append({"role": "assistant", "content": reply})
    trim_history()
    return reply


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
        [PIPER_BINARY, "--model", PIPER_VOICE_MODEL, "--output_file", TTS_FILE],
        input=text.encode("utf-8"),
        check=True,
    )
    data, sr = sf.read(TTS_FILE)
    # Only now, right as audio actually starts playing, switch the HUD to speaking.
    set_hud_state(state="speaking")
    sd.play(data, sr)
    sd.wait()


def run_turn():
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

    # Always broadcast what was heard to the HUD, even if it's not for ARIA -
    # this is the main "am I even being picked up correctly" feedback loop.
    set_hud_state(heard=user_text)

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