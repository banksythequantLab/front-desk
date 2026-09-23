#!/usr/bin/env python3
"""Lobby receptionist avatar — prototype.

DESIGN NOTE — why a stylised avatar and not a photoreal one:
A convincing video likeness of the attorney, speaking in his cloned voice,
could lead a visitor to believe they are speaking with the attorney. That is
misleading-communication territory under NY Rule 7.1, quite apart from being
uncanny. This avatar is deliberately, obviously synthetic.

It is also cheap: mouth shapes are driven from the audio envelope in the
browser via Web Audio, so the GPU stays free for the language model. No
diffusion video, no ROCm, no PyTorch.

Speech comes from whichever backend is configured:
  FD_TTS_URL   e.g. http://johnson:8300/api/clone  (FreeClone/VoxCPM)
  FD_TTS_REF   reference wav for cloning
If neither is set the page falls back to the browser's own speech synthesis,
so the prototype runs standalone.

Env:
  FD_AVATAR_PORT  default 8314
  FD_AVATAR_BIND  default 0.0.0.0 (LAN only - never tunnelled)
"""

import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("FD_AVATAR_PORT", "8314"))
BIND = os.environ.get("FD_AVATAR_BIND", "0.0.0.0")
TTS_URL = os.environ.get("FD_TTS_URL", "")
TTS_REF = os.environ.get("FD_TTS_REF", "")
HERE = os.path.dirname(os.path.abspath(__file__))


class Handler(BaseHTTPRequestHandler):
    server_version = "FrontDeskAvatar/0.1"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            with open(os.path.join(HERE, "avatar.html"), encoding="utf-8") as fh:
                return self._send(200, fh.read(), "text/html; charset=utf-8")
        if path == "/api/config":
            return self._send(200, json.dumps({"tts": bool(TTS_URL)}),
                              "application/json")
        return self._send(404, '{"error":"not found"}', "application/json")

    def do_POST(self):
        if self.path.split("?")[0] != "/api/say":
            return self._send(404, '{"error":"not found"}', "application/json")
        n = int(self.headers.get("Content-Length") or 0)
        try:
            text = json.loads(self.rfile.read(n) or b"{}").get("text", "")
        except json.JSONDecodeError:
            return self._send(400, '{"error":"bad json"}', "application/json")
        if not text or not TTS_URL:
            return self._send(503, '{"error":"no tts backend"}', "application/json")
        try:
            import mimetypes  # noqa: F401  (kept for future multipart use)
            boundary = "----frontdesk"
            parts = []
            if TTS_REF and os.path.exists(TTS_REF):
                with open(TTS_REF, "rb") as fh:
                    ref = fh.read()
                parts.append(
                    f'--{boundary}\r\nContent-Disposition: form-data; '
                    f'name="prompt_audio"; filename="ref.wav"\r\n'
                    f'Content-Type: audio/wav\r\n\r\n'.encode() + ref + b"\r\n")
            for k, v in (("text", text), ("lang", "en")):
                parts.append(
                    f'--{boundary}\r\nContent-Disposition: form-data; '
                    f'name="{k}"\r\n\r\n{v}\r\n'.encode())
            parts.append(f"--{boundary}--\r\n".encode())
            body = b"".join(parts)
            req = urllib.request.Request(
                TTS_URL, data=body, method="POST",
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
            with urllib.request.urlopen(req, timeout=300) as r:
                audio = r.read()
            return self._send(200, audio, "audio/wav")
        except Exception as e:                                # noqa: BLE001
            return self._send(502, json.dumps({"error": str(e)[:200]}),
                              "application/json")


if __name__ == "__main__":
    print(f"avatar on http://{BIND}:{PORT}  tts={'yes' if TTS_URL else 'browser fallback'}")
    ThreadingHTTPServer((BIND, PORT), Handler).serve_forever()
