#!/usr/bin/env python3
"""
Front Desk - Ring Partner API webhook receiver.

Stdlib only (no pip installs) so it drops onto johnson or the N5 Max without
touching the venv that banksy_ears / banksy_mouth depend on.

Responsibilities, in order:
  1. Verify the Ring HMAC-SHA256 signature (hex) over the RAW request body.
  2. Reject replays via meta.request_id.
  3. Validate + normalize the JSON:API-shaped payload.
  4. Append to an append-only JSONL event store.
  5. Hand the event to classify() -> route(). Both are stubs right now;
     neither invents a result.

ACK FAST: Ring retries on non-2xx, so we persist and return 200 immediately.
Slow work (VLM, calls) belongs in a worker off the JSONL tail, not here.

Env:
  FRONTDESK_HMAC_KEY   HMAC Signature Key from the Ring Developer Console (required)
  FRONTDESK_BEARER     optional extra shared-secret check (the AmazonAppDev sample's scheme)
  FRONTDESK_SIG_HEADER override the signature header name (see SIG_HEADER_CANDIDATES)
  FRONTDESK_STORE      path to the JSONL event store
  FRONTDESK_PORT       default 8310 (8300/8302/8303 are taken by the voice stack)
"""

import base64
import binascii
import hashlib
import hmac
import json
import logging
import os
import queue
import sys
import tempfile
import threading
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------- config

HMAC_KEY = os.environ.get("FRONTDESK_HMAC_KEY", "")
BEARER = os.environ.get("FRONTDESK_BEARER", "")
STORE = os.environ.get("FRONTDESK_STORE", "front_desk_events.jsonl")
PORT = int(os.environ.get("FRONTDESK_PORT", "8310"))

# UNVERIFIED: the exact header Ring signs with is not stated in the public
# docs we could reach. We accept any of these and record which one matched,
# so the first real delivery tells us the answer. Override via env once known.
SIG_HEADER_CANDIDATES = [
    "X-Ring-Signature",
    "X-Amz-Vision-Signature",
    "X-Signature",
    "X-Hub-Signature-256",
]
if os.environ.get("FRONTDESK_SIG_HEADER"):
    SIG_HEADER_CANDIDATES.insert(0, os.environ["FRONTDESK_SIG_HEADER"])

MAX_BODY = 1_048_576  # 1 MiB
SEEN_MAX = 2000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("frontdesk")

_seen = set()
_seen_order = []
_lock = threading.Lock()


# ---------------------------------------------------------------- security

def _key_variants():
    """Ring issues the signing key base64-encoded.

    Whether the HMAC is computed over the decoded bytes or over the base64
    string itself is not documented, so we try both and record which one
    verified. Once a real delivery tells us, pin it and delete the other.
    """
    variants = [("utf8", HMAC_KEY.encode())]
    try:
        decoded = base64.b64decode(HMAC_KEY, validate=True)
        if decoded:
            variants.append(("base64", decoded))
    except (binascii.Error, ValueError):
        pass
    return variants


def verify_signature(raw: bytes, headers) -> tuple[bool, str]:
    """Constant-time HMAC-SHA256 (hex) check over the raw body.

    Returns (ok, detail). Fails closed when no key is configured.
    """
    if not HMAC_KEY:
        return False, "no HMAC key configured"

    for name in SIG_HEADER_CANDIDATES:
        got = headers.get(name)
        if not got:
            continue
        candidate = got.split("=", 1)[1] if got.lower().startswith("sha256=") else got
        candidate = candidate.strip().lower()
        for enc, key in _key_variants():
            expected = hmac.new(key, raw, hashlib.sha256).hexdigest()
            if hmac.compare_digest(candidate, expected):
                return True, f"{name} ({enc} key)"
        return False, f"bad signature on {name}"

    return False, "no signature header present"


def check_bearer(headers) -> bool:
    if not BEARER:
        return True
    return headers.get("Authorization") == f"Bearer {BEARER}"


# ---------------------------------------------------------------- normalize

def normalize(body: dict) -> dict:
    """Flatten Ring's JSON:API envelope. Mirrors the AmazonAppDev sample's
    field mapping so payload fixtures stay interchangeable."""
    meta = body.get("meta") or {}
    data = body.get("data") or {}
    attrs = data.get("attributes") or {}

    ts = attrs.get("timestamp")
    if isinstance(ts, (int, float)):
        # Ring sends epoch ms
        ts = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()
    elif not ts:
        ts = meta.get("time") or datetime.now(timezone.utc).isoformat()

    return {
        "event_id": data.get("id"),
        "event_type": data.get("type", "unknown"),
        "timestamp": ts,
        "device_id": attrs.get("source"),
        "source_type": attrs.get("source_type"),
        "confidence": attrs.get("confidence"),
        "bounding_box": attrs.get("bounding_box"),
        "thumbnail_url": attrs.get("thumbnail_url"),
        "request_id": meta.get("request_id"),
        "ring_version": meta.get("version"),
        "received_at": datetime.now(timezone.utc).isoformat(),
        "raw": body,
    }


def is_ring_shaped(body: dict) -> bool:
    return (
        isinstance(body.get("meta"), dict)
        and isinstance(body.get("data"), dict)
        and isinstance(body["data"].get("attributes"), dict)
        and "source" in body["data"]["attributes"]
    )


# ---------------------------------------------------------------- pipeline

# Classification takes seconds; Ring retries on non-2xx. So the webhook ACKS
# FIRST and a worker thread classifies afterwards, appending a second record
# keyed by event_id. Readers merge the two. The store stays append-only.

CLASSIFY_ON = os.environ.get("FD_CLASSIFY", "1") != "0"
RING_TOKEN = os.environ.get("FD_RING_TOKEN", "")
_queue = queue.Queue(maxsize=500)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "classifier"))


