"""
ARIA - HUD state broadcasting.
A tiny local HTTP server that serves ARIA's current state as JSON, so a
separate HUD window (hud.py) can poll it and show live status/transcript
without being coupled to the voice pipeline itself.
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


def set_hud_state(**kwargs):
    with _hud_state_lock:
        _hud_state.update(kwargs)
        _hud_state["timestamp"] = time.time()


def reset_hud_idle():
    """Goes back to idle and clears any leftover transcript/reply text."""
    set_hud_state(state="idle", heard="", reply="")


class _HudStateHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/state":
            self.send_response(404)
            self.end_headers()
            return
        with _hud_state_lock:
            body = json.dumps(_hud_state).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")  # HUD window fetches cross-origin
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # silence default request logging, it's noisy


def start_hud_server():
    server = HTTPServer(("127.0.0.1", config.HUD_SERVER_PORT), _HudStateHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[HUD state server running on http://127.0.0.1:{config.HUD_SERVER_PORT}/state]")
