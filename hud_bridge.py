"""
ARIA - HUD state broadcasting and shared preferences.
A tiny local HTTP server that serves ARIA's current state as JSON, so a
separate HUD window (hud.py) can poll it and show live status/transcript
without being coupled to the voice pipeline itself. Also serves/accepts
toggleable preferences (mute, free listening, show transcript) so the
device switcher tray icon can control ARIA's behavior live.
"""
import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

import config

_hud_state = {
    "state": "idle",        # idle | listening | thinking | speaking
    "heard": "",
    "reply": "",
    "timestamp": time.time(),
}
_hud_state_lock = threading.Lock()

# Toggleable preferences, controlled via the device switcher tray icon.
# mute: when True, ARIA stops capturing audio entirely (no VAD, nothing).
# free_listening: when True, skips the wake-word check - every utterance
#   heard is treated as a direct command, no "ARIA" needed first.
# show_transcript: whether the HUD window displays heard/reply text.
_hud_prefs = {
    "mute": False,
    "free_listening": False,
    "show_transcript": True,
}
_hud_prefs_lock = threading.Lock()


def set_hud_state(**kwargs):
    with _hud_state_lock:
        _hud_state.update(kwargs)
        _hud_state["timestamp"] = time.time()


def reset_hud_idle():
    """Goes back to idle and clears any leftover transcript/reply text."""
    set_hud_state(state="idle", heard="", reply="")


def get_prefs() -> dict:
    with _hud_prefs_lock:
        return dict(_hud_prefs)


def set_prefs(**kwargs):
    with _hud_prefs_lock:
        _hud_prefs.update(kwargs)


def is_muted() -> bool:
    with _hud_prefs_lock:
        return _hud_prefs["mute"]


def is_free_listening() -> bool:
    with _hud_prefs_lock:
        return _hud_prefs["free_listening"]


class _HudStateHandler(BaseHTTPRequestHandler):
    def _send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")  # cross-origin fetch from HUD/tray
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/state":
            with _hud_state_lock:
                self._send_json(dict(_hud_state))
        elif self.path == "/prefs":
            self._send_json(get_prefs())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/prefs":
            self.send_response(404)
            self.end_headers()
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            updates = json.loads(body) if body else {}
            # Only accept known preference keys, ignore anything unexpected.
            valid_updates = {k: v for k, v in updates.items() if k in _hud_prefs}
            set_prefs(**valid_updates)
            self._send_json(get_prefs())
        except Exception as e:
            self._send_json({"error": str(e)}, status=400)

    def log_message(self, format, *args):
        pass  # silence default request logging, it's noisy


def start_hud_server():
    server = HTTPServer(("127.0.0.1", config.HUD_SERVER_PORT), _HudStateHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[HUD state server running on http://127.0.0.1:{config.HUD_SERVER_PORT}/state]")