"""
Test a specific device index for mic input.
Usage: python test_mic_device.py <device_index>
"""
import sys
import sounddevice as sd
import soundfile as sf

DEVICE_INDEX = int(sys.argv[1]) if len(sys.argv) > 1 else None
DURATION = 4
SAMPLE_RATE = 16000
FILENAME = f"test_device_{DEVICE_INDEX}.wav"

print(f"Testing device index {DEVICE_INDEX}...")
print(f"Recording {DURATION}s - speak now.")

audio = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                channels=1, dtype="int16", device=DEVICE_INDEX)
sd.wait()
sf.write(FILENAME, audio, SAMPLE_RATE)
print(f"Saved to {FILENAME}")

print("Playing back...")
sd.play(audio, SAMPLE_RATE)
sd.wait()
print("Done.")