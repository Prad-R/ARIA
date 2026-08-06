"""
Step 1: Confirm mic input + speaker output work.
Records 5 seconds of audio, saves it, then plays it back.
"""
import sounddevice as sd
import soundfile as sf

DURATION = 5  # seconds
SAMPLE_RATE = 16000  # 16kHz is standard for speech models (Whisper wants this)
FILENAME = "test_recording.wav"

def record():
    print(f"Recording for {DURATION} seconds... speak now.")
    audio = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    sf.write(FILENAME, audio, SAMPLE_RATE)
    print(f"Saved to {FILENAME}")

def playback():
    print("Playing back...")
    data, sr = sf.read(FILENAME)
    sd.play(data, sr)
    sd.wait()
    print("Done.")

if __name__ == "__main__":
    # List available devices first — useful if the wrong mic/speaker gets picked
    print("Available audio devices:")
    print(sd.query_devices())
    print()

    record()
    playback()