"""
Step 2: Confirm speech-to-text works.
Transcribes the recording from Step 1 using faster-whisper.
"""
from faster_whisper import WhisperModel
import time

FILENAME = "test_recording.wav"

# Model sizes: tiny, base, small, medium, large-v3
# Start with "base" — good accuracy/speed balance for a laptop CPU.
MODEL_SIZE = "base"

def transcribe():
    print(f"Loading Whisper model ({MODEL_SIZE})... first run will download it.")

    # device="cpu" for now — we'll test GPU later once the pipeline works.
    # compute_type="int8" is fastest on CPU with minimal accuracy loss.
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

    print(f"Transcribing {FILENAME}...")
    start = time.time()

    segments, info = model.transcribe(FILENAME, beam_size=5)

    print(f"Detected language: {info.language} (probability {info.language_probability:.2f})")
    print(f"Transcription took {time.time() - start:.2f}s\n")

    print("--- Transcript ---")
    full_text = ""
    for segment in segments:
        print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
        full_text += segment.text

    print("\n--- Full text ---")
    print(full_text.strip())

if __name__ == "__main__":
    transcribe()