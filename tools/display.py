"""
ARIA - screen brightness control via brightnessctl.
"""
import config
from ._shell import run_cli

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "control_brightness",
            "description": (
                "Controls the screen or display brightness. Use this when the user "
                "asks to change, set, increase, decrease, raise, lower, dim, or "
                "brighten the screen, display, or backlight. Also use it if they "
                "ask what the current brightness is."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["get", "set", "increase", "decrease"],
                        "description": (
                            "The action to perform. "
                            "'get' returns the current brightness. "
                            "'set' sets it to an exact percentage (requires 'value'). "
                            "'increase' raises it by a step (optionally provide 'step'). "
                            "'decrease' lowers it by a step (optionally provide 'step')."
                        ),
                    },
                    "value": {
                        "type": "integer",
                        "description": "Target brightness percentage (0-100). Only used when action is 'set'.",
                    },
                    "step": {
                        "type": "integer",
                        "description": f"How many percentage points to increase or decrease. Defaults to {config.BRIGHTNESS_STEP} if not provided.",
                    },
                },
                "required": ["action"],
            },
        },
    },
]

_PERM_ERROR = (
    "Brightness control failed due to a permission error. "
    "To fix this, add your user to the video group by running: "
    "sudo usermod -aG video followed by your username, then log out and back in."
)


def _brightnessctl_run(*args) -> str:
    """Runs a brightnessctl command, returns stdout. Raises RuntimeError on failure."""
    return run_cli("brightnessctl", *args)


def _get_brightness_percent() -> int:
    """Returns the current brightness as an integer 0-100."""
    try:
        current = int(_brightnessctl_run("get"))
        maximum = int(_brightnessctl_run("max"))
        if maximum == 0:
            return 0
        return round((current / maximum) * 100)
    except (ValueError, ZeroDivisionError):
        return 0


def control_brightness(action: str, value: int = None, step: int = None) -> str:
    """
    Controls screen brightness via brightnessctl.
    Returns a short spoken-friendly confirmation string.
    """
    step = step if step is not None else config.BRIGHTNESS_STEP

    if action == "get":
        pct = _get_brightness_percent()
        return f"The screen brightness is at {pct} percent."

    elif action == "set":
        if value is None:
            return "Please specify a brightness level between 0 and 100."
        value = max(1, min(100, int(value)))  # floor at 1% so screen doesn't go completely black
        try:
            _brightnessctl_run("set", f"{value}%")
        except RuntimeError as e:
            print(f"[control_brightness set error: {e}]")
            return _PERM_ERROR
        actual = _get_brightness_percent()
        return f"Brightness set to {actual} percent."

    elif action == "increase":
        try:
            _brightnessctl_run("set", f"+{step}%")
        except RuntimeError as e:
            print(f"[control_brightness increase error: {e}]")
            return _PERM_ERROR
        actual = _get_brightness_percent()
        return f"Brightness increased to {actual} percent."

    elif action == "decrease":
        try:
            _brightnessctl_run("set", f"{step}%-")  # brightnessctl syntax for decrease
        except RuntimeError as e:
            print(f"[control_brightness decrease error: {e}]")
            return _PERM_ERROR
        actual = _get_brightness_percent()
        return f"Brightness decreased to {actual} percent."

    else:
        return f"Unknown brightness action: {action}."


DISPATCH = {
    "control_brightness": control_brightness,
}