#!/usr/bin/env python3
"""Ring one-way (Ring-initiated) account linking.

REPLACES the legacy bidirectional model. Ring's docs: the model where the
partner operates as an OAuth server is "supported for existing integrations
only — skip it for new work."

THE FLOW, as Ring specifies it:

  1. Ring POSTs an authorization code to our Token Exchange URL.
     We redeem it at oauth.ring.com within 60 seconds, call /v1/users/me to
     learn the Account ID, and park the token as UNCLAIMED, keyed by that id.

  2. Ring redirects the user to our Account Link URL with `nonce` and `time`.
     nonce = URL-safe-b64( HMAC-SHA256(signing_key, "<time_ms>:<account_id>") )
     with no padding. Reject anything older than 600 seconds.

  3. The user SIGNS IN here. Ring makes this mandatory: the signed-in identity
     is what claims the token, and without it a partner is trusting a redirect
     with customer data behind it.

  4. We recompute the nonce for each unclaimed token and constant-time compare.
     A match binds this Ring account to this signed-in operator.

  5. POST  /v1/accounts/me/app-integrations   (nonce + account_identifier)
     PATCH /v1/accounts/me/app-integrations   (status: completed)
     The PATCH is mandatory — without it the integration never goes live.

ONE KEY, TWO ENCODINGS — the same signing key verifies webhooks as HEX
(`sha256=` prefix) and computes nonces as URL-SAFE BASE64. Ring's docs warn
explicitly against mixing them, so each has its own function below.
"""

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request

SIGNING_KEY = os.environ.get("FRONTDESK_HMAC_KEY", "")
CLIENT_ID = os.environ.get("RING_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("RING_CLIENT_SECRET", "")
OAUTH_TOKEN_URL = os.environ.get("RING_TOKEN_URL", "https://oauth.ring.com/oauth/token")
AVA_BASE = os.environ.get("RING_API_BASE", "https://api.amazonvision.com")

ADMIN_USER = os.environ.get("FD_ADMIN_USER", "")
ADMIN_HASH = os.environ.get("FD_ADMIN_PASSWORD_HASH", "")

TOKENS_FILE = os.environ.get(
    "FD_TOKENS_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", ".tokens.json"))

NONCE_WINDOW_S = 600


# ------------------------------------------------------------------ storage

def _load():
    if not os.path.exists(TOKENS_FILE):
        return {"unclaimed": {}, "claimed": {}}
    try:
        with open(TOKENS_FILE, encoding="utf-8") as fh:
            d = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {"unclaimed": {}, "claimed": {}}
    d.setdefault("unclaimed", {})
    d.setdefault("claimed", {})
    return d


def _save(d):
    os.makedirs(os.path.dirname(TOKENS_FILE), exist_ok=True)
    tmp = TOKENS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=2)
    os.replace(tmp, TOKENS_FILE)
    try:
        os.chmod(TOKENS_FILE, 0o600)
    except OSError:
        pass


def status():
    """Counts only — never token material."""
    d = _load()
    return {"unclaimed": len(d["unclaimed"]), "claimed": len(d["claimed"]),
            "linked": bool(d["claimed"])}


# ------------------------------------------------------------------ nonce

def compute_nonce(timestamp_ms, account_id, key=None):
    """HMAC-SHA256 over "<time_ms>:<account_id>", URL-safe base64, no padding."""
    key = (key or SIGNING_KEY).encode()
    payload = f"{timestamp_ms}:{account_id}".encode()
    mac = hmac.new(key, payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).rstrip(b"=").decode()


def nonce_is_fresh(timestamp_ms, now_ms=None):
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    try:
        age = (now_ms - int(timestamp_ms)) / 1000.0
    except (TypeError, ValueError):
        return False, "malformed timestamp"
    if age < -60:
        return False, "timestamp is in the future"
    if age > NONCE_WINDOW_S:
        return False, f"stale nonce ({age:.0f}s old, limit {NONCE_WINDOW_S}s)"
    return True, ""


def match_nonce(nonce, timestamp_ms):
    """Find which unclaimed token this nonce binds to. Constant-time."""
    d = _load()
    for account_id, rec in d["unclaimed"].items():
        expected = compute_nonce(timestamp_ms, account_id)
        if hmac.compare_digest(expected, nonce or ""):
            return account_id, rec
    return None, None


