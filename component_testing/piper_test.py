"""
Step 4: Confirm text-to-speech works via Piper.
Converts a test sentence to speech and plays it back.
"""
import subprocess
import sounddevice as sd
import soundfile as sf
import time

TEST_TEXT = "Hello, I am ARIA, your voice assistant. This is a test of the speech synthesis system."
OUTPUT_FILE = "tts_test.wav"

# Path to the piper voice model you downloaded.
# e.g. en_US-lessac-medium.onnx (get from https://github.com/rhasspy/piper/releases
# or huggingface.co/rhasspy/piper-voices)
VOICE_MODEL = "../piper_voices/en_US-lessac-medium.onnx"

def synthesize(text: str):
    print(f"Synthesizing: \"{text}\"")
    start = time.time()

    # piper reads text from stdin, writes wav to --output_file
    subprocess.run(
        ["piper", "--model", VOICE_MODEL, "--output_file", OUTPUT_FILE],
        input=text.encode("utf-8"),
        check=True,
    )

    print(f"Synthesis took {time.time() - start:.2f}s")
    print(f"Saved to {OUTPUT_FILE}")

def playback():
    print("Playing back...")
    data, sr = sf.read(OUTPUT_FILE)
    sd.play(data, sr)
    sd.wait()
    print("Done.")

if __name__ == "__main__":
    synthesize(TEST_TEXT)
    playback()