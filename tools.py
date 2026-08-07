"""
ARIA - tool calling support.
Defines tools the LLM can invoke and the actual Python functions that
execute them. Ollama's tool-calling support lets the model decide when it
needs current information it doesn't have, rather than hallucinating an answer.
"""
import re
import subprocess
from datetime import datetime

from ddgs import DDGS

import config

# ---- Tool schemas, given to the model so it knows what's available ----
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the web for current information, facts, or anything that "
                "might have changed since your training data, or that you're not "
                "confident about. ONLY use this for genuine factual lookups, such "
                "as specific current events, statistics, prices, or recent "
                "developments you don't already know. Do NOT use this for casual "
                "conversation, greetings, small talk, opinions, jokes, creative "
                "requests, or anything you can already answer naturally without "
                "looking anything up. Do NOT use this for the current date, time, "
                "or news headlines - use get_current_datetime or search_news instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A short, specific search query, like you'd type into a search engine.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_datetime",
            "description": (
                "Gets the current date and time right now. Always use this for any "
                "question about today's date, the current time, or the day of the "
                "week. This is instant and always accurate, unlike web search."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_news",
            "description": (
                "Searches for actual current news headlines and articles on a topic. "
                "Use this instead of search_web whenever the user asks for news, "
                "current events, or 'what's happening' type questions, since it "
                "returns real news articles rather than generic web pages."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The news topic to search for, e.g. 'technology' or a specific subject.",
                    }
                },
                "required": ["topic"],
            },
        },
    },
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

MAX_RESULTS = 4


def _pactl_run(*args) -> str:
    """Runs a pactl command and returns stdout, raising on failure."""
    result = subprocess.run(
        ["pactl"] + list(args),
        capture_output=True, text=True, timeout=5
    )
    return result.stdout.strip()


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


def _brightnessctl_run(*args) -> str:
    """Runs a brightnessctl command, returns stdout. Raises RuntimeError on failure."""
    result = subprocess.run(
        ["brightnessctl"] + list(args),
        capture_output=True, text=True, timeout=5
    )
    if result.returncode != 0:
        # Surface the actual error (e.g. permission denied) so callers can
        # return a clear spoken error instead of silently returning stale data.
        raise RuntimeError(result.stderr.strip() or f"brightnessctl exited with code {result.returncode}")
    return result.stdout.strip()


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
    _PERM_ERROR = (
        "Brightness control failed due to a permission error. "
        "To fix this, add your user to the video group by running: "
        "sudo usermod -aG video followed by your username, then log out and back in."
    )

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


def get_current_datetime(**_) -> str:
    """Returns the real current date/time from the system clock - instant, no search needed."""
    now = datetime.now()
    return f"The current date and time is {now.strftime('%A, %B %d, %Y, %I:%M %p')}."


def search_web(query: str) -> str:
    """
    Runs a DuckDuckGo search and returns a short plain-text summary of the
    top results, formatted for an LLM to read and turn into a spoken answer.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=MAX_RESULTS))
    except Exception as e:
        print(f"[search_web error: {e}]")
        return "Web search failed, no results available."

    if not results:
        print("[search_web: no results returned]")
        return "The search returned no results."

    summary_lines = []
    for r in results:
        title = r.get("title", "")
        body = r.get("body", "")
        summary_lines.append(f"- {title}: {body}")

    result_text = "\n".join(summary_lines)
    print(f"[search_web results for '{query}']:\n{result_text}")

    return (
        f"Current, up to date web search results for '{query}':\n"
        f"{result_text}\n\n"
        f"Use this information directly to answer. This is more current and "
        f"reliable than anything you already know, since your training data "
        f"has a cutoff date and this search just happened right now."
    )


def search_news(topic: str) -> str:
    """
    Runs a DuckDuckGo news search - returns actual current news articles,
    unlike search_web which returns generic web pages.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(topic, max_results=MAX_RESULTS))
    except Exception as e:
        print(f"[search_news error: {e}]")
        return "News search failed, no results available."

    if not results:
        print("[search_news: no results returned]")
        return "The news search returned no results."

    summary_lines = []
    for r in results:
        title = r.get("title", "")
        body = r.get("body", "")
        date = r.get("date", "")
        summary_lines.append(f"- [{date}] {title}: {body}")

    result_text = "\n".join(summary_lines)
    print(f"[search_news results for '{topic}']:\n{result_text}")

    return (
        f"Current news results for '{topic}':\n"
        f"{result_text}\n\n"
        f"Use this information directly to answer, including the dates so the "
        f"user knows how recent each item is."
    )


# Maps tool name (as the model will call it) to the actual Python function.
TOOL_DISPATCH = {
    "search_web": search_web,
    "get_current_datetime": get_current_datetime,
    "search_news": search_news,
    "control_volume": control_volume,
    "control_brightness": control_brightness,
}