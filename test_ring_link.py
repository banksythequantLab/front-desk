#!/usr/bin/env python3
"""Ring one-way account linking — nonce, sign-in, and claim flow.

Covers everything testable without Ring's live API: nonce computation against
the documented spec, the freshness window, constant-time matching, operator
sign-in, and the HTTP surface Ring drives.
"""
import base64
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = "8413"
BASE = f"http://127.0.0.1:{PORT}"
KEY = "test-signing-key"
USER = "derek"
PW = "correct-horse-battery"
TOKENS = os.path.join(ROOT, "_test_tokens.json")

sys.path.insert(0, ROOT)
os.environ["FRONTDESK_HMAC_KEY"] = KEY
os.environ["FD_TOKENS_FILE"] = TOKENS
import ring_link  # noqa: E402

results = []
def check(name, ok, detail=""):
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:<44} {detail}")


# ---------------------------------------------------------------- unit

print("nonce and sign-in\n")

# Ring's documented example shape: HMAC-SHA256 over "<ms>:<account_id>",
# URL-safe base64, no padding.
ts, acct = 1771130906289, "acct_test_123"
n = ring_link.compute_nonce(ts, acct)
expected = base64.urlsafe_b64encode(
    hmac.new(KEY.encode(), f"{ts}:{acct}".encode(), hashlib.sha256).digest()
).rstrip(b"=").decode()
check("nonce matches documented construction", n == expected)
check("nonce is url-safe with no padding",
      "=" not in n and all(c.isalnum() or c in "-_" for c in n))

now_ms = int(time.time() * 1000)
check("fresh nonce accepted", ring_link.nonce_is_fresh(now_ms)[0])
check("601s-old nonce rejected", not ring_link.nonce_is_fresh(now_ms - 601_000)[0])
check("599s-old nonce accepted", ring_link.nonce_is_fresh(now_ms - 599_000)[0])
check("far-future nonce rejected", not ring_link.nonce_is_fresh(now_ms + 120_000)[0])
check("malformed timestamp rejected", not ring_link.nonce_is_fresh("abc")[0])

h = ring_link.make_password_hash(PW)
os.environ["FD_ADMIN_USER"] = USER
os.environ["FD_ADMIN_PASSWORD_HASH"] = h
ring_link.ADMIN_USER, ring_link.ADMIN_HASH = USER, h
check("correct password accepted", ring_link.check_password(USER, PW)[0])
check("wrong password rejected", not ring_link.check_password(USER, "nope")[0])
check("wrong username rejected", not ring_link.check_password("mallory", PW)[0])
check("hash is pbkdf2 with a random salt",
      h.startswith("pbkdf2_sha256$") and h != ring_link.make_password_hash(PW))

# Seed an unclaimed token and prove the nonce binds to exactly that account.
with open(TOKENS, "w", encoding="utf-8") as fh:
    json.dump({"unclaimed": {acct: {"access_token": "tok_abc"}}, "claimed": {}}, fh)
found, rec = ring_link.match_nonce(n, ts)
check("nonce matches its account", found == acct, found)
check("wrong nonce matches nothing", ring_link.match_nonce("xxxx", ts)[0] is None)
check("right nonce, wrong time matches nothing",
      ring_link.match_nonce(n, ts + 1)[0] is None)


# ---------------------------------------------------------------- http

print("\nHTTP surface Ring drives\n")

env = dict(os.environ, FRONTDESK_PORT=PORT, FD_CLASSIFY="0",
           FRONTDESK_STORE=os.path.join(ROOT, "_test_link.jsonl"))
proc = subprocess.Popen([sys.executable, "-u", "frontdesk.py"], cwd=ROOT, env=env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(4)


def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=10) as r:
            return r.status, r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


def post(path, fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(BASE + path, data=data, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="replace")


try:
    fresh_ts = int(time.time() * 1000)
    fresh_nonce = ring_link.compute_nonce(fresh_ts, acct)

    c, b = get(f"/oauth/authorize?nonce={fresh_nonce}&time={fresh_ts}")
    check("account link shows sign-in", c == 200 and "Sign in and link" in b)
    check("sign-in states images stay local", "never sent to a cloud" in b)

    c, b = get("/oauth/authorize")
    check("missing nonce rejected", c == 400 and "Bad link" in b)

    old = int(time.time() * 1000) - 700_000
    c, b = get(f"/oauth/authorize?nonce={ring_link.compute_nonce(old, acct)}&time={old}")
    check("stale link rejected", c == 400 and "expired" in b.lower())

    c, b = post("/oauth/authorize", {"nonce": fresh_nonce, "time": fresh_ts,
                                     "username": USER, "password": "wrong"})
    check("bad sign-in re-prompts", c == 200 and "Sign-in failed" in b)

    c, b = post("/oauth/token", {})
    check("token exchange needs a code", c == 400)

    c, b = get("/ring/webhook")
    check("webhook GET probe still answers", c == 200)

    c, b = get("/health")
    check("health still up", c == 200 and '"ok": true' in b)
finally:
    proc.kill()
    for f in (TOKENS, os.path.join(ROOT, "_test_link.jsonl")):
        if os.path.exists(f):
            os.remove(f)

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
