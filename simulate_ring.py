#!/usr/bin/env python3
"""Fire synthetic Ring webhooks at the Front Desk receiver.

Payload shape copied from the AmazonAppDev/ring-api-helloworld Zod schema
(lib/schemas/webhook.ts), so fixtures match what the official sample expects.

Usage: python simulate_ring.py [base_url]
"""

import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8310"
KEY = os.environ.get("FRONTDESK_HMAC_KEY", "")

PASS = "PASS"
FAIL = "FAIL"
results = []


def payload(event_type="motion_detected", request_id=None, confidence=0.94):
    now_ms = int(time.time() * 1000)
    rid = request_id or f"req_{now_ms}"
    return {
        "meta": {
            "version": "1.1",
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "request_id": rid,
        },
        "data": {
            "id": f"evt_{now_ms}",
            "type": event_type,
            "attributes": {
                "source": "dev_frontdoor_001",
                "source_type": "doorbell",
                "timestamp": now_ms,
                "confidence": confidence,
                "bounding_box": {"x": 0.31, "y": 0.12, "width": 0.22, "height": 0.55},
                "thumbnail_url": "https://example.invalid/snap.jpg",
            },
            "relationships": {"devices": {"links": {"self": "/v1/devices/dev_frontdoor_001"}}},
        },
    }


def post(body_obj, sign_with=None, header="X-Ring-Signature", raw_override=None):
    raw = raw_override if raw_override is not None else json.dumps(body_obj).encode()
    headers = {"Content-Type": "application/json"}
    if sign_with is not None:
        headers[header] = hmac.new(sign_with.encode(), raw, hashlib.sha256).hexdigest()
    req = urllib.request.Request(f"{BASE}/ring/webhook", data=raw, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def check(name, got_code, want_code, got_body=None):
    ok = got_code == want_code
    results.append(ok)
    print(f"  [{PASS if ok else FAIL}] {name:<42} -> {got_code} {got_body or ''}")


print(f"Front Desk test run against {BASE}\n")

try:
    with urllib.request.urlopen(f"{BASE}/health", timeout=5) as r:
        hc, hb = r.status, json.loads(r.read())
    check("health endpoint", hc, 200, hb)
except Exception as e:
    print(f"  [{FAIL}] health endpoint unreachable: {e}")
    sys.exit(1)

# 1. happy path
c, b = post(payload(), sign_with=KEY)
check("valid signed motion_detected", c, 200, b)

# 2. person_detected
c, b = post(payload("person_detected"), sign_with=KEY)
check("valid signed person_detected", c, 200, b)

# 3. replay of the same request_id
dup = payload(request_id="req_replay_me")
c, b = post(dup, sign_with=KEY)
check("first delivery of replay fixture", c, 200, b)
c, b = post(dup, sign_with=KEY)
check("replay rejected as duplicate", c, 200, b)
results[-1] = b.get("status") == "already_processed"
print(f"       (idempotency status={b.get('status')})")

# 4. wrong key
c, b = post(payload(), sign_with="wrong-key-entirely")
check("bad signature rejected", c, 401, b)

# 5. unsigned
c, b = post(payload())
check("unsigned request rejected", c, 401, b)

# 6. tampered body, valid sig over the ORIGINAL bytes
orig = payload()
raw = json.dumps(orig).encode()
sig = hmac.new(KEY.encode(), raw, hashlib.sha256).hexdigest()
tampered = raw.replace(b"dev_frontdoor_001", b"dev_attacker_999")
req = urllib.request.Request(
    f"{BASE}/ring/webhook", data=tampered,
    headers={"Content-Type": "application/json", "X-Ring-Signature": sig}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=5) as r:
        c, b = r.status, json.loads(r.read())
except urllib.error.HTTPError as e:
    c, b = e.code, json.loads(e.read() or b"{}")
check("tampered body rejected", c, 401, b)

# 7. malformed JSON, correctly signed
bad = b"{not json at all"
sig = hmac.new(KEY.encode(), bad, hashlib.sha256).hexdigest()
req = urllib.request.Request(
    f"{BASE}/ring/webhook", data=bad,
    headers={"Content-Type": "application/json", "X-Ring-Signature": sig}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=5) as r:
        c, b = r.status, json.loads(r.read())
except urllib.error.HTTPError as e:
    c, b = e.code, json.loads(e.read() or b"{}")
check("malformed JSON rejected", c, 400, b)

# 8. signed but non-Ring shape
c, b = post({"hello": "world"}, sign_with=KEY)
check("non-Ring payload stored separately", c, 200, b)

# 9. alternate signature header name
c, b = post(payload(), sign_with=KEY, header="X-Hub-Signature-256")
check("alternate header accepted", c, 200, b)

# 10. base64-decoded key path — Ring issues the key base64-encoded and does not
# document whether the HMAC is over the decoded bytes or the string. The
# receiver accepts either; this proves the decoded path works.
import base64 as _b64
try:
    _decoded = _b64.b64decode(KEY, validate=True)
except Exception:
    _decoded = b""
if _decoded:
    orig = payload()
    raw = json.dumps(orig).encode()
    sig = hmac.new(_decoded, raw, hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        f"{BASE}/ring/webhook", data=raw,
        headers={"Content-Type": "application/json", "X-Ring-Signature": sig},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            c, b = r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        c, b = e.code, json.loads(e.read() or b"{}")
    check("base64-decoded key accepted", c, 200, b)
else:
    print("  [SKIP] base64-decoded key (test key is not valid base64)")

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
