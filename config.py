"""
ARIA - all configuration constants in one place.
Adjust values here rather than hunting through the other modules.
"""
import os
import sys

import sounddevice as sd

# ---- Paths ----
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PIPER_BINARY = os.path.join(os.path.dirname(sys.executable), "piper")
PIPER_VOICE_MODEL = os.path.join(SCRIPT_DIR, "piper_voices", "en_US-lessac-medium.onnx")
RECORDING_FILE = os.path.join(SCRIPT_DIR, "turn_input.wav")
TTS_FILE = os.path.join(SCRIPT_DIR, "turn_output.wav")

# ---- Audio / VAD config (tuned values from calibration) ----
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

# ---- Model config ----
WHISPER_MODEL_SIZE = "base"
OLLAMA_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
OLLAMA_NUM_CTX = 8192  # Ollama defaults to 2048 regardless of model's real max

# Qwen3 (and other hybrid-reasoning models) generate hidden "thinking" tokens
# before their actual answer, which costs real latency even though you never
# see them. For a real-time voice assistant, speed matters more than the
# extra deliberation, so this is off by default. Flip to True to compare -
# thinking mode may improve tool-call accuracy at the cost of response time.
OLLAMA_THINK = False

# Cap how many user/assistant turn-pairs we keep, so context sent to the LLM
# (and thus latency) doesn't grow unbounded over a long-running service.
MAX_HISTORY_TURNS = 15  # ~15 back-and-forth exchanges, fits comfortably in 8192 ctx

# ---- Wake word config ----
# Common ways Whisper might mishear "ARIA" - add more here if you notice new ones
WAKE_WORD_VARIANTS = ["aria", "area", "are ya", "ares", "arya", "asia", "ari", "ariah", "arriya"]
WAKE_WORD_MATCH_THRESHOLD = 0.7  # 0-1, similarity ratio required to count as a match

# ---- HUD state broadcasting ----
HUD_SERVER_PORT = 8765

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
    "for example 'you could do X, Y, or Z' rather than separate bullet points.\n"
    "- You have access to tools including web search. Only use a tool when you "
    "genuinely need current, factual, or specific information you don't already "
    "know. Do not use any tool for casual conversation, greetings, small talk, "
    "opinions, jokes, creative requests, or general knowledge you're already "
    "confident about. For example, 'how are you doing' or 'tell me something "
    "cool' should be answered directly and naturally, never by searching. Only "
    "search for things like current events, specific facts, or recent "
    "developments you're genuinely unsure about."
)