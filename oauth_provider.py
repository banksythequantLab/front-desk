#!/usr/bin/env python3
"""OAuth authorization server — the side Ring talks to.

DIRECTION NOTE, because it is easy to get backwards:
Ring is the CLIENT. Our service is the AUTHORIZATION SERVER. Ring sends the
user to /oauth/authorize, receives a code, and POSTs it to /oauth/token to get
an access token. Ring then presents that token when calling our webhook.

That is why the official AmazonAppDev sample checks webhooks with a bearer
token: the token is one we issued to Ring.

Calling Ring's own API is the opposite direction and uses Ring's credentials
against oauth.ring.com — kept separate and not handled here.

SECURITY:
  - authorization codes are single-use and expire in 60s
  - client credentials are compared in constant time
  - redirect_uri is echoed exactly and must be absolute https
  - tokens are opaque random strings, stored hashed, never logged

Env:
  RING_CLIENT_ID / RING_CLIENT_SECRET  credentials Ring presents to us
  FD_TOKEN_TTL                         access token lifetime, default 30 days
  FD_GRANT_FILE                        where issued grants live (gitignored)
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.parse

CLIENT_ID = os.environ.get("RING_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("RING_CLIENT_SECRET", "")
TOKEN_TTL = int(os.environ.get("FD_TOKEN_TTL", str(30 * 24 * 3600)))
GRANT_FILE = os.environ.get(
    "FD_GRANT_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".grants.json"))

CODE_TTL = 60
_codes = {}          # code -> {redirect_uri, scope, expires}


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _load_grants():
    if not os.path.exists(GRANT_FILE):
        return {}
    try:
        with open(GRANT_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_grants(grants):
    with open(GRANT_FILE, "w", encoding="utf-8") as fh:
        json.dump(grants, fh, indent=2)
    try:
        os.chmod(GRANT_FILE, 0o600)
    except OSError:
        pass


def verify_bearer(token):
    """True if this bearer token is one we issued and has not expired."""
    if not token:
        return False
    rec = _load_grants().get(_hash(token))
    return bool(rec) and rec.get("expires", 0) > time.time()


def check_client(client_id, client_secret):
    if not (CLIENT_ID and CLIENT_SECRET):
        return False, "client credentials not configured on this server"
    if not hmac.compare_digest(client_id or "", CLIENT_ID):
        return False, "unknown client_id"
    if not hmac.compare_digest(client_secret or "", CLIENT_SECRET):
        return False, "bad client_secret"
    return True, ""


def client_from_request(headers, form):
    """Ring may authenticate via HTTP Basic or form body. Accept both."""
    auth = headers.get("Authorization", "")
    if auth.startswith("Basic "):
        try:
            raw = base64.b64decode(auth[6:]).decode()
            cid, _, csec = raw.partition(":")
            return cid, csec
        except Exception:                        # noqa: BLE001
            return "", ""
    return (form.get("client_id", [""])[0], form.get("client_secret", [""])[0])


def issue_code(redirect_uri, scope):
    code = secrets.token_urlsafe(32)
    _codes[code] = {"redirect_uri": redirect_uri, "scope": scope,
                    "expires": time.time() + CODE_TTL}
    # opportunistic sweep
    for k, v in list(_codes.items()):
        if v["expires"] < time.time():
            _codes.pop(k, None)
    return code


def redeem_code(code, redirect_uri):
    """Single-use. Returns (grant, error)."""
    rec = _codes.pop(code, None)
    if not rec:
        return None, "invalid_grant: unknown or already-used code"
    if rec["expires"] < time.time():
        return None, "invalid_grant: code expired"
    if redirect_uri and rec["redirect_uri"] and redirect_uri != rec["redirect_uri"]:
        return None, "invalid_grant: redirect_uri mismatch"
    return rec, ""


def issue_token(scope):
    access = secrets.token_urlsafe(40)
    refresh = secrets.token_urlsafe(40)
    grants = _load_grants()
    grants[_hash(access)] = {"scope": scope, "expires": time.time() + TOKEN_TTL,
                             "issued": time.time(), "refresh": _hash(refresh)}
    _save_grants(grants)
    return {"access_token": access, "token_type": "Bearer",
            "expires_in": TOKEN_TTL, "refresh_token": refresh, "scope": scope}


def build_redirect(redirect_uri, code, state):
    sep = "&" if "?" in redirect_uri else "?"
    q = {"code": code}
    if state:
        q["state"] = state
    return f"{redirect_uri}{sep}{urllib.parse.urlencode(q)}"
