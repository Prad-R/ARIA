# ARIA

ARIA is a voice-first desktop assistant for Linux. It listens for a wake word, turns your speech into text, sends your request to a local language model, speaks the answer back out loud, and shows a small live status window while it works.

The project is meant to feel simple and helpful rather than overly technical. You can talk to it naturally, and it will respond like a small local assistant running on your own machine.

## What ARIA can do

- Listen for your voice and wake up when you say "ARIA"
- Turn your spoken request into text
- Send that request to a local model through Ollama
- Speak the reply back using Piper
- Show a small HUD with live status and transcript text
- Switch audio input and output devices from a system tray menu

## How it works

The app follows a simple flow:

1. It listens to the microphone.
2. It detects when someone is speaking.
3. It turns that speech into text.
4. It looks for the wake word.
5. It sends the request to a local language model.
6. It speaks the reply back out loud.

This is split into a few small files so each part is easier to understand and tweak.

## Project structure

- [aria_main.py](aria_main.py) - the main loop that runs the full conversation flow
- [audio_capture.py](audio_capture.py) - listens to the microphone and detects speech
- [transcription.py](transcription.py) - converts speech to text
- [wake_word.py](wake_word.py) - looks for the wake word in the transcript
- [llm.py](llm.py) - sends requests to Ollama and keeps recent chat context
- [tts.py](tts.py) - turns replies into spoken audio
- [hud_bridge.py](hud_bridge.py) - shares live state with the HUD
- [hud/](hud/) - the visual HUD window and device switcher tools
- [component_testing/](component_testing/) - small helper scripts for testing audio, speech, Whisper, Piper, and Ollama

## Requirements

Before using ARIA, make sure you have:

- A Linux desktop environment
- Python 3.10 or newer
- Ollama installed and running
- Piper installed and available on your system
- A working microphone and speakers
- PulseAudio or PipeWire tools such as pactl available for the device switcher

## Quick start

### 1. Install the Python packages

Install the main dependencies with:

```bash
pip install faster-whisper numpy sounddevice soundfile webrtcvad ollama pywebview PyQt5
```

### 2. Start Ollama

Make sure Ollama is available locally:

```bash
ollama serve
```

If needed, pull the default model used by the project:

```bash
ollama pull llama3.2:3b
```

### 3. Make sure Piper is installed

ARIA expects a Piper binary to be available on your system. If it is not installed yet, install Piper and make sure the `piper` command works.

### 4. Start ARIA

Run the main assistant:

```bash
python aria_main.py
```

Once it is running, say something like:

```text
ARIA what is the weather today
```

### 5. Start the HUD (optional but recommended)

Open a second terminal and launch the visual HUD:

```bash
python hud/hud.py
```

You can also use the helper launcher in the HUD folder.

### 6. Start the device switcher (optional)

If you want to change input or output devices from a tray icon, run:

```bash
python hud/device_switcher.py
```

## How to use it

- Speak clearly and keep your request short at first.
- The assistant waits for a wake word, so it is best to say "ARIA" first.
- The HUD will show what it heard and what it replied with.
- If the microphone does not seem to work, check the device settings in [config.py](config.py).

## Configuration

Most of the project settings live in [config.py](config.py). You can adjust things like:

- the microphone device
- the wake word behavior
- the model name used by Ollama
- the HUD port
- the voice settings

The microphone is currently set up in a fairly specific way in [config.py](config.py), so if your hardware is different you may need to adjust that value.

## Testing helpers

The [component_testing/](component_testing/) folder contains small scripts for checking the main pieces separately:

- microphone input
- speech detection
- Whisper transcription
- Ollama connectivity
- Piper speech output

These are useful if something is not working and you want to narrow down the issue.

## Notes

- ARIA is designed to run mostly locally, so it does not depend on an external cloud service for the core voice flow.
- The default setup is tuned for a simple, spoken, real-time assistant experience.
- The project is intentionally easy to inspect and modify, which makes it a good fit for learning and experimentation.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
