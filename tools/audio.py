"""
ARIA - system volume control via pactl.
"""
import re

import config
from ._shell import run_cli

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "control_volume",
            "description": (
                "Controls the system speaker volume. Use this when the user asks to "
                "change, set, increase, decrease, raise, lower, turn up, turn down, "
                "mute, or unmute the volume, audio, or sound. Also use it if they "
                "ask what the current volume is."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["get", "set", "increase", "decrease", "mute", "unmute", "toggle_mute"],
                        "description": (
                            "The action to perform. "
                            "'get' returns the current volume. "
                            "'set' sets it to an exact percentage (requires 'value'). "
                            "'increase' raises it by a step (optionally provide 'step'). "
                            "'decrease' lowers it by a step (optionally provide 'step'). "
                            "'mute' silences audio. 'unmute' restores it. "
                            "'toggle_mute' flips the mute state."
                        ),
                    },
                    "value": {
                        "type": "integer",
                        "description": "Target volume percentage (0-100). Only used when action is 'set'.",
                    },
                    "step": {
                        "type": "integer",
                        "description": f"How many percentage points to increase or decrease. Defaults to {config.VOLUME_STEP} if not provided.",
                    },
                },
                "required": ["action"],
            },
        },
    },
]


def _pactl_run(*args) -> str:
    """Runs a pactl command and returns stdout, raising on failure."""
    return run_cli("pactl", *args)


def _get_volume_percent() -> int:
    """Returns the current default sink volume as an integer 0-100."""
    output = _pactl_run("get-sink-volume", "@DEFAULT_SINK@")
    # Output looks like: "Volume: front-left: 65536 / 100% / 0.00 dB, ..."
    match = re.search(r"(\d+)%", output)
    return int(match.group(1)) if match else 0


def _is_muted() -> bool:
    """Returns True if the default sink is currently muted."""
    output = _pactl_run("get-sink-mute", "@DEFAULT_SINK@")
    return "yes" in output.lower()


def control_volume(action: str, value: int = None, step: int = None) -> str:
    """
    Controls system volume via pactl.
    Returns a short spoken-friendly confirmation string.
    """
    step = step if step is not None else config.VOLUME_STEP

    if action == "get":
        vol = _get_volume_percent()
        muted = _is_muted()
        mute_note = ", and it is currently muted" if muted else ""
        return f"The volume is at {vol} percent{mute_note}."

    elif action == "set":
        if value is None:
            return "Please specify a volume level between 0 and 100."
        value = max(0, min(100, int(value)))
        _pactl_run("set-sink-volume", "@DEFAULT_SINK@", f"{value}%")
        # If it was muted, unmute automatically when explicitly setting a level.
        if _is_muted():
            _pactl_run("set-sink-mute", "@DEFAULT_SINK@", "0")
        actual = _get_volume_percent()
        return f"Volume set to {actual} percent."

    elif action == "increase":
        _pactl_run("set-sink-volume", "@DEFAULT_SINK@", f"+{step}%")
        actual = _get_volume_percent()
        return f"Volume increased to {actual} percent."

    elif action == "decrease":
        _pactl_run("set-sink-volume", "@DEFAULT_SINK@", f"-{step}%")
        actual = _get_volume_percent()
        return f"Volume decreased to {actual} percent."

    elif action == "mute":
        _pactl_run("set-sink-mute", "@DEFAULT_SINK@", "1")
        return "Audio muted."

    elif action == "unmute":
        _pactl_run("set-sink-mute", "@DEFAULT_SINK@", "0")
        vol = _get_volume_percent()
        return f"Audio unmuted. Volume is at {vol} percent."

    elif action == "toggle_mute":
        _pactl_run("set-sink-mute", "@DEFAULT_SINK@", "toggle")
        muted = _is_muted()
        return "Audio muted." if muted else f"Audio unmuted. Volume is at {_get_volume_percent()} percent."

    else:
        return f"Unknown volume action: {action}."


DISPATCH = {
    "control_volume": control_volume,
}