def fetch_snapshot(url):
    """Download an event snapshot to a temp file. Returns (path, error)."""
    if not url:
        return None, "event carried no snapshot URL"
    req = urllib.request.Request(url)
    if RING_TOKEN:
        req.add_header("Authorization", f"Bearer {RING_TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
    except Exception as e:                      # noqa: BLE001 - report any failure
        return None, f"snapshot fetch failed: {e}"
    if len(data) < 1024:
        return None, f"snapshot too small ({len(data)} bytes)"
    fd, path = tempfile.mkstemp(suffix=".jpg", prefix="fd_snap_")
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    return path, None


def classify_event(event):
    """Snapshot -> VLM -> rules. Returns a verdict dict, never raises."""
    path, err = fetch_snapshot(event.get("thumbnail_url"))
    if err:
        # No image is not an escalation — it is a gap. Escalating here would
        # flood the review queue every time a snapshot is unavailable.
        return {"disposition": "no_snapshot", "escalate": False, "why": err}
    try:
        from classify import classify as run_classify
        out = run_classify(path)
    except Exception as e:                      # noqa: BLE001
        return {"disposition": "error", "escalate": True,
                "why": f"classifier raised: {e}"}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    return out


def _worker():
    while True:
        event = _queue.get()
        if event is None:
            return
        try:
            verdict = classify_event(event)
            persist({"record_type": "classification",
                     "event_id": event.get("event_id"),
                     "device_id": event.get("device_id"),
                     "classified_at": datetime.now(timezone.utc).isoformat(),
                     "verdict": verdict})
            log.info("classified %s -> %s (escalate=%s)", event.get("event_id"),
                     verdict.get("disposition"), verdict.get("escalate"))
        except Exception as e:                  # noqa: BLE001
            log.exception("worker failed on %s: %s", event.get("event_id"), e)
        finally:
            _queue.task_done()


def enqueue(event):
    if not CLASSIFY_ON:
        return "classification_disabled"
    try:
        _queue.put_nowait(event)
        return "queued"
    except queue.Full:
        log.warning("classification queue full, dropping %s", event.get("event_id"))
        return "queue_full"


def persist(record: dict) -> None:
    with _lock:
        with open(STORE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def seen_before(request_id: str) -> bool:
    if not request_id:
        return False
    with _lock:
        if request_id in _seen:
            return True
        _seen.add(request_id)
        _seen_order.append(request_id)
        while len(_seen_order) > SEEN_MAX:
            _seen.discard(_seen_order.pop(0))
    return False


# ---------------------------------------------------------------- http

class Handler(BaseHTTPRequestHandler):
    server_version = "FrontDesk/0.1"

    def log_message(self, fmt, *args):  # route access logs through logging
        log.info("%s %s", self.address_string(), fmt % args)

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            count = 0
            if os.path.exists(STORE):
                with open(STORE, encoding="utf-8") as fh:
                    count = sum(1 for _ in fh)
            # No filesystem paths here: this endpoint is public.
            return self._json(200, {
                "ok": True,
                "hmac_configured": bool(HMAC_KEY),
                "classifier": "on" if CLASSIFY_ON else "off",
                "records_stored": count,
            })
        if path == "/ring/webhook":
            # Registration flows often probe the URL with a GET before they
            # will accept it. Answer the probe; POST still requires a valid
            # HMAC signature and is unaffected by this.
            return self._json(200, {"ok": True, "endpoint": "ring-webhook",
                                    "accepts": ["POST"]})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path.split("?")[0] != "/ring/webhook":
            return self._json(404, {"error": "not found"})

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            return self._json(400, {"error": "bad content-length"})
        raw = self.rfile.read(length)

        if not check_bearer(self.headers):
            log.warning("rejected: bearer mismatch")
            return self._json(401, {"error": "unauthorized"})

        ok, detail = verify_signature(raw, self.headers)
        if not ok:
            log.warning("rejected: %s", detail)
            return self._json(401, {"error": "signature verification failed"})

        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            return self._json(400, {"error": "invalid json"})
        if not isinstance(body, dict):
            return self._json(400, {"error": "expected object"})

        request_id = (body.get("meta") or {}).get("request_id", "")
        if seen_before(request_id):
            log.info("duplicate request_id=%s ignored", request_id)
            return self._json(200, {"status": "already_processed", "request_id": request_id})

        if not is_ring_shaped(body):
            log.warning("payload not Ring-shaped, storing raw request_id=%s", request_id)
            persist({"event_type": "unrecognized", "sig_header": detail,
                     "received_at": datetime.now(timezone.utc).isoformat(), "raw": body})
            return self._json(200, {"status": "stored_unrecognized"})

        event = normalize(body)
        event["sig_header"] = detail
        event["record_type"] = "event"
        queued = enqueue(event)
        event["classification"] = queued
        persist(event)

        log.info("event %s type=%s device=%s -> %s",
                 event["event_id"], event["event_type"],
                 event["device_id"], queued)
        return self._json(200, {"status": "processed", "event_id": event["event_id"]})


def main():
    if not HMAC_KEY:
        log.warning("FRONTDESK_HMAC_KEY is unset - every webhook will be rejected (fail closed)")
    if CLASSIFY_ON:
        threading.Thread(target=_worker, daemon=True, name="classifier").start()
        log.info("classifier worker started (vlm backend enabled)")
    else:
        log.info("FD_CLASSIFY=0 - events will be stored but not classified")
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    log.info("Front Desk listening on :%d  store=%s", PORT, os.path.abspath(STORE))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log.info("shutting down")
        srv.shutdown()


if __name__ == "__main__":
    main()
