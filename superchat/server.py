"""Tiny standard-library web server: GET / serves the chat page, POST /api/chat answers."""
from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .app import SuperChat

STATIC = Path(__file__).resolve().parent.parent / "static"


def make_handler(bot: SuperChat):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/health":
                self._send(200, b'{"ok": true}')
            else:
                self._send(404, b'{"error": "not found"}')

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(length) or b"{}")
                if self.path == "/api/reset":
                    bot.sessions.reset(data.get("session_id", ""))
                    return self._send(200, b'{"ok": true}')
                if self.path != "/api/chat":
                    return self._send(404, b'{"error": "not found"}')
                out = bot.handle(data.get("session_id"), str(data.get("message", "")))
                self._send(200, json.dumps(out, ensure_ascii=False).encode())
            except Exception:
                logging.exception("request failed")
                self._send(500, json.dumps({"reply": "Something went wrong, please try again."}).encode())

        def log_message(self, *args):
            pass

    return Handler


def serve(host="127.0.0.1", port=8000):
    bot = SuperChat()
    from .api_repositories import describe
    print("Data sources →", describe(bot.repos))
    httpd = ThreadingHTTPServer((host, port), make_handler(bot))
    print(f"SuperChat is running → http://{host}:{port}  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
