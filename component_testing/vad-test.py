"""
Step 5a: VAD-based recording - stops automatically after detecting silence.
Run with --debug to see calibration/energy diagnostics if tuning is needed again.
"""
import argparse
import sounddevice as sd
import soundfile as sf
import numpy as np
import webrtcvad

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 30  # webrtcvad supports 10, 20, or 30 ms frames
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)

VAD_AGGRESSIVENESS = 3
SILENCE_FRAMES_THRESHOLD = int(2000 / FRAME_DURATION_MS)   # ~2 seconds of silence
TRIGGER_FRAMES_THRESHOLD = 3                                 # ~90ms of continuous speech
ENERGY_THRESHOLD = 400                                        # RMS floor to count as real speech

WARMUP_FRAMES = 10
MAX_RECORD_SECONDS = 15
OUTPUT_FILE = "vad_test.wav"


def rms_energy(audio_chunk):
    samples = audio_chunk.astype(np.float32)
    return np.sqrt(np.mean(samples ** 2))


def record_with_vad(debug=False):
    vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
    frames = []
    silence_count = 0
    triggered = False
    max_frames = int(MAX_RECORD_SECONDS * 1000 / FRAME_DURATION_MS)

    print("Listening... (speak whenever you're ready)")

    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=FRAME_SIZE)
    stream.start()

    for _ in range(WARMUP_FRAMES):
        stream.read(FRAME_SIZE)

    if debug:
        print("[debug: ambient energy for 30 frames, stay silent]")
        for i in range(30):
            chunk, _ = stream.read(FRAME_SIZE)
            print(f"  frame {i}: energy={rms_energy(chunk):.1f}")
        print("[debug done]\n")

    speech_run = 0
    pending_frames = []

    for _ in range(max_frames):
        audio_chunk, _ = stream.read(FRAME_SIZE)
        frame_bytes = audio_chunk.tobytes()

        vad_says_speech = vad.is_speech(frame_bytes, SAMPLE_RATE)
        energy = rms_energy(audio_chunk)
        is_speech = vad_says_speech and energy > ENERGY_THRESHOLD

        if not triggered:
            if is_speech:
                speech_run += 1
                pending_frames.append(audio_chunk.copy())
                if debug:
                    print(f"  [candidate] energy={energy:.1f} vad={vad_says_speech} run={speech_run}")
                if speech_run >= TRIGGER_FRAMES_THRESHOLD:
                    print("[speech detected, recording...]")
                    triggered = True
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
        print("No speech detected.")
        return None

    audio_data = np.concatenate(frames, axis=0)
    sf.write(OUTPUT_FILE, audio_data, SAMPLE_RATE)
    duration = len(audio_data) / SAMPLE_RATE
    print(f"Saved {duration:.1f}s of audio to {OUTPUT_FILE}")
    return OUTPUT_FILE


def playback(filename):
    data, sr = sf.read(filename)
    sd.play(data, sr)
    sd.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Show calibration and per-frame trigger diagnostics")
    args = parser.parse_args()

    result = record_with_vad(debug=args.debug)
    if result:
        print("Playing back what was recorded...")
        playback(result)