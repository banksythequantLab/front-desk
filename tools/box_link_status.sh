cd /opt/banksy/front-desk
echo "=== link status ==="
FD_TOKENS_FILE=/opt/banksy/front-desk/data/.tokens.json ./.venv/bin/python ring_link.py

echo
echo "=== linking log ==="
grep -E 'token parked|nonce|ACCOUNT LINKED|sign-in|redemption|app-integrations|confirmation failed' \
  logs/receiver.log 2>/dev/null | tail -12

echo
echo "=== devices on the linked account ==="
set -a; . ./.env; set +a
./.venv/bin/python - <<'PY'
import json, sys, urllib.request, urllib.error
sys.path.insert(0, "/opt/banksy/front-desk")
import ring_link

tok = ring_link.access_token()
if not tok:
    print("  no claimed token yet")
    raise SystemExit(0)

def call(path):
    req = urllib.request.Request("https://api.amazonvision.com" + path,
                                 headers={"Authorization": "Bearer " + tok})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300].decode(errors="replace")

code, body = call("/v1/devices?include=status,capabilities,location")
print("  HTTP", code)
if isinstance(body, dict):
    for d in body.get("data") or []:
        a = d.get("attributes") or {}
        print(f"    {a.get('name','?'):<22} {d.get('id','')[:44]}...")
else:
    print("   ", body)
PY
