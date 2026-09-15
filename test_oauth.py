#!/usr/bin/env python3
"""Exercise the OAuth provider the way Ring will drive it.

Ring is the client: it sends the user to /oauth/authorize, receives a code at
its redirect_uri, then POSTs that code to /oauth/token with client credentials.
"""
import base64, json, sys, urllib.error, urllib.parse, urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8310"
CID = "test-client"
CSEC = "test-secret"
REDIRECT = "https://client.example.com/cb"

results = []
def check(name, ok, detail=""):
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:<44} {detail}")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


opener = urllib.request.build_opener(NoRedirect)


def get(path):
    try:
        with opener.open(BASE + path, timeout=10) as r:
            return r.status, r.headers.get("Location"), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location"), e.read()


def post_token(form, basic=True, cid=CID, csec=CSEC):
    data = urllib.parse.urlencode(form).encode()
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if basic:
        headers["Authorization"] = "Basic " + base64.b64encode(
            f"{cid}:{csec}".encode()).decode()
    req = urllib.request.Request(BASE + "/oauth/token", data=data,
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


print(f"OAuth provider test against {BASE}\n")

q = urllib.parse.urlencode({"client_id": CID, "response_type": "code",
                            "redirect_uri": REDIRECT, "scope": "ava.v1:read",
                            "state": "xyz123"})

code_, loc, body = get(f"/oauth/authorize?{q}")
check("authorize shows consent page", code_ == 200 and b"Allow" in body)

code_, loc, _ = get(f"/oauth/authorize?{q}&confirm=1")
check("consent redirects to client", code_ == 302 and loc and loc.startswith(REDIRECT), loc)

auth_code, state = "", ""
if loc:
    p = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)
    auth_code = p.get("code", [""])[0]
    state = p.get("state", [""])[0]
check("code returned", bool(auth_code))
check("state echoed back", state == "xyz123", state)

code_, _, _ = get("/oauth/authorize?client_id=x&redirect_uri=http://insecure.example/cb&confirm=1")
check("rejects non-https redirect_uri", code_ == 400)

st, tok = post_token({"grant_type": "authorization_code", "code": auth_code,
                      "redirect_uri": REDIRECT})
check("token exchange succeeds", st == 200 and "access_token" in tok,
      f"type={tok.get('token_type')} ttl={tok.get('expires_in')}")
check("refresh token issued", bool(tok.get("refresh_token")))

st, err = post_token({"grant_type": "authorization_code", "code": auth_code,
                      "redirect_uri": REDIRECT})
check("code is single-use", st == 400 and err.get("error") == "invalid_grant")

_, loc2, _ = get(f"/oauth/authorize?{q}&confirm=1")
c2 = urllib.parse.parse_qs(urllib.parse.urlparse(loc2).query).get("code", [""])[0]
st, err = post_token({"grant_type": "authorization_code", "code": c2,
                      "redirect_uri": REDIRECT}, csec="wrong-secret")
check("bad client_secret rejected", st == 401 and err.get("error") == "invalid_client")

st, err = post_token({"grant_type": "authorization_code", "code": c2,
                      "redirect_uri": REDIRECT}, cid="wrong-client")
check("unknown client_id rejected", st == 401)

st, err = post_token({"grant_type": "password", "code": c2})
check("unsupported grant_type rejected", st == 400 and
      err.get("error") == "unsupported_grant_type")

st, tok2 = post_token({"grant_type": "authorization_code", "code": c2,
                       "redirect_uri": REDIRECT, "client_id": CID,
                       "client_secret": CSEC}, basic=False)
check("form-body client auth also works", st == 200 and "access_token" in tok2)

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
