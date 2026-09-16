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

def mask_identifier(identifier):
    """Obfuscate the signed-in identity before sending it to Ring.

    Ring displays this value to the Ring user in a confirmation email, and the
    docs specify a masked form (their example: u***r@partner.example.com). It
    still has to be derived from the real signed-in session — this masks it,
    it does not invent one.
    """
    ident = (identifier or "").strip()
    if not ident:
        return ""
    if "@" in ident:
        local, _, domain = ident.partition("@")
        if len(local) <= 2:
            return f"{local[:1]}***@{domain}"
        return f"{local[0]}***{local[-1]}@{domain}"
    if len(ident) <= 2:
        return f"{ident[:1]}***"
    return f"{ident[0]}***{ident[-1]}"


def claim_and_confirm(account_id, rec, nonce, account_identifier):
    """Claim the matched token, then POST + PATCH app-integrations.

    The PATCH is mandatory: the integration sits in `awaiting` and is not
    operational until it lands, whatever the POST returned.
    """
    access = rec.get("access_token")
    url = f"{AVA_BASE}/v1/accounts/me/app-integrations"
    masked = mask_identifier(account_identifier)

    # Pass the nonce exactly as received — do not decode or re-encode it.
    body, err = _json_req(url, "POST", {
        "nonce": nonce,
        "account_identifier": masked,
    }, bearer=access)
    if err:
        return False, f"app-integrations POST failed: {err}"
    if (body or {}).get("status") and body["status"] != "awaiting":
        return False, f"unexpected POST status: {body['status']}"

    _, err = _json_req(url, "PATCH", {"status": "completed"}, bearer=access)
    if err:
        return False, f"app-integrations PATCH failed: {err}"

    d = _load()
    claimed = d["unclaimed"].pop(account_id, rec)
    claimed["account_identifier"] = masked
    claimed["claimed_at"] = int(time.time())
    d["claimed"][account_id] = claimed
    _save(d)
    return True, ""


def refresh_access_token(account_id, rec):
    """Trade the refresh token for a new access token.

    Access tokens last 14,400s (4 hours). Without this the link goes dead
    mid-demo and there is no recovery path short of re-linking. Credentials go
    in the form body, matching Ring's own sample (lib/auth.ts).
    """
    refresh = rec.get("refresh_token")
    if not refresh:
        return None, "no refresh token stored for this account"
    if not (CLIENT_ID and CLIENT_SECRET):
        return None, "client credentials not configured"

    tokens, err = _post_form(OAUTH_TOKEN_URL, {
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    })
    if err:
        return None, f"refresh failed: {err}"
    access = tokens.get("access_token")
    if not access:
        return None, "refresh response contained no access_token"

    d = _load()
    slot = "claimed" if account_id in d["claimed"] else "unclaimed"
    cur = d[slot].get(account_id, dict(rec))
    cur["access_token"] = access
    # Ring may rotate the refresh token; keep the new one if it sends one.
    if tokens.get("refresh_token"):
        cur["refresh_token"] = tokens["refresh_token"]
    cur["expires_in"] = tokens.get("expires_in")
    cur["refreshed_at"] = int(time.time())
    d[slot][account_id] = cur
    _save(d)
    return access, None


def access_token(auto_refresh=True):
    """A usable access token for Ring's API, refreshing if it is near expiry.

    Renews 60s early, the same margin Ring's sample uses.
    """
    d = _load()
    for account_id, rec in d["claimed"].items():
        if not rec.get("access_token"):
            continue
        issued = rec.get("refreshed_at") or rec.get("received_at") or 0
        ttl = rec.get("expires_in") or 0
        if auto_refresh and ttl and time.time() > (issued + ttl - 60):
            new, err = refresh_access_token(account_id, rec)
            if new:
                return new
            # Fall through and hand back the old one — it may still work, and
            # the caller's 401 is a clearer signal than None.
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