# ------------------------------------------------------------------ http helpers

def _post_form(url, fields, bearer=None):
    data = urllib.parse.urlencode(fields).encode()
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    return _send(req)


def _json_req(url, method, payload=None, bearer=None):
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    return _send(req)


def _send(req):
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return (json.loads(raw) if raw else {}), None
    except urllib.error.HTTPError as e:
        detail = e.read()[:300].decode(errors="replace")
        return None, f"HTTP {e.code}: {detail}"
    except Exception as e:                       # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


# ------------------------------------------------------------------ step 1

def redeem_code(code):
    """Ring POSTed us a code. Trade it at Ring, then park it unclaimed.

    Must happen within 60 seconds of receiving the code.
    """
    if not (CLIENT_ID and CLIENT_SECRET):
        return None, "RING_CLIENT_ID / RING_CLIENT_SECRET not configured"

    tokens, err = _post_form(OAUTH_TOKEN_URL, {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    })
    if err:
        return None, f"token exchange failed: {err}"
    access = tokens.get("access_token")
    if not access:
        return None, "token response contained no access_token"

    me, err = _json_req(f"{AVA_BASE}/v1/users/me", "GET", bearer=access)
    if err:
        return None, f"users/me failed: {err}"
    account_id = ((me or {}).get("data") or {}).get("id")
    if not account_id:
        return None, "users/me returned no account id"

    d = _load()
    d["unclaimed"][account_id] = {
        "access_token": access,
        "refresh_token": tokens.get("refresh_token"),
        "scope": tokens.get("scope"),
        "expires_in": tokens.get("expires_in"),
        "received_at": int(time.time()),
    }
    _save(d)
    return account_id, None


# ------------------------------------------------------------------ sign-in

def check_password(user, password):
    """Single-operator sign-in. Hash format: pbkdf2_sha256$iters$salt_hex$hash_hex."""
    if not (ADMIN_USER and ADMIN_HASH):
        return False, "no operator credentials configured on this server"
    if not hmac.compare_digest(user or "", ADMIN_USER):
        return False, "bad credentials"
    try:
        algo, iters, salt_hex, want_hex = ADMIN_HASH.split("$")
        assert algo == "pbkdf2_sha256"
        got = hashlib.pbkdf2_hmac("sha256", (password or "").encode(),
                                  bytes.fromhex(salt_hex), int(iters))
    except Exception:                            # noqa: BLE001
        return False, "malformed FD_ADMIN_PASSWORD_HASH"
    if not hmac.compare_digest(got.hex(), want_hex):
        return False, "bad credentials"
    return True, ""


def make_password_hash(password, iters=310000):
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iters)
    return f"pbkdf2_sha256${iters}${salt.hex()}${h.hex()}"


# ------------------------------------------------------------------ steps 4-5

def claim_and_confirm(account_id, rec, nonce, account_identifier):
    """Claim the matched token, then POST + PATCH app-integrations.

    The PATCH is mandatory: without it the integration never becomes
    operational, whatever the POST returned.
    """
    access = rec.get("access_token")
    url = f"{AVA_BASE}/v1/accounts/me/app-integrations"

    _, err = _json_req(url, "POST", {
        "nonce": nonce,
        "account_identifier": account_identifier,
    }, bearer=access)
    if err:
        return False, f"app-integrations POST failed: {err}"

    _, err = _json_req(url, "PATCH", {"status": "completed"}, bearer=access)
    if err:
        return False, f"app-integrations PATCH failed: {err}"

    d = _load()
    claimed = d["unclaimed"].pop(account_id, rec)
    claimed["account_identifier"] = account_identifier
    claimed["claimed_at"] = int(time.time())
    d["claimed"][account_id] = claimed
    _save(d)
    return True, ""


def access_token():
    """The token to call Ring's API with, if we have one."""
    d = _load()
    for rec in d["claimed"].values():
        if rec.get("access_token"):
            return rec["access_token"]
    return None


if __name__ == "__main__":
    import getpass
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "hash":
        pw = getpass.getpass("operator password: ")
        if pw != getpass.getpass("again: "):
            sys.exit("passwords do not match")
        print("\nSet these in .env:")
        print(f"FD_ADMIN_USER=<your username>")
        print(f"FD_ADMIN_PASSWORD_HASH={make_password_hash(pw)}")
    else:
        print(json.dumps(status(), indent=2))
