cd /opt/banksy/front-desk
set -a; . ./.env; set +a
./.venv/bin/python - <<'PY'
import json, sys, urllib.request, urllib.error
sys.path.insert(0, "/opt/banksy/front-desk")
import ring_link

tok = ring_link.access_token()

def api(path):
    r = urllib.request.Request(ring_link.AVA_BASE + path,
        headers={"Authorization": "Bearer " + tok, "Accept": "*/*",
                 "User-Agent": ring_link.USER_AGENT})
    try:
        with urllib.request.urlopen(r, timeout=40) as x:
            return x.status, json.loads(x.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:260].decode(errors="replace")

code, devs = api("/v1/devices")
for d in (devs.get("data") or []):
    did = d["id"]; name = (d.get("attributes") or {}).get("name", "?")
    print("=" * 60)
    print(name)
    for label, path in (("configurations", "/v1/devices/" + did + "/configurations"),
                        ("status",         "/v1/devices/" + did + "/status"),
                        ("history",        "/v1/history/devices/" + did + "/events?limit=5")):
        c, body = api(path)
        print("  " + label + ": HTTP", c)
        if isinstance(body, dict):
            print("   ", json.dumps(body)[:420])
        else:
            print("   ", body[:220])
PY
