"""
ARIA Device Switcher - a system tray icon for quickly switching audio
input/output devices, instead of relying on PulseAudio/PipeWire's
auto-switch-on-connect behavior (which is inconsistent across setups).
Also exposes quick toggles for muting ARIA and enabling free listening
(no wake word required), both controlled via ARIA's shared prefs server.

Uses PyQt5's native QSystemTrayIcon instead of pystray, since pystray's
default backend requires GTK, which isn't available in this environment
(same reason the HUD uses pywebview's Qt backend instead of GTK).
"""
import json
import subprocess
import sys
import urllib.request

HUD_PREFS_URL = "http://127.0.0.1:8765/prefs"

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QActionGroup
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QCursor


def run_pactl_json(args):
    try:
        output = subprocess.check_output(["pactl", "-f", "json"] + args, text=True, timeout=3)
        return json.loads(output)
    except Exception:
        return None


def get_sinks():
    data = run_pactl_json(["list", "sinks"])
    if data is None:
        return []
    return [(s["name"], s.get("description", s["name"])) for s in data]


def get_sources():
    data = run_pactl_json(["list", "sources"])
    if data is None:
        return []
    return [
        (s["name"], s.get("description", s["name"]))
        for s in data
        if ".monitor" not in s["name"]
    ]


def get_default_sink_name():
    try:
        return subprocess.check_output(["pactl", "get-default-sink"], text=True, timeout=3).strip()
    except Exception:
        return None


def get_default_source_name():
    try:
        return subprocess.check_output(["pactl", "get-default-source"], text=True, timeout=3).strip()
    except Exception:
        return None


def set_default_sink(name):
    subprocess.run(["pactl", "set-default-sink", name], check=False)


def set_default_source(name):
    subprocess.run(["pactl", "set-default-source", name], check=False)


def get_prefs() -> dict:
    """Fetches all ARIA prefs at once (mute, free_listening, show_transcript)."""
    try:
        with urllib.request.urlopen(HUD_PREFS_URL, timeout=2) as response:
            return json.loads(response.read())
    except Exception:
        # ARIA not reachable yet - safe defaults (nothing muted/forced on).
        return {"mute": False, "free_listening": False, "show_transcript": True}


def set_pref(key: str, value: bool):
    try:
        payload = json.dumps({key: value}).encode("utf-8")
        req = urllib.request.Request(
            HUD_PREFS_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass  # ARIA not running yet, or server not up - fail silently


def make_tray_icon():
    """Simple glowing blue dot, matching the ARIA HUD's theme."""
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(10, 132, 255, 255))
    painter.setPen(QColor(10, 132, 255, 255))
    painter.drawEllipse(8, 8, size - 16, size - 16)
    painter.end()
    return QIcon(pixmap)


class DeviceSwitcherTray:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.tray = QSystemTrayIcon(make_tray_icon())
        self.tray.setToolTip("ARIA Devices")

        self.menu = QMenu()
        self.tray.setContextMenu(self.menu)
        self.rebuild_menu()
        self.tray.show()

        # Right-click shows the context menu automatically, but left-click
        # normally does nothing unless we wire it up - this makes left-click
        # also open the same menu, which is more intuitive for most people.
        self.tray.activated.connect(self.on_tray_activated)

        # Rebuild right before the menu is actually shown, not on a periodic
        # timer - rebuilding while the menu is open was closing it out from
        # under you mid-click. This still keeps the device list fresh, since
        # it rebuilds fresh every single time you open it.
        self.menu.aboutToShow.connect(self.rebuild_menu)

    def on_tray_activated(self, reason):
        # Trigger = left-click (on most platforms/desktop environments).
        # Context menu (right-click) already shows automatically via setContextMenu.
        if reason == QSystemTrayIcon.Trigger:
            self.menu.popup(QCursor.pos())

    def rebuild_menu(self):
        self.menu.clear()

        current_sink = get_default_sink_name()
        current_source = get_default_source_name()
        prefs = get_prefs()

        output_menu = self.menu.addMenu("Output Device")
        output_group = QActionGroup(output_menu)
        output_group.setExclusive(True)
        for name, description in get_sinks():
            action = QAction(description, output_menu, checkable=True)
            action.setChecked(name == current_sink)
            action.triggered.connect(lambda checked, n=name: set_default_sink(n))
            output_group.addAction(action)
            output_menu.addAction(action)

        input_menu = self.menu.addMenu("Input Device")
        input_group = QActionGroup(input_menu)
        input_group.setExclusive(True)
        for name, description in get_sources():
            action = QAction(description, input_menu, checkable=True)
            action.setChecked(name == current_source)
            action.triggered.connect(lambda checked, n=name: set_default_source(n))
            input_group.addAction(action)
            input_menu.addAction(action)

        self.menu.addSeparator()

        # Mute: stops ARIA capturing audio entirely, so you can talk freely
        # nearby without accidentally triggering it.
        mute_action = QAction("Mute ARIA", self.menu, checkable=True)
        mute_action.setChecked(prefs.get("mute", False))
        mute_action.triggered.connect(lambda checked: set_pref("mute", checked))
        self.menu.addAction(mute_action)

        # Free listening: skips the wake-word requirement, every utterance
        # heard is treated as a direct command.
        free_listening_action = QAction("Free Listening", self.menu, checkable=True)
        free_listening_action.setChecked(prefs.get("free_listening", False))
        free_listening_action.triggered.connect(lambda checked: set_pref("free_listening", checked))
        self.menu.addAction(free_listening_action)

        self.menu.addSeparator()

        transcript_action = QAction("Show Transcript Text", self.menu, checkable=True)
        transcript_action.setChecked(prefs.get("show_transcript", True))
        transcript_action.triggered.connect(lambda checked: set_pref("show_transcript", checked))
        self.menu.addAction(transcript_action)

        self.menu.addSeparator()
        quit_action = QAction("Quit", self.menu)
        quit_action.triggered.connect(self.app.quit)
        self.menu.addAction(quit_action)

    def run(self):
        sys.exit(self.app.exec_())


if __name__ == "__main__":
    tray = DeviceSwitcherTray()
    tray.run()