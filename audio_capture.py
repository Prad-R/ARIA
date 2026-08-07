"""
ARIA - microphone capture with VAD (voice activity detection).
Records until silence is detected, gating false triggers via both
webrtcvad and an RMS energy floor (filters quiet noise VAD misreads
as speech based on frequency shape alone).
"""
import collections

import numpy as np
import sounddevice as sd
import soundfile as sf
import webrtcvad

import config
from hud_bridge import set_hud_state, is_muted


def rms_energy(audio_chunk):
    samples = audio_chunk.astype(np.float32)
    return np.sqrt(np.mean(samples ** 2))


def record_with_vad() -> bool:
    """Records until silence is detected. Returns True if speech was captured."""
    vad = webrtcvad.Vad(config.VAD_AGGRESSIVENESS)
    frames = []
    silence_count = 0
    triggered = False
    max_frames = int(config.MAX_RECORD_SECONDS * 1000 / config.FRAME_DURATION_MS)

    print("\n[Listening...]")

    stream = sd.InputStream(samplerate=config.MIC_SAMPLE_RATE, channels=1, dtype="int16",
                             blocksize=config.FRAME_SIZE, device=config.MIC_DEVICE_INDEX)
    stream.start()

    # Instead of blindly discarding the first WARMUP_FRAMES (which used to eat
    # the start of words like "hey ARIA" if you spoke immediately), we keep a
    # rolling buffer of that audio. We just don't use those frames to decide
    # whether speech has started (dodges the stream-startup click artifact),
    # but the actual audio is preserved and gets included once real speech
    # is confirmed shortly after.
    prebuffer = collections.deque(maxlen=config.WARMUP_FRAMES)
    frame_count = 0

    speech_run = 0
    pending_frames = []

    for _ in range(max_frames):
        # Check mute on every frame (not just once at the start of the turn)
        # so toggling it takes effect within ~30ms, not only after the
        # current up-to-15-second listening window finishes.
        if is_muted():
            print("[muted mid-recording, aborting]")
            stream.stop()
            stream.close()
            return False

        audio_chunk, _ = stream.read(config.FRAME_SIZE)
        frame_count += 1

        if frame_count <= config.WARMUP_FRAMES:
            # Still in the warmup window - store audio but don't evaluate
            # VAD/energy on it yet, since this window can contain a click
            # artifact from the stream just starting.
            prebuffer.append(audio_chunk.copy())
            continue

        frame_bytes = audio_chunk.tobytes()
        vad_says_speech = vad.is_speech(frame_bytes, config.MIC_SAMPLE_RATE)
        energy = rms_energy(audio_chunk)
        is_speech = vad_says_speech and energy > config.ENERGY_THRESHOLD

        if not triggered:
            if is_speech:
                speech_run += 1
                pending_frames.append(audio_chunk.copy())
                if speech_run >= config.TRIGGER_FRAMES_THRESHOLD:
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
                if silence_count > config.SILENCE_FRAMES_THRESHOLD:
                    print("[silence detected, stopping]")
                    break

    stream.stop()
    stream.close()

    if not frames:
        return False

    audio_data = np.concatenate(frames, axis=0)
    sf.write(config.RECORDING_FILE, audio_data, config.MIC_SAMPLE_RATE)
    return True