"""
ARIA HUD - a small always-on-top window showing a Jarvis-style status orb.
Run this separately from aria_main.py - it polls ARIA's local state server
and updates purely visually. If ARIA isn't running, it just sits idle.

Run with:  python hud.py
"""
import os
import re
import subprocess
import webview

HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hud.html")

WINDOW_WIDTH = 300
WINDOW_HEIGHT = 320


def get_primary_monitor_geometry():
    """
    Uses xrandr to find the primary monitor's actual geometry (width, height,
    x offset, y offset). This is important on multi-monitor setups, since
    tkinter's winfo_screenwidth/height returns the combined virtual screen
    across ALL monitors, not just the primary one - which centers the window
    in the wrong place.
    Returns (width, height, x_offset, y_offset), or None if it can't be determined.
    """
    try:
        output = subprocess.check_output(["xrandr", "--query"], text=True, timeout=3)
    except Exception:
        return None

    # Look for the line marked "primary", e.g.:
    # eDP-1 connected primary 1920x1080+0+0 (normal left inverted...) 344mm x 193mm
    for line in output.splitlines():
        if " primary " in line:
            match = re.search(r"(\d+)x(\d+)\+(\d+)\+(\d+)", line)
            if match:
                width, height, x_off, y_off = map(int, match.groups())
                return width, height, x_off, y_off
    return None


def get_centered_position():
    """Returns (x, y) to center the HUD window on the primary monitor."""
    geometry = get_primary_monitor_geometry()

    if geometry:
        mon_width, mon_height, x_off, y_off = geometry
        x = x_off + (mon_width - WINDOW_WIDTH) // 2
        y = y_off + (mon_height - WINDOW_HEIGHT) // 2
        return x, y

    # Fallback: if xrandr parsing fails for any reason, fall back to tkinter's
    # combined virtual screen (not perfect on multi-monitor, but better than nothing).
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.destroy()
    return (screen_width - WINDOW_WIDTH) // 2, (screen_height - WINDOW_HEIGHT) // 2


if __name__ == "__main__":
    x, y = get_centered_position()

    window = webview.create_window(
        "ARIA",
        HTML_PATH,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        x=x,
        y=y,
        frameless=True,
        easy_drag=True,       # lets you drag the borderless window by clicking anywhere
        on_top=True,
        transparent=True,
        background_color="#000000",
    )
    webview.start(gui="qt